"""Word-level pronunciations from free dictionary audio sources.

Verified public sources (no API key required):

- Wiktionary (``https://en.wiktionary.org/wiki/<word>``): the English section of
  the page links pronunciation recordings hosted on Wikimedia Commons
  (``upload.wikimedia.org``), including pre-transcoded mp3 copies. These are
  recordings of real human speakers.
- Free Dictionary API: ``https://api.dictionaryapi.dev/api/v2/entries/en/<word>``
  (Wiktionary data: phonetics with UK/US mp3/ogg audio URLs). Kept as a
  redundancy fallback; its media proxy can be flaky.
- Youdao dictvoice: ``https://dict.youdao.com/dictvoice?audio=<text>&type=1|2``
  (type=1 British, type=2 American; also reads Chinese words). Note that this
  endpoint serves Youdao's *synthesized* voice, not a human recording, so it is
  the last resort.

Downloaded audio is cached under ``<data>/tts/dictionary-audio`` and referenced by
``TtsAsset`` rows with ``provider='dictionary_audio'``. Failures raise
:class:`DictionaryAudioError` so callers can fall back to configured TTS.

Human recordings are preferred over synthesized audio for single English words:
the MiMo TTS models are broadcast/performance oriented and do not guarantee
faithful single-word pronunciation, and Youdao dictvoice is synthesized too.
Ogg recordings are transcoded to mp3 when ffmpeg is available (Safari cannot
decode Ogg Vorbis); otherwise the .ogg file is kept and served as ``audio/ogg``.
"""

import hashlib
import json
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tts_asset import TtsAsset

Accent = Literal['uk', 'us']

# Bumped from 1: English words now prefer human dictionary recordings over the
# synthesized Youdao voice, so previously cached files must be re-fetched.
DICTIONARY_AUDIO_VERSION = 2
YOUDAO_DICTVOICE_URL = 'https://dict.youdao.com/dictvoice?audio={text}&type={kind}'
FREE_DICTIONARY_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'
WIKTIONARY_URL = 'https://en.wiktionary.org/wiki/{word}'
USER_AGENT = 'family-learning/1.0 (dictionary audio)'

# Failures of a source are remembered in-process so a flaky/unreachable source
# does not delay every word lookup with a full timeout.
MISS_TTL_SECONDS = 6 * 3600
_MISS_CACHE: dict[str, float] = {}

_ENGLISH_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_CHINESE_WORD = re.compile(r'[\u3400-\u9fff]{1,12}')
_WIKIMEDIA_AUDIO = re.compile(r'//upload\.wikimedia\.org/[^"\s\\<>]+\.(?:ogg|oga|mp3|wav)', re.IGNORECASE)


class DictionaryAudioError(Exception):
    pass


def is_single_word(text: str, source_language: str) -> bool:
    normalized = ' '.join(text.split())
    if source_language == 'en':
        return bool(_ENGLISH_WORD.fullmatch(normalized))
    return bool(_CHINESE_WORD.fullmatch(normalized))


def _looks_like_audio(data: bytes) -> bool:
    if len(data) < 64:
        return False
    if data.startswith(b'ID3') or data.startswith(b'RIFF') or data.startswith(b'OggS'):
        return True
    return data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def _request(url: str, timeout: float) -> bytes:
    try:
        with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            data = response.read()
    except OSError as error:
        raise DictionaryAudioError('DICTIONARY_AUDIO_FETCH_FAILED') from error
    if len(data) < 64:
        raise DictionaryAudioError('DICTIONARY_AUDIO_EMPTY')
    if content_type.startswith('audio/') or _looks_like_audio(data):
        return data
    raise DictionaryAudioError('DICTIONARY_AUDIO_UNRECOGNIZED')


def _youdao_bytes(text: str, accent: Accent, timeout: float) -> bytes:
    kind = '1' if accent == 'uk' else '2'
    return _request(YOUDAO_DICTVOICE_URL.format(text=quote(text), kind=kind), timeout)


def _accent_marked(name: str, accent: Accent) -> bool:
    """Whether an audio filename carries the requested accent marker.

    Matches ``En-us-apple.ogg`` (``en-us`` inside the name) and
    ``apple-us.mp3`` (``-us`` right before the extension) while avoiding
    word-internal false positives like ``fr-bonus.ogg``.
    """
    stem = name.rsplit('.', 1)[0]
    return f'en-{accent}' in name or f'en_{accent}' in name or stem.endswith(f'-{accent}')


def _pick_audio_url(urls: list[str], accent: Accent, *, wikimedia: bool = False) -> str | None:
    """Pick the best audio URL for the requested accent.

    Human pronunciation files are named like ``apple-us.mp3`` (accent marker
    right before the extension), ``En-us-apple.ogg`` or ``read-1-us.ogg``
    (accent and a ``-1-`` primary-reading marker in the stem). Prefer the
    requested accent, then an English recording, then the primary reading,
    then mp3 (plays everywhere, with Wikimedia pre-transcoded mp3 ranked
    highest); keep list order for ties.
    """
    if not urls:
        return None

    def score(url: str) -> tuple[int, int]:
        lowered = url.lower()
        name = unquote(lowered.rsplit('/', 1)[-1])
        points = 0
        if _accent_marked(name, accent):
            points += 8
        if wikimedia:
            if name.startswith('en-') or name.startswith('ll-q1860'):
                points += 4
            if '/transcoded/' in lowered and name.endswith('.mp3'):
                points += 3
        if '-1-' in name or '_1_' in name:
            points += 2
        if name.endswith('.mp3'):
            points += 1
        return points

    ranked = sorted(enumerate(urls), key=lambda pair: (score(pair[1]), -pair[0]), reverse=True)
    return ranked[0][1]


def _english_section_audio_urls(text: str) -> list[str]:
    """Audio URLs from the English language section of a Wiktionary page."""
    start = text.find('id="English"')
    if start < 0:
        return []
    rest = text[start:]
    next_language = re.search(r'<h2', rest)
    section = rest[:next_language.start()] if next_language else rest
    return [url.replace('&amp;', '&') for url in _WIKIMEDIA_AUDIO.findall(section)]


def _wiktionary_bytes(word: str, accent: Accent, timeout: float) -> bytes:
    try:
        with urlopen(Request(WIKTIONARY_URL.format(word=quote(word)), headers={'User-Agent': USER_AGENT}), timeout=timeout) as response:
            text = response.read().decode('utf-8', 'ignore')
    except OSError as error:
        raise DictionaryAudioError('DICTIONARY_AUDIO_FETCH_FAILED') from error
    preferred = _pick_audio_url(_english_section_audio_urls(text), accent, wikimedia=True)
    if preferred is None:
        raise DictionaryAudioError('DICTIONARY_AUDIO_NOT_FOUND')
    return _request('https:' + preferred, timeout)


def _free_dictionary_bytes(word: str, accent: Accent, timeout: float) -> bytes:
    try:
        with urlopen(Request(FREE_DICTIONARY_URL.format(word=quote(word)), headers={'User-Agent': USER_AGENT}), timeout=timeout) as response:
            entries = json.loads(response.read())
    except (OSError, ValueError) as error:
        raise DictionaryAudioError('DICTIONARY_AUDIO_FETCH_FAILED') from error
    audio_urls = [
        (phonetic.get('audio') or '').strip()
        for entry in entries
        for phonetic in entry.get('phonetics', [])
    ]
    audio_urls = [url for url in audio_urls if url]
    preferred = _pick_audio_url(audio_urls, accent)
    if preferred is None:
        raise DictionaryAudioError('DICTIONARY_AUDIO_NOT_FOUND')
    return _request(preferred, timeout)


def _cache_key(text: str, accent: Accent) -> str:
    return hashlib.sha256(f'dictionary-audio:v{DICTIONARY_AUDIO_VERSION}\n{text}\n{accent}'.encode()).hexdigest()


def _base_dir(key: str) -> Path:
    return get_settings().tts_dir / 'dictionary-audio' / key[:2]


def _cached_path(key: str) -> Path | None:
    base = _base_dir(key)
    for suffix in ('.mp3', '.ogg'):
        path = base / f'{key}{suffix}'
        if path.is_file():
            return path
    return None


def _new_path(key: str, suffix: str) -> Path:
    return _base_dir(key) / f'{key}{suffix}'


def _audio_suffix(data: bytes) -> str:
    return '.ogg' if data.startswith(b'OggS') else '.mp3'


def _transcode_to_mp3(data: bytes) -> bytes | None:
    """Convert Ogg audio to mp3 when ffmpeg is available; None on any failure."""
    if shutil.which('ffmpeg') is None:
        return None
    try:
        completed = subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error', '-i', 'pipe:0', '-map', '0:a:0',
             '-c:a', 'libmp3lame', '-q:a', '5', '-f', 'mp3', 'pipe:1'],
            input=data, capture_output=True, timeout=20, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = completed.stdout
    return output if _looks_like_audio(output) else None


def _miss_key(source: str, text: str, accent: Accent) -> str:
    return f'{source}|{text}|{accent}'


def _miss_fresh(source: str, text: str, accent: Accent) -> bool:
    recorded = _MISS_CACHE.get(_miss_key(source, text, accent))
    return recorded is not None and time.monotonic() - recorded < MISS_TTL_SECONDS


def _record_miss(source: str, text: str, accent: Accent) -> None:
    _MISS_CACHE[_miss_key(source, text, accent)] = time.monotonic()


def fetch_word_audio(
    text: str, source_language: str, accent: Accent = 'us', timeout: float = 10, refresh: bool = False,
) -> tuple[Path, str]:
    """Fetch single-word pronunciation audio, caching it on disk.

    English words try human recordings (Wiktionary/Wikimedia first, Free
    Dictionary API second) and fall back to the synthesized Youdao voice;
    Chinese words use Youdao only. Returns ``(path, source)`` where source is
    ``'wiktionary'``, ``'dictionaryapi.dev'``, ``'dictvoice'`` or ``'cached'``
    when the file already existed.
    Raises :class:`DictionaryAudioError` when the text is not a single word or
    every source fails; a previously cached file is kept on refresh failures.
    """
    normalized = ' '.join(text.strip().split())
    if not is_single_word(normalized, source_language):
        raise DictionaryAudioError('DICTIONARY_AUDIO_NOT_A_WORD')
    key = _cache_key(normalized, accent)
    if not refresh:
        cached = _cached_path(key)
        if cached is not None:
            return cached, 'cached'
    sources: list[tuple[str, Callable[[], bytes]]] = []
    if source_language == 'en':
        sources.append(('wiktionary', lambda: _wiktionary_bytes(normalized, accent, timeout)))
        sources.append(('dictionaryapi.dev', lambda: _free_dictionary_bytes(normalized, accent, timeout)))
    sources.append(('dictvoice', lambda: _youdao_bytes(normalized, accent, timeout)))
    last_error: DictionaryAudioError | None = None
    for source, fetch in sources:
        if not refresh and _miss_fresh(source, normalized, accent):
            continue
        try:
            data = fetch()
        except DictionaryAudioError as error:
            last_error = error
            _record_miss(source, normalized, accent)
            continue
        suffix = _audio_suffix(data)
        if suffix == '.ogg':
            transcoded = _transcode_to_mp3(data)
            if transcoded is not None:
                data, suffix = transcoded, '.mp3'
        target = _new_path(key, suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(f'{suffix}.part')
        partial.write_bytes(data)
        partial.replace(target)
        return target, source
    raise DictionaryAudioError('DICTIONARY_AUDIO_NOT_FOUND') from last_error


def dictionary_asset_cache_key(text: str, accent: Accent, owner: str) -> str:
    return hashlib.sha256(f'dictionary-audio:v{DICTIONARY_AUDIO_VERSION}:{owner}:{accent}:{text}'.encode()).hexdigest()


def ensure_word_audio_asset(
    session: Session, text: str, source_language: str, *,
    accent: Accent = 'us', owner_user_id: str | None = None, regenerate: bool = False,
) -> TtsAsset | None:
    """Return a ready ``TtsAsset`` backed by free dictionary audio, or None.

    Returns ``None`` when the text is not a single word or every audio source
    fails, so callers can fall back to configured TTS. ``regenerate`` bypasses
    both the asset and the file cache and re-fetches from the network.
    """
    normalized = ' '.join(text.strip().split())
    if not is_single_word(normalized, source_language):
        return None
    owner = owner_user_id or 'shared'
    key = dictionary_asset_cache_key(normalized, accent, owner)
    if not regenerate:
        existing = session.scalar(select(TtsAsset).where(TtsAsset.cache_key == key, TtsAsset.status == 'ready'))
        if existing is not None:
            return existing
    try:
        path, source = fetch_word_audio(normalized, source_language, accent, refresh=regenerate)
    except DictionaryAudioError:
        return None
    locale = 'en-US' if source_language == 'en' else 'zh-CN'
    asset = session.scalar(select(TtsAsset).where(TtsAsset.cache_key == key))
    if asset is None:
        asset = TtsAsset(
            cache_key=key, provider='dictionary_audio', model=source if source != 'cached' else 'dictvoice',
            voice=accent, locale=locale, speed=1.0, normalized_text=normalized[:160], path=str(path),
        )
        if owner_user_id is not None:
            asset.owner_user_id = owner_user_id
        session.add(asset)
    else:
        if source != 'cached':
            asset.model = source
        asset.provider = 'dictionary_audio'
        asset.voice, asset.locale, asset.speed = accent, locale, 1.0
        asset.normalized_text, asset.path = normalized[:160], str(path)
        asset.status = 'ready'
        asset.failure_count = 0
    session.commit()
    session.refresh(asset)
    return asset
