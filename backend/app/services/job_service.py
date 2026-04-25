"""
Background job execution and tracking service.
Uses a thread pool to run long-running tasks without blocking the API.
"""

import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models


# Thread pool for background tasks
_executor = ThreadPoolExecutor(max_workers=4)


def create_job(db: Session, job_type: str) -> models.Job:
    """Create a new job record in the database."""
    job = models.Job(
        id=str(uuid.uuid4()),
        type=job_type,
        status="pending",
        progress=0.0,
        logs="",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(job_id: str, status: str = None, progress: float = None,
               log_line: str = None, error: str = None):
    """Update job status from a background thread (uses its own session)."""
    db = SessionLocal()
    try:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job:
            return
        if status:
            job.status = status
        if progress is not None:
            job.progress = progress
        if log_line:
            job.logs = (job.logs or "") + log_line + "\n"
        if error:
            job.error = error
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def run_in_background(job_id: str, fn: Callable, *args, **kwargs):
    """Submit a function to run in the thread pool.
    
    The function receives `job_id` as its first argument so it can
    call `update_job` to report progress.
    """
    def _wrapper():
        try:
            update_job(job_id, status="running", progress=0.0,
                       log_line="Job started")
            fn(job_id, *args, **kwargs)
            update_job(job_id, status="completed", progress=100.0,
                       log_line="Job completed successfully")
        except Exception as exc:
            update_job(job_id, status="failed", error=str(exc),
                       log_line=f"Job failed: {exc}")

    _executor.submit(_wrapper)
