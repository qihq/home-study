import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dictionary import DictionaryEntry
from app.models.unknown_item import UnknownItem
from app.services.learning_items import create_learning_list, normalize_learning_text


def mark_unknown(session: Session, child_id: str, dictionary_entry_id: str) -> UnknownItem:
    entry = session.get(DictionaryEntry, dictionary_entry_id)
    if entry is None:
        raise ValueError('DICTIONARY_ENTRY_NOT_FOUND')
    return mark_unknown_text(session, child_id, {**json.loads(entry.result_json), 'dictionary_entry_id': entry.id})


def mark_unknown_text(session: Session, child_id: str, item: dict) -> UnknownItem:
    source_language = item['source_language']
    normalized = normalize_learning_text(item['source_text'], source_language)
    existing = session.scalar(select(UnknownItem).where(
        UnknownItem.child_id == child_id,
        UnknownItem.source_language == source_language,
        UnknownItem.target_language == item['target_language'],
        UnknownItem.normalized_text == normalized,
        UnknownItem.status == 'unknown',
    ))
    if existing is not None:
        return existing
    unknown = UnknownItem(
        child_id=child_id,
        dictionary_entry_id=item.get('dictionary_entry_id'),
        item_type=item['item_type'],
        source_text=item['source_text'],
        normalized_text=normalized,
        source_language=source_language,
        target_language=item['target_language'],
        translation_text=item['translation_text'] if 'translation_text' in item else item['primary_translation'],
    )
    session.add(unknown)
    session.commit()
    session.refresh(unknown)
    return unknown


def update_unknown_status(session: Session, child_id: str, unknown_id: str, status: str) -> UnknownItem:
    if status not in {'unknown', 'mastered'}:
        raise ValueError('UNKNOWN_ITEM_STATUS_INVALID')
    unknown = session.get(UnknownItem, unknown_id)
    if unknown is None or unknown.child_id != child_id:
        raise ValueError('UNKNOWN_ITEM_NOT_FOUND')
    unknown.status = status
    unknown.mastered_at = datetime.now(timezone.utc) if status == 'mastered' else None
    session.commit()
    session.refresh(unknown)
    return unknown


def delete_unknown_item(session: Session, child_id: str, unknown_id: str) -> None:
    unknown = session.get(UnknownItem, unknown_id)
    if unknown is None or unknown.child_id != child_id:
        raise ValueError('UNKNOWN_ITEM_NOT_FOUND')
    session.delete(unknown)
    session.commit()


def count_active_unknown(session: Session, child_id: str, normalized_text: str) -> int:
    return len(list(session.scalars(select(UnknownItem).where(
        UnknownItem.child_id == child_id,
        UnknownItem.normalized_text == normalized_text,
        UnknownItem.status == 'unknown',
    ))))


def list_unknown_items(session: Session, child_id: str, status: str | None = None, item_type: str | None = None) -> list[UnknownItem]:
    statement = select(UnknownItem).where(UnknownItem.child_id == child_id)
    if status:
        statement = statement.where(UnknownItem.status == status)
    if item_type:
        statement = statement.where(UnknownItem.item_type == item_type)
    return list(session.scalars(statement.order_by(UnknownItem.marked_at.desc())))


def create_learning_list_from_unknown_items(session: Session, child_id: str, unknown_ids: list[str]):
    items_by_id = {
        item.id: item for item in session.scalars(select(UnknownItem).where(
            UnknownItem.child_id == child_id,
            UnknownItem.id.in_(unknown_ids),
        ))
    }
    selected = [items_by_id[item_id] for item_id in unknown_ids if item_id in items_by_id]
    if not selected:
        raise ValueError('NO_UNKNOWN_ITEMS_SELECTED')
    return create_learning_list(session, child_id, '生词复习', [
        {
            'display_text': item.source_text,
            'item_type': item.item_type,
            'source_language': item.source_language,
            'target_language': item.target_language,
            'translation_text': item.translation_text,
        }
        for item in selected
    ])
