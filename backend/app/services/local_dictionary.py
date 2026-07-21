import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.schemas.dictionary import DictionaryResult, PartOfSpeech


POS_PREFIX = re.compile(r'^(n|v|vt|vi|adj|adv|prep|pron|conj|num|art|int|aux|abbr)\.\s*(.+)$', re.IGNORECASE)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


@dataclass(frozen=True)
class LocalLookup:
    result: DictionaryResult
    source: Literal['ecdict', 'cc-cedict']


class LocalDictionary:
    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def available(self) -> bool:
        return self.path.is_file()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f'file:{self.path.as_posix()}?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    @property
    def fingerprint(self) -> str:
        if not self.available:
            return 'local:unavailable'
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = 'version'").fetchone()
        return f"local:{row['value'] if row else 'unknown'}"

    def lookup(self, text: str, source_language: Literal['en', 'zh']) -> LocalLookup | None:
        if not self.available:
            return None
        normalized = re.sub(r'\s+', ' ', text).strip()
        if not normalized:
            return None
        return self._lookup_english(normalized) if source_language == 'en' else self._lookup_chinese(normalized)

    def _lookup_english(self, text: str) -> LocalLookup | None:
        word = text.casefold()
        with self._connect() as connection:
            row = connection.execute('SELECT * FROM ecdict WHERE word = ? COLLATE NOCASE', (word,)).fetchone()
            if row is None:
                alias = connection.execute('SELECT word FROM ecdict_aliases WHERE alias = ? COLLATE NOCASE', (word,)).fetchone()
                if alias is not None:
                    row = connection.execute('SELECT * FROM ecdict WHERE word = ?', (alias['word'],)).fetchone()
        if row is None:
            return None
        translations = _unique([line.strip() for line in (row['translation'] or '').replace('\\n', '\n').splitlines()])
        definitions = _unique([line.strip() for line in (row['definition'] or '').replace('\\n', '\n').splitlines()])
        parts: list[PartOfSpeech] = []
        alternatives: list[str] = []
        for translation in translations:
            match = POS_PREFIX.match(translation)
            if match:
                parts.append(PartOfSpeech(part=f'{match.group(1).lower()}.', meaning=match.group(2).strip()))
            else:
                alternatives.append(translation)
        primary = parts[0].meaning if parts else alternatives[0] if alternatives else definitions[0] if definitions else row['word']
        if not parts and alternatives and alternatives[0] == primary:
            alternatives = alternatives[1:]
        return LocalLookup(result=DictionaryResult(
            source_language='en', target_language='zh', item_type='word', source_text=row['word'],
            primary_translation=primary, phonetic=row['phonetic'] or None, parts_of_speech=parts,
            alternatives=alternatives[:8], examples=[], usage_note='\n'.join(definitions) if definitions else None,
        ), source='ecdict')

    def _lookup_chinese(self, text: str) -> LocalLookup | None:
        with self._connect() as connection:
            rows = connection.execute(
                'SELECT * FROM cedict WHERE simplified = ? OR traditional = ? ORDER BY CASE WHEN substr(pinyin, 1, 1) = lower(substr(pinyin, 1, 1)) THEN 0 ELSE 1 END, rowid',
                (text, text),
            ).fetchall()
        if not rows:
            return None
        row = rows[0]
        definitions = []
        for entry in rows:
            definitions.extend(item.strip() for item in (entry['definitions'] or '').split('/') if item.strip() and item.strip() not in definitions)
        primary = definitions[0] if definitions else row['simplified']
        return LocalLookup(result=DictionaryResult(
            source_language='zh', target_language='en', item_type='word', source_text=row['simplified'],
            primary_translation=primary, phonetic=row['pinyin'] or None, parts_of_speech=[],
            alternatives=definitions[1:9], examples=[], usage_note=None,
        ), source='cc-cedict')
