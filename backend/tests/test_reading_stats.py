from datetime import date, datetime, timedelta


def add_official_recording(session, child_id: str, reading_date: date, language: str, status: str = 'ready'):
    from app.models.recording import Recording
    item = Recording(
        child_id=child_id,
        reading_date=reading_date,
        language_type=language,
        status=status,
        is_official=True,
        source_validated_at=datetime.now(),
        verified_duration_ms=60_000,
    )
    session.add(item)
    session.commit()


def test_current_month_excludes_future_days(session) -> None:
    from app.models.child import Child
    from app.services.reading_stats import build_reading_stats

    child = Child(display_name='孩子', slug='stats-child', created_at=datetime(2026, 7, 1))
    session.add(child); session.commit()

    stats = build_reading_stats(session, child.id, 'month', date(2026, 7, 12))

    assert stats['available_days'] == 12


def test_transcode_failure_still_counts_completed_source(session) -> None:
    from app.models.child import Child
    from app.services.reading_stats import build_reading_stats

    today = date(2026, 7, 12)
    child = Child(display_name='孩子', slug='stats-child')
    session.add(child); session.commit()
    add_official_recording(session, child.id, today, 'chinese', status='transcode_failed')

    stats = build_reading_stats(session, child.id, 'week', today)

    assert stats['chinese']['completed_days'] == 1
    assert stats['chinese']['duration_ms'] == 60_000


def test_stats_include_calendar_combined_rate_and_dual_language_streak(session) -> None:
    from app.models.child import Child
    from app.services.reading_stats import build_reading_stats

    today = date(2026, 7, 12)
    child = Child(display_name='孩子', slug='calendar-child', created_at=datetime(2026, 7, 1))
    session.add(child); session.commit()
    for day in (date(2026, 7, 10), date(2026, 7, 11), date(2026, 7, 12)):
        add_official_recording(session, child.id, day, 'chinese')
        add_official_recording(session, child.id, day, 'english')

    stats = build_reading_stats(session, child.id, 'month', today)

    assert stats['combined_rate'] == 6 / 24
    assert stats['current_dual_streak'] == 3
    assert stats['calendar'][-1] == {'date': '2026-07-12', 'chinese': True, 'english': True}
