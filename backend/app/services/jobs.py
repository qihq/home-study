from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.job import Job

LEASE_DURATION = timedelta(minutes=5)


def enqueue_once(session: Session, job_type: str, entity_id: str) -> Job:
    existing = session.scalar(select(Job).where(Job.type == job_type, Job.entity_id == entity_id, Job.status.in_(['queued', 'running'])))
    if existing is not None:
        return existing
    job = Job(type=job_type, entity_id=entity_id)
    session.add(job)
    return job


def claim_next_job(session: Session, worker_id: str, now: datetime) -> Job | None:
    expired_before = now - LEASE_DURATION
    statement = (
        select(Job)
        .where(
            or_(
                (Job.status == 'queued') & (Job.run_after <= now),
                (Job.status == 'running') & (Job.locked_at < expired_before),
            )
        )
        .order_by(Job.created_at)
        .limit(1)
    )
    job = session.scalar(statement)
    if job is None:
        return None
    job.status = 'running'
    job.locked_by = worker_id
    job.locked_at = now
    job.attempts += 1
    session.commit()
    session.refresh(job)
    return job
