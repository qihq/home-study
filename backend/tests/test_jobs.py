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


def test_renew_job_lease_keeps_active_job_owned_by_worker(session):
    from app.models.job import Job
    from app.services.jobs import renew_job_lease

    earlier = datetime.now(timezone.utc) - timedelta(minutes=4)
    job = Job(type='transcode_video', entity_id='r-active', status='running', locked_by='worker-a', locked_at=earlier)
    session.add(job)
    session.commit()

    renewed_at = datetime.now(timezone.utc)
    assert renew_job_lease(session, job.id, 'worker-a', renewed_at) is True
    session.refresh(job)

    assert job.locked_by == 'worker-a'
    assert job.locked_at == renewed_at.replace(tzinfo=None)


def test_renew_job_lease_does_not_take_job_from_another_worker(session):
    from app.models.job import Job
    from app.services.jobs import renew_job_lease

    locked_at = datetime.now(timezone.utc) - timedelta(minutes=4)
    job = Job(type='assemble_video', entity_id='r-other', status='running', locked_by='worker-b', locked_at=locked_at)
    session.add(job)
    session.commit()

    assert renew_job_lease(session, job.id, 'worker-a', datetime.now(timezone.utc)) is False
    session.refresh(job)
    assert job.locked_at == locked_at.replace(tzinfo=None)


def test_bootstrap_creates_only_one_default_child(session):
    from app.services.bootstrap import bootstrap_default_child

    first = bootstrap_default_child(session, '孩子', 'Asia/Shanghai')
    second = bootstrap_default_child(session, '孩子', 'Asia/Shanghai')

    assert first.id == second.id
