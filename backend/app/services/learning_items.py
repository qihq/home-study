import re
import unicodedata
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning_item import LearningItem, LearningList, LearningListVersion
from app.services.jobs import enqueue_once
from app.services.tts_config import get_tts_config
from app.models.speaker import VoiceVersion
from app.models.tts_asset import TtsAsset
from app.services.tts import tts_cache_key

ItemType = Literal['word', 'phrase', 'sentence']


def normalize_learning_text(text: str, source_language: str) -> str:
    normalized = ' '.join(unicodedata.normalize('NFKC', text).strip().split())
    return normalized.casefold() if source_language == 'en' else normalized


def infer_item_type(text: str, source_language: str) -> ItemType:
    normalized = normalize_learning_text(text, source_language)
    if source_language != 'en':
        return 'sentence'

    tokens = normalized.split()
    if len(tokens) == 1 and any(character.isalpha() for character in tokens[0]):
        return 'word'
    if 2 <= len(tokens) <= 5 and not re.search(r'[.!?。！？]$', normalized):
        return 'phrase'
    return 'sentence'


def create_learning_list(
    session: Session, child_id: str, title: str, items: list[dict[str, str]]
) -> LearningList:
    learning_list = LearningList(child_id=child_id, title=title)
    session.add(learning_list)
    session.flush()
    draft = LearningListVersion(word_list_id=learning_list.id, version=0)
    session.add(draft)
    session.flush()
    for position, item in enumerate(items):
        source_language = item.get('source_language', 'en')
        display_text = item['display_text']
        session.add(LearningItem(
            word_list_version_id=draft.id,
            position=position,
            item_type=item.get('item_type') or infer_item_type(display_text, source_language),
            display_text=display_text,
            normalized_text=item.get('normalized_text') or normalize_learning_text(display_text, source_language),
            source_language=source_language,
            target_language=item.get('target_language', 'zh' if source_language == 'en' else 'en'),
            translation_text=item.get('translation_text'),
        ))
    session.commit()
    session.refresh(learning_list)
    return learning_list


def confirm_learning_list(session: Session, list_id: str) -> LearningListVersion:
    learning_list = session.get(LearningList, list_id)
    if learning_list is None:
        raise ValueError('LEARNING_LIST_NOT_FOUND')
    if learning_list.status == 'confirmed':
        return session.scalar(select(LearningListVersion).where(
            LearningListVersion.word_list_id == learning_list.id,
            LearningListVersion.version == learning_list.current_version,
        ))

    draft = session.scalar(select(LearningListVersion).where(
        LearningListVersion.word_list_id == learning_list.id,
        LearningListVersion.version == 0,
    ))
    if draft is None:
        raise ValueError('LEARNING_LIST_DRAFT_NOT_FOUND')
    version = LearningListVersion(word_list_id=learning_list.id, version=1)
    session.add(version)
    session.flush()
    for item in session.scalars(select(LearningItem).where(
        LearningItem.word_list_version_id == draft.id
    ).order_by(LearningItem.position)):
        confirmed_item = LearningItem(
            word_list_version_id=version.id,
            position=item.position,
            item_type=item.item_type,
            display_text=item.display_text,
            normalized_text=item.normalized_text,
            source_language=item.source_language,
            target_language=item.target_language,
            translation_text=item.translation_text,
            dictionary_entry_id=item.dictionary_entry_id,
            source_location=item.source_location,
            warning_json=item.warning_json,
        )
        session.add(confirmed_item)
        session.flush()
        config = get_tts_config(session)
        custom_ready = config is not None and config.pronunciation_source == 'custom' and session.get(VoiceVersion, config.voice_version_id) is not None
        if item.source_language == 'en' and config is not None and (config.api_key_encrypted or custom_ready):
            enqueue_once(session, 'generate_tts', confirmed_item.id)
    learning_list.status = 'confirmed'
    learning_list.current_version = 1
    learning_list.confirmed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(version)
    version.items = list(session.scalars(select(LearningItem).where(
        LearningItem.word_list_version_id == version.id
    ).order_by(LearningItem.position)))
    return version


def enqueue_missing_tts_for_confirmed_items(session: Session) -> int:
    """Queue local audio generation for English items created before TTS was configured."""
    config = get_tts_config(session)
    custom_ready = config is not None and config.pronunciation_source == 'custom' and session.get(VoiceVersion, config.voice_version_id) is not None
    if config is None or (not config.api_key_encrypted and not custom_ready):
        return 0
    items = session.scalars(select(LearningItem).join(
        LearningListVersion, LearningItem.word_list_version_id == LearningListVersion.id,
    ).join(
        LearningList, LearningListVersion.word_list_id == LearningList.id,
    ).where(
        LearningList.status == 'confirmed',
        LearningListVersion.version == LearningList.current_version,
        LearningItem.source_language == 'en',
    )).all()
    queued = 0
    for item in items:
        source = item.pronunciation_source if item.pronunciation_source != 'default' else config.pronunciation_source
        expected_key = tts_cache_key(item.display_text, 'en-US', config.protocol, config.base_url, config.model, config.voice, config.speed) if source != 'custom' else None
        asset = session.get(TtsAsset, item.tts_asset_id) if item.tts_asset_id else None
        if asset is not None and (expected_key is None or asset.cache_key == expected_key):
            continue
        item.tts_asset_id = None
        enqueue_once(session, 'generate_tts', item.id)
        queued += 1
    session.commit()
    return queued


def replace_confirmed_learning_list(session: Session, list_id: str, title: str, items: list[dict[str, str]]) -> LearningListVersion:
    learning_list = session.get(LearningList, list_id)
    if learning_list is None:
        raise ValueError('LEARNING_LIST_NOT_FOUND')
    learning_list.title = title
    next_version = (learning_list.current_version or 0) + 1
    version = LearningListVersion(word_list_id=learning_list.id, version=next_version)
    session.add(version)
    session.flush()
    config = get_tts_config(session)
    for position, item in enumerate(items):
        display_text = item['display_text']
        learning_item = LearningItem(
            word_list_version_id=version.id, position=position, display_text=display_text,
            normalized_text=item.get('normalized_text') or normalize_learning_text(display_text, 'en'),
            source_language='en', target_language='zh',
            item_type=item.get('item_type') or infer_item_type(display_text, 'en'),
        )
        session.add(learning_item)
        session.flush()
        custom_ready = config is not None and config.pronunciation_source == 'custom' and session.get(VoiceVersion, config.voice_version_id) is not None
        if config is not None and (config.api_key_encrypted or custom_ready):
            enqueue_once(session, 'generate_tts', learning_item.id)
    learning_list.current_version = next_version
    learning_list.status = 'confirmed'
    learning_list.confirmed_at = datetime.now(timezone.utc)
    session.commit()
    return version
