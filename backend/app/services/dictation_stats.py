from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dictation import DictationResult, DictationSession
from app.models.dictionary import DictionaryEntry
from app.models.unknown_item import UnknownItem
from app.models.word_list import WordItem
from app.services.words import create_draft_word_list


def _scored_rows(session: Session, child_id: str):
    return session.execute(
        select(DictationResult, WordItem)
        .join(DictationSession, DictationSession.id == DictationResult.session_id)
        .join(WordItem, WordItem.id == DictationResult.word_item_id)
        .where(DictationSession.child_id == child_id, DictationResult.result.in_(['correct', 'incorrect']))
    ).all()


def build_dictation_stats(session: Session, child_id: str, reference_date: date | None = None) -> dict:
    daily: dict[str, dict[str, int]] = defaultdict(lambda: {'correct': 0, 'incorrect': 0})
    type_counts: dict[str, dict[str, int]] = defaultdict(lambda: {'correct': 0, 'incorrect': 0})
    for result, item in _scored_rows(session, child_id):
        day = result.scored_at.date().isoformat()
        daily[day][result.result] += 1
        type_counts[result.item_type_snapshot or item.item_type][result.result] += 1
    statistics = {
        'daily': [
            {'date': day, **counts, 'accuracy': counts['correct'] / (counts['correct'] + counts['incorrect'])}
            for day, counts in sorted(daily.items())
        ]
    }
    for item_type in ('word', 'phrase', 'sentence'):
        counts = type_counts[item_type]
        denominator = counts['correct'] + counts['incorrect']
        statistics[f'{item_type}_accuracy'] = counts['correct'] / denominator if denominator else None
    total_correct = sum(counts['correct'] for counts in daily.values())
    total_incorrect = sum(counts['incorrect'] for counts in daily.values())
    total_scored = total_correct + total_incorrect
    statistics['accuracy'] = total_correct / total_scored if total_scored else None
    today = reference_date or date.today()
    week_start = today - timedelta(days=today.weekday())
    starts_at = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    ends_at = starts_at + timedelta(days=7)
    statistics['unknown_items'] = {
        'added_this_week': session.scalar(select(func.count(UnknownItem.id)).where(UnknownItem.child_id == child_id, UnknownItem.marked_at >= starts_at, UnknownItem.marked_at < ends_at)) or 0,
        'mastered_this_week': session.scalar(select(func.count(UnknownItem.id)).where(UnknownItem.child_id == child_id, UnknownItem.mastered_at >= starts_at, UnknownItem.mastered_at < ends_at)) or 0,
    }
    statistics['dictionary_cache_hits'] = session.scalar(select(func.coalesce(func.sum(DictionaryEntry.hit_count), 0))) or 0
    return statistics


def build_mistakes(session: Session, child_id: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for result, item in _scored_rows(session, child_id):
        row = grouped.setdefault(item.normalized_text, {'word': item.display_text, 'normalized_text': item.normalized_text, 'incorrect_count': 0, 'correct_count': 0})
        row[f'{result.result}_count'] += 1
    return sorted(grouped.values(), key=lambda item: (-item['incorrect_count'], item['word']))


def create_review_list(session: Session, child_id: str, normalized_words: list[str]):
    available = {item['normalized_text']: item for item in build_mistakes(session, child_id)}
    selected = [
        {'display_text': available[word]['word'], 'normalized_text': word}
        for word in normalized_words if word in available
    ]
    if not selected:
        raise ValueError('NO_MISTAKES_SELECTED')
    return create_draft_word_list(session, child_id, '错词复习', selected)
