from datetime import datetime, timedelta, timezone


def test_claim_reclaims_expired_lease(session):
    from app.models.job import Job
    from app.services.jobs import claim_next_job

    now = datetime.now(timezone.utc)
    job = Job(type='transcode_video', entity_id='r1', status='running', locked_at=now - timedelta(minutes=6))
    session.add(job)
    session.commit()

    claimed = claim_next_job(session, 'worker-a', now)

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.locked_by == 'worker-a'
    assert claimed.attempts == 1


def test_bootstrap_creates_only_one_default_child(session):
    from app.services.bootstrap import bootstrap_default_child

    first = bootstrap_default_child(session, '孩子', 'Asia/Shanghai')
    second = bootstrap_default_child(session, '孩子', 'Asia/Shanghai')

    assert first.id == second.id
