"""DB-backed job queue. Claim is one atomic conditional UPDATE, so workers never double-process."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from clue.core.ids import utcnow
from clue.models import Job

MAX_ATTEMPTS = 2


def enqueue(db: Session, type: str, payload: dict, user_id: str | None = None, priority: int = 0, credit_ref: str | None = None) -> Job:
    job = Job(type=type, payload=payload, user_id=user_id, priority=priority, credit_ref=credit_ref)
    db.add(job)
    db.commit()
    return job


def claim(db: Session, worker_id: str, types: list[str] | None = None) -> Job | None:
    """Atomically claim the highest-priority, oldest queued job."""
    for _ in range(5):
        q = select(Job.id).where(Job.status == "queued")
        if types is not None:
            q = q.where(Job.type.in_(types))
        jid = db.scalar(q.order_by(Job.priority.desc(), Job.id).limit(1))
        if jid is None:
            return None
        res = db.execute(
            update(Job).where(Job.id == jid, Job.status == "queued")
            .values(status="running", locked_by=worker_id, locked_at=utcnow(), attempts=Job.attempts + 1)
        )
        db.commit()
        if res.rowcount == 1:
            return db.get(Job, jid)
    return None


def progress(db: Session, job_id: str, pct: int, stage: str = "") -> None:
    db.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(progress=pct, stage=stage))
    db.commit()


def finish(db: Session, job_id: str, result: dict) -> None:
    db.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(status="done", progress=100, result=result))
    db.commit()


def fail(db: Session, job_id: str, error: str, retry: bool = True) -> str:
    """Requeue if attempts remain (and retry is allowed), else mark failed. Returns the new status."""
    job = db.get(Job, job_id)
    status = "queued" if (retry and job.attempts < MAX_ATTEMPTS) else "failed"
    db.execute(update(Job).where(Job.id == job_id).values(status=status, error=error[:2000], locked_by=None))
    db.commit()
    return status


def cancel(db: Session, job_id: str) -> None:
    db.execute(update(Job).where(Job.id == job_id, Job.status.in_(["queued", "running"])).values(status="cancelled"))
    db.commit()
