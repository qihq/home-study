from typing import Literal

from pydantic import BaseModel, Field


class PartOfSpeech(BaseModel):
    part: str
    meaning: str


class DictionaryExample(BaseModel):
    source: str
    translation: str


class DictionaryResult(BaseModel):
    source_language: Literal['en', 'zh']
    target_language: Literal['en', 'zh']
    item_type: Literal['word', 'phrase', 'sentence']
    source_text: str
    primary_translation: str
    phonetic: str | None
    parts_of_speech: list[PartOfSpeech]
    alternatives: list[str] = Field(max_length=8)
    examples: list[DictionaryExample] = Field(max_length=5)
    usage_note: str | None
    result_source: Literal['ecdict', 'cc-cedict', 'ai'] = 'ai'
    source_attribution: str | None = None
