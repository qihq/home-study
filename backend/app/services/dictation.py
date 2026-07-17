import json
import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dictation import DictationResult, DictationSession
from app.models.word_list import WordItem


def start_dictation(
    session: Session,
    child_id: str,
    word_list_version_id: str,
    mode: str,
    random_source: random.Random,
    speaker_profile_id: str | None = None,
    voice_version_id: str | None = None,
    speaker_profile_name_snapshot: str | None = None,
    voice_version_name_snapshot: str | None = None,
) -> DictationSession:
    items = list(session.scalars(select(WordItem).where(
        WordItem.word_list_version_id == word_list_version_id
    ).order_by(WordItem.position)))
    ids = [item.id for item in items]
    if mode == 'random': random_source.shuffle(ids)
    record = DictationSession(
        child_id=child_id,
        word_list_version_id=word_list_version_id,
        mode=mode,
        ordered_item_ids_json=json.dumps(ids),
        speaker_profile_id=speaker_profile_id,
        voice_version_id=voice_version_id,
        speaker_profile_name_snapshot=speaker_profile_name_snapshot,
        voice_version_name_snapshot=voice_version_name_snapshot,
    )
    session.add(record); session.flush()
    item_types = {item.id: item.item_type for item in items}
    for sequence, item_id in enumerate(ids):
        session.add(DictationResult(
            session_id=record.id,
            word_item_id=item_id,
            sequence=sequence,
            item_type_snapshot=item_types[item_id],
        ))
    session.commit(); session.refresh(record)
    record.results = list(session.scalars(select(DictationResult).where(DictationResult.session_id == record.id).order_by(DictationResult.sequence)))
    return record


def score_result(session: Session, dictation_id: str, result_id: str, value: str) -> DictationResult:
    if value not in {'correct', 'incorrect', 'unscored'}: raise ValueError('INVALID_RESULT')
    result = session.get(DictationResult, result_id)
    if result is None or result.session_id != dictation_id: raise ValueError('RESULT_NOT_FOUND')
    result.result = value
    result.scored_at = datetime.now(timezone.utc) if value != 'unscored' else None
    session.commit(); session.refresh(result)
    return result
