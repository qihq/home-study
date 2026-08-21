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
    phonetic_uk: str | None = None
    phonetic_us: str | None = None
    word_tags: list[str] = Field(default_factory=list, max_length=10)
    parts_of_speech: list[PartOfSpeech]
    alternatives: list[str] = Field(max_length=8)
    examples: list[DictionaryExample] = Field(max_length=5)
    usage_note: str | None
    result_source: Literal['ecdict', 'cc-cedict', 'dictionaryapi', 'youdao', 'ai'] = 'ai'
    source_attribution: str | None = None
