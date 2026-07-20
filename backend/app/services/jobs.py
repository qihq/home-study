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


def renew_job_lease(session: Session, job_id: str, worker_id: str, now: datetime) -> bool:
    job = session.get(Job, job_id)
    if job is None or job.status != 'running' or job.locked_by != worker_id:
        return False
    job.locked_at = now
    session.commit()
    return True


def reset_failed_job(session: Session, job_type: str, entity_id: str, now: datetime | None = None) -> Job:
    job = session.scalar(select(Job).where(
        Job.type == job_type,
        Job.entity_id == entity_id,
        Job.status.in_(['failed', 'superseded']),
    ).order_by(Job.created_at.desc()))
    if job is None:
        job = enqueue_once(session, job_type, entity_id)
    job.status = 'queued'
    job.attempts = 0
    job.progress = 0
    job.run_after = now or datetime.now().astimezone()
    job.locked_by = None
    job.locked_at = None
    job.error_code = None
    job.error_detail = None
    return job
