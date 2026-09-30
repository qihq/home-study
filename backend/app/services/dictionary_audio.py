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
  (type=1 British, type=2 American; also reads Chinese words). This synthesized
  voice is the first source for the fast ``standard`` mode and is backed by
  Baidu when unavailable.
- Baidu Translate TTS: ``https://fanyi.baidu.com/gettts`` -- reads Chinese (and
  English) words reliably from behind the NAS network; fallback for the
  ``standard`` mode before configured TTS.

The public dictionary UI keeps two independent source chains and caches:
``standard`` uses Youdao then Baidu, while ``human`` uses Wiktionary then Free
Dictionary and never falls back to synthesized audio. The internal ``preferred``
mode preserves the older human-first chain for dictation and learning workers.

Downloaded audio is cached under ``<data>/tts/dictionary-audio`` and referenced by
``TtsAsset`` rows with ``provider='dictionary_audio'``. Failures raise
:class:`DictionaryAudioError` so callers can fall back to configured TTS where
appropriate. Ogg recordings are transcoded to mp3 when ffmpeg is available
(Safari cannot decode Ogg Vorbis); otherwise the .ogg file is kept and served
as ``audio/ogg``.
"""

import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tts_asset import TtsAsset

Accent = Literal['uk', 'us']
AudioMode = Literal['preferred', 'standard', 'human']

# Bumped from 2: standard and human pronunciation now use independent caches.
DICTIONARY_AUDIO_VERSION = 3
YOUDAO_DICTVOICE_URL = 'https://dict.youdao.com/dictvoice?audio={text}&type={kind}'
FREE_DICTIONARY_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'
WIKTIONARY_URL = 'https://en.wiktionary.org/wiki/{word}'
BAIDU_TTS_URL = 'https://fanyi.baidu.com/gettts?lan={lang}&text={text}&spd=3&source=web'
USER_AGENT = 'family-learning/1.0 (dictionary audio)'
BAIDU_USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'

# Failures of a source are remembered in-process so a flaky/unreachable source
# does not delay every word lookup with a full timeout. Two failures inside the
# window open a circuit breaker that skips the source entirely for a while.
# The breaker state is persisted to disk so a container restart does not make
# the first word wait through unreachable sources again (wall-clock based).
MISS_TTL_SECONDS = 6 * 3600
_MISS_CACHE: dict[str, float] = {}
BREAKER_TRIP_FAILURES = 2
BREAKER_OPEN_SECONDS = 10 * 60
_BREAKER_UNTIL: dict[str, float] = {}
_FAILURE_TIMES: dict[str, float] = {}
_BREAKER_STATE_LOADED = False

_ENGLISH_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_CHINESE_WORD = re.compile(r'[\u3400-\u9fff]{1,12}')
_WIKIMEDIA_AUDIO = re.compile(r'//upload\.wikimedia\.org/[^"\s\\<>]+\.(?:ogg|oga|mp3|wav)', re.IGNORECASE)


class DictionaryAudioError(Exception):
    pass


@dataclass
class _AudioFlight:
    event: threading.Event = field(default_factory=threading.Event)
    result: tuple[Path, str] | None = None
    error_code: str | None = None


_AUDIO_FLIGHTS: dict[str, _AudioFlight] = {}
_AUDIO_FLIGHTS_LOCK = threading.Lock()


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


def _request(url: str, timeout: float, user_agent: str = USER_AGENT, retries: int = 1) -> bytes:
    last_error: DictionaryAudioError | None = None
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers={'User-Agent': user_agent}), timeout=timeout) as response:
                content_type = response.headers.get_content_type()
                data = response.read()
        except OSError as error:
            last_error = DictionaryAudioError('DICTIONARY_AUDIO_FETCH_FAILED')
            if attempt + 1 < retries:
                time.sleep(0.5)
                continue
            raise last_error from error
        if len(data) < 64:
            last_error = DictionaryAudioError('DICTIONARY_AUDIO_EMPTY')
            if attempt + 1 < retries:
                time.sleep(0.5)
                continue
            raise last_error
        if content_type.startswith('audio/') or _looks_like_audio(data):
            return data
        last_error = DictionaryAudioError('DICTIONARY_AUDIO_UNRECOGNIZED')
        if attempt + 1 < retries:
            time.sleep(0.5)
            continue
        raise last_error
    raise last_error if last_error is not None else DictionaryAudioError('DICTIONARY_AUDIO_FETCH_FAILED')


def _youdao_bytes(text: str, accent: Accent, timeout: float) -> bytes:
    kind = '1' if accent == 'uk' else '2'
    return _request(YOUDAO_DICTVOICE_URL.format(text=quote(text), kind=kind), timeout, retries=2)


def _baidu_bytes(text: str, lang: str, timeout: float) -> bytes:
    return _request(
        BAIDU_TTS_URL.format(lang=lang, text=quote(text)), timeout,
        user_agent=BAIDU_USER_AGENT, retries=2,
    )


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


def _cache_key(text: str, accent: Accent, mode: AudioMode = 'preferred') -> str:
    return hashlib.sha256(
        f'dictionary-audio:v{DICTIONARY_AUDIO_VERSION}\n{mode}\n{text}\n{accent}'.encode()
    ).hexdigest()


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


def _breaker_state_path() -> Path:
    return get_settings().tts_dir / 'dictionary-audio-breaker.json'


def _load_persisted_breaker_state() -> None:
    """Merge the on-disk breaker state into memory; never raises."""
    global _BREAKER_STATE_LOADED
    if _BREAKER_STATE_LOADED:
        return
    _BREAKER_STATE_LOADED = True
    try:
        path = _breaker_state_path()
        if not path.is_file():
            return
        state = json.loads(path.read_text())
    except (OSError, ValueError):
        return
    for source, entry in state.items():
        if not isinstance(entry, dict):
            continue
        until = entry.get('open_until')
        if isinstance(until, (int, float)) and until > time.time():
            _BREAKER_UNTIL.setdefault(source, until)
        failures = entry.get('failure_count', 0)
        if isinstance(failures, int):
            _FAILURE_TIMES.setdefault(source, float(failures))


def _save_persisted_breaker_state() -> None:
    """Write the breaker state to disk; never raises."""
    try:
        state = {
            source: {'open_until': _BREAKER_UNTIL.get(source, 0.0), 'failure_count': _FAILURE_TIMES.get(source, 0)}
            for source in set(_BREAKER_UNTIL) | set(_FAILURE_TIMES)
        }
        path = _breaker_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix('.json.part')
        partial.write_text(json.dumps(state))
        partial.replace(path)
    except OSError:
        pass


def _breaker_open(source: str) -> bool:
    _load_persisted_breaker_state()
    until = _BREAKER_UNTIL.get(source)
    return until is not None and time.time() < until


def _record_source_failure(source: str) -> None:
    _load_persisted_breaker_state()
    now = time.time()
    recent = _FAILURE_TIMES.get(source, 0) + 1
    _FAILURE_TIMES[source] = recent
    if recent >= BREAKER_TRIP_FAILURES:
        _BREAKER_UNTIL[source] = now + BREAKER_OPEN_SECONDS
    _save_persisted_breaker_state()


def _record_source_success(source: str) -> None:
    _load_persisted_breaker_state()
    _FAILURE_TIMES.pop(source, None)
    _BREAKER_UNTIL.pop(source, None)
    _save_persisted_breaker_state()


def _sources_for_mode(
    normalized: str, source_language: str, accent: Accent, timeout: float, mode: AudioMode,
) -> list[tuple[str, Callable[[], bytes]]]:
    human_sources: list[tuple[str, Callable[[], bytes]]] = []
    if source_language == 'en':
        human_sources = [
            ('wiktionary', lambda: _wiktionary_bytes(normalized, accent, timeout)),
            ('dictionaryapi.dev', lambda: _free_dictionary_bytes(normalized, accent, timeout)),
        ]
    standard_sources: list[tuple[str, Callable[[], bytes]]] = [
        ('dictvoice', lambda: _youdao_bytes(normalized, accent, timeout)),
        ('baidu', lambda: _baidu_bytes(normalized, 'en' if source_language == 'en' else 'zh', timeout)),
    ]
    if mode == 'human':
        return human_sources
    if mode == 'standard':
        return standard_sources
    if mode == 'preferred':
        return human_sources + standard_sources
    raise DictionaryAudioError('DICTIONARY_AUDIO_MODE_INVALID')


def _fetch_word_audio_uncached(
    normalized: str, source_language: str, accent: Accent, timeout: float, refresh: bool, mode: AudioMode,
) -> tuple[Path, str]:
    key = _cache_key(normalized, accent, mode)
    last_error: DictionaryAudioError | None = None
    for source, fetch in _sources_for_mode(normalized, source_language, accent, timeout, mode):
        if not refresh and (_breaker_open(source) or _miss_fresh(source, normalized, accent)):
            continue
        try:
            data = fetch()
        except DictionaryAudioError as error:
            last_error = error
            _record_miss(source, normalized, accent)
            _record_source_failure(source)
            continue
        _record_source_success(source)
        suffix = _audio_suffix(data)
        if suffix == '.ogg':
            transcoded = _transcode_to_mp3(data)
            if transcoded is not None:
                data, suffix = transcoded, '.mp3'
        target = _new_path(key, suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f'{target.name}.{uuid4().hex}.part')
        try:
            partial.write_bytes(data)
            partial.replace(target)
        finally:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
        return target, source
    raise DictionaryAudioError('DICTIONARY_AUDIO_NOT_FOUND') from last_error


def fetch_word_audio(
    text: str, source_language: str, accent: Accent = 'us', timeout: float = 10, refresh: bool = False,
    mode: AudioMode = 'preferred',
) -> tuple[Path, str]:
    """Fetch and cache one pronunciation mode for a single word.

    ``standard`` uses Youdao then Baidu, ``human`` uses Wiktionary then Free
    Dictionary, and the internal ``preferred`` mode preserves the legacy
    human-first chain for dictation and learning-item workers. Concurrent calls
    for the same mode, normalized word and accent share one in-process fetch.
    """
    normalized = ' '.join(text.strip().split())
    if not is_single_word(normalized, source_language):
        raise DictionaryAudioError('DICTIONARY_AUDIO_NOT_A_WORD')
    key = _cache_key(normalized, accent, mode)
    if not refresh:
        cached = _cached_path(key)
        if cached is not None:
            return cached, 'cached'

    with _AUDIO_FLIGHTS_LOCK:
        flight = _AUDIO_FLIGHTS.get(key)
        owner = flight is None
        if flight is None:
            flight = _AudioFlight()
            _AUDIO_FLIGHTS[key] = flight

    if not owner:
        flight.event.wait()
        if flight.result is not None:
            return flight.result
        raise DictionaryAudioError(flight.error_code or 'DICTIONARY_AUDIO_FETCH_FAILED')

    result: tuple[Path, str] | None = None
    error_code: str | None = None
    try:
        result = _fetch_word_audio_uncached(normalized, source_language, accent, timeout, refresh, mode)
        return result
    except DictionaryAudioError as error:
        error_code = str(error)
        raise
    except Exception as error:
        error_code = 'DICTIONARY_AUDIO_FETCH_FAILED'
        raise DictionaryAudioError(error_code) from error
    finally:
        with _AUDIO_FLIGHTS_LOCK:
            flight.result = result
            flight.error_code = error_code
            flight.event.set()
            if _AUDIO_FLIGHTS.get(key) is flight:
                _AUDIO_FLIGHTS.pop(key, None)


def dictionary_asset_cache_key(
    text: str, accent: Accent, owner: str, mode: AudioMode = 'preferred',
) -> str:
    return hashlib.sha256(
        f'dictionary-audio:v{DICTIONARY_AUDIO_VERSION}:{mode}:{owner}:{accent}:{text}'.encode()
    ).hexdigest()


def prefetch_word_audio(
    text: str, source_language: str, accents: tuple[Accent, ...] = ('us',), timeout: float = 5,
    mode: AudioMode = 'standard',
) -> dict[str, str]:
    """Best-effort cache fill; by default only the standard American audio."""
    fetched: dict[str, str] = {}
    for accent in accents:
        try:
            _path, source = fetch_word_audio(
                text, source_language, accent, timeout=timeout, mode=mode,
            )
            fetched[accent] = source
        except DictionaryAudioError:
            continue
    return fetched


def ensure_word_audio_asset(
    session: Session, text: str, source_language: str, *,
    accent: Accent = 'us', owner_user_id: str | None = None, regenerate: bool = False, timeout: float = 10,
    mode: AudioMode = 'preferred',
) -> TtsAsset | None:
    """Return a ready mode-specific ``TtsAsset`` backed by word audio, or None."""
    normalized = ' '.join(text.strip().split())
    if not is_single_word(normalized, source_language):
        return None
    owner = owner_user_id or 'shared'
    key = dictionary_asset_cache_key(normalized, accent, owner, mode)
    if not regenerate:
        existing = session.scalar(select(TtsAsset).where(TtsAsset.cache_key == key, TtsAsset.status == 'ready'))
        if existing is not None and Path(existing.path).is_file():
            return existing
    try:
        path, source = fetch_word_audio(
            normalized, source_language, accent, timeout=timeout, refresh=regenerate, mode=mode,
        )
    except DictionaryAudioError:
        return None
    locale = 'en-US' if source_language == 'en' else 'zh-CN'
    asset = session.scalar(select(TtsAsset).where(TtsAsset.cache_key == key))
    if asset is None:
        asset = TtsAsset(
            cache_key=key, provider='dictionary_audio', model=source if source != 'cached' else mode,
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
