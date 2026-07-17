from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recording import Recording


def _range(period: str, today: date) -> tuple[date, date]:
    if period == 'week':
        return today - timedelta(days=today.weekday()), today
    if period == 'month':
        return today.replace(day=1), today
    raise ValueError('INVALID_PERIOD')


def build_reading_stats(session: Session, child_id: str, period: str, today: date) -> dict:
    start, end = _range(period, today)
    available_days = (end - start).days + 1
    recordings = list(session.scalars(select(Recording).where(
        Recording.child_id == child_id,
        Recording.reading_date >= start,
        Recording.reading_date <= end,
        Recording.is_official.is_(True),
        Recording.source_validated_at.is_not(None),
        Recording.source_missing_at.is_(None),
    )))
    by_language = {}
    for language in ('chinese', 'english'):
        items = [item for item in recordings if item.language_type == language]
        by_language[language] = {
            'completed_days': len({item.reading_date for item in items}),
            'duration_ms': sum(item.verified_duration_ms or 0 for item in items),
            'rate': len({item.reading_date for item in items}) / available_days if available_days else 0,
        }
    completed_by_day = {
        day: {item.language_type for item in recordings if item.reading_date == day}
        for day in {item.reading_date for item in recordings}
    }
    calendar = []
    cursor = start
    while cursor <= end:
        languages = completed_by_day.get(cursor, set())
        calendar.append({'date': cursor.isoformat(), 'chinese': 'chinese' in languages, 'english': 'english' in languages})
        cursor += timedelta(days=1)
    dual_days = {day for day, languages in completed_by_day.items() if {'chinese', 'english'} <= languages}
    current_streak = 0
    cursor = end
    while cursor in dual_days:
        current_streak += 1
        cursor -= timedelta(days=1)
    longest_streak = 0
    running = 0
    for day in calendar:
        if day['chinese'] and day['english']:
            running += 1; longest_streak = max(longest_streak, running)
        else:
            running = 0
    completed_tasks = by_language['chinese']['completed_days'] + by_language['english']['completed_days']
    return {
        'period_start': start.isoformat(), 'period_end': end.isoformat(), 'available_days': available_days,
        'combined_rate': completed_tasks / (available_days * 2) if available_days else 0,
        'current_dual_streak': current_streak, 'longest_dual_streak': longest_streak,
        'calendar': calendar, **by_language,
    }
