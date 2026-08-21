"""Free online dictionary tier for English words (no API key required).

Verified public sources:

- Youdao jsonapi: ``https://dict.youdao.com/jsonapi?q=<word>``
  (bilingual en→zh entries: UK/US phonetics, parts of speech, meanings).
- Free Dictionary API: ``https://api.dictionaryapi.dev/api/v2/entries/en/<word>``
  (Wiktionary data: UK/US phonetics, definitions, English examples).

The local SQLite dictionary sits below this tier and the LLM tier sits above
it. Results are cached in ``dictionary_entries`` with a 30-day TTL keyed by
:data:`ONLINE_FINGERPRINT`, so stale cache entries refetch transparently.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dictionary import DictionaryEntry, DictionaryHistory
from app.schemas.dictionary import DictionaryExample, DictionaryResult, PartOfSpeech
from app.services.learning_items import normalize_learning_text

ONLINE_FINGERPRINT = 'online-v1'
ONLINE_TTL = timedelta(days=30)

YOUDAO_JSONAPI_URL = 'https://dict.youdao.com/jsonapi?q={word}'
FREE_DICTIONARY_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'
USER_AGENT = 'family-learning/1.0 (online dictionary)'

_POS_PREFIX = re.compile(r'^(n|v|vt|vi|adj|adv|prep|pron|conj|num|art|int|aux|abbr|det)\.\s*(.+)$', re.IGNORECASE)
_DICTAPI_POS = {
    'noun': 'n.', 'verb': 'v.', 'adjective': 'adj.', 'adverb': 'adv.', 'pronoun': 'pron.',
    'preposition': 'prep.', 'conjunction': 'conj.', 'interjection': 'int.', 'article': 'art.',
    'numeral': 'num.', 'determiner': 'det.', 'exclamation': 'int.', 'auxiliary': 'aux.',
}


class OnlineDictionaryError(Exception):
    pass


@dataclass(frozen=True)
class OnlineLookup:
    result: DictionaryResult
    cache_hit: bool
    entry_id: str


def _get_json(url: str, timeout: float):
    try:
        with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=timeout) as response:
            return json.loads(response.read())
    except (OSError, ValueError) as error:
        raise OnlineDictionaryError('ONLINE_DICTIONARY_FETCH_FAILED') from error


def _youdao_entry(word: str, timeout: float) -> dict | None:
    """Return {'parts', 'alternatives', 'phonetic_uk', 'phonetic_us'} or None."""
    try:
        data = _get_json(YOUDAO_JSONAPI_URL.format(word=quote(word)), timeout)
    except OnlineDictionaryError:
        return None
    entries = ((data or {}).get('ec') or {}).get('word') or []
    if not entries:
        return None
    first = entries[0]
    parts: list[tuple[str, str]] = []
    alternatives: list[str] = []
    for group in first.get('trs') or []:
        for item in group.get('tr') or []:
            pos = (item.get('pos') or '').strip()
            lines = [line.strip() for line in (item.get('l', {}) or {}).get('i', []) if line and line.strip()]
            for line in lines:
                match = _POS_PREFIX.match(line)
                if match and not pos:
                    pos = match.group(1)
                    line = match.group(2).strip()
                if pos:
                    parts.append((f'{pos.lower()}.', line))
                else:
                    alternatives.append(line)
    if not parts and not alternatives:
        return None
    return {
        'parts': parts,
        'alternatives': alternatives,
        'phonetic_uk': first.get('ukphone') or None,
        'phonetic_us': first.get('usphone') or None,
    }


def _dictapi_entry(word: str, timeout: float) -> dict | None:
    """Return {'parts', 'definitions', 'examples', 'phonetic', 'phonetic_uk', 'phonetic_us'} or None."""
    try:
        data = _get_json(FREE_DICTIONARY_URL.format(word=quote(word)), timeout)
    except OnlineDictionaryError:
        return None
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    phonetics = first.get('phonetics') or []
    phonetic_uk = next((item.get('text') for item in phonetics if (item.get('audio') or '').endswith('-uk.mp3')), None)
    phonetic_us = next((item.get('text') for item in phonetics if (item.get('audio') or '').endswith('-us.mp3')), None)
    parts: list[tuple[str, str]] = []
    definitions: list[str] = []
    examples: list[DictionaryExample] = []
    for meaning in first.get('meanings') or []:
        part = _DICTAPI_POS.get(meaning.get('partOfSpeech') or '', f"{(meaning.get('partOfSpeech') or 'other')}.")
        for definition in meaning.get('definitions') or []:
            text = (definition.get('definition') or '').strip()
            if text:
                parts.append((part, text))
                definitions.append(text)
                example = (definition.get('example') or '').strip()
                if example:
                    examples.append(DictionaryExample(source=example, translation=''))
    if not parts:
        return None
    return {
        'parts': parts,
        'definitions': definitions,
        'examples': examples[:3],
        'phonetic': first.get('phonetic') or None,
        'phonetic_uk': phonetic_uk or None,
        'phonetic_us': phonetic_us or None,
    }


def lookup_english_word(text: str, timeout: float = 10) -> DictionaryResult:
    """Look up an English word online; raises when every source fails."""
    word = ' '.join(text.strip().split())
    youdao = _youdao_entry(word, timeout * 0.5)
    dictapi = _dictapi_entry(word, timeout * 0.5)
    if youdao is None and dictapi is None:
        raise OnlineDictionaryError('ONLINE_DICTIONARY_NOT_FOUND')

    if youdao is not None:
        parts = [PartOfSpeech(part=part, meaning=meaning) for part, meaning in youdao['parts'][:8]]
        alternatives = youdao['alternatives'][:8]
        primary = parts[0].meaning if parts else alternatives[0] if alternatives else word
        if not parts and alternatives and alternatives[0] == primary:
            alternatives = alternatives[1:]
        result_source = 'youdao'
        attribution = '在线词典 · 有道（公开接口）'
    else:
        parts = [PartOfSpeech(part=part, meaning=meaning) for part, meaning in dictapi['parts'][:8]]
        alternatives = dictapi['definitions'][1:9]
        primary = dictapi['definitions'][0]
        result_source = 'dictionaryapi'
        attribution = 'Free Dictionary API (Wiktionary)'

    if not alternatives and dictapi is not None:
        alternatives = [item for item in dictapi['definitions'] if item != primary][:8]
    usage_note = '\n'.join(dictapi['definitions']) if dictapi is not None and dictapi['definitions'] else None
    phonetic = (dictapi or {}).get('phonetic') or (youdao or {}).get('phonetic_us')
    return DictionaryResult(
        source_language='en', target_language='zh', item_type='word', source_text=word,
        primary_translation=primary, phonetic=phonetic or None,
        phonetic_uk=(dictapi or {}).get('phonetic_uk') or (youdao or {}).get('phonetic_uk'),
        phonetic_us=(dictapi or {}).get('phonetic_us') or (youdao or {}).get('phonetic_us'),
        word_tags=[], parts_of_speech=parts, alternatives=alternatives[:8],
        examples=(dictapi or {}).get('examples') or [], usage_note=usage_note,
        result_source=result_source, source_attribution=attribution,
    )


def _query_hash(text: str) -> str:
    normalized = normalize_learning_text(text, 'en')
    value = '\n'.join((normalized, 'en', 'zh', ONLINE_FINGERPRINT, ONLINE_FINGERPRINT))
    return sha256(value.encode()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def lookup_online_word(
    session: Session, child_id: str, text: str, owner_user_id: str | None = None,
) -> OnlineLookup | None:
    """Cached online lookup for English words; returns None when every source fails."""
    key = _query_hash(text)
    entry = session.scalar(select(DictionaryEntry).where(DictionaryEntry.query_hash == key))
    now = datetime.now(timezone.utc)
    fresh = entry is not None and (now - _as_utc(entry.created_at)) < ONLINE_TTL
    if fresh:
        entry.last_accessed_at = now
        entry.hit_count += 1
        existing_history = session.scalar(select(DictionaryHistory).where(
            DictionaryHistory.child_id == child_id,
            DictionaryHistory.entry_id == entry.id,
            DictionaryHistory.owner_user_id == owner_user_id,
        ))
        if existing_history is None:
            session.add(DictionaryHistory(child_id=child_id, entry_id=entry.id, owner_user_id=owner_user_id))
        session.commit()
        return OnlineLookup(result=DictionaryResult.model_validate_json(entry.result_json), cache_hit=True, entry_id=entry.id)
    try:
        result = lookup_english_word(text)
    except OnlineDictionaryError:
        return None
    if entry is None:
        entry = DictionaryEntry(query_hash=key, result_json=result.model_dump_json())
        session.add(entry)
        session.flush()
    else:
        entry.result_json = result.model_dump_json()
        entry.created_at = now
        entry.last_accessed_at = now
        entry.hit_count += 1
    existing_history = session.scalar(select(DictionaryHistory).where(
        DictionaryHistory.child_id == child_id,
        DictionaryHistory.entry_id == entry.id,
        DictionaryHistory.owner_user_id == owner_user_id,
    ))
    if existing_history is None:
        session.add(DictionaryHistory(child_id=child_id, entry_id=entry.id, owner_user_id=owner_user_id))
    session.commit()
    return OnlineLookup(result=result, cache_hit=False, entry_id=entry.id)
