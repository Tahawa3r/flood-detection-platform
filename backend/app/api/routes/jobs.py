"""
Job monitoring endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models, schemas

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=List[schemas.JobOut])
def list_jobs(db: Session = Depends(get_db)):
    """List all jobs, most recent first."""
    return db.query(models.Job).order_by(models.Job.created_at.desc()).all()


@router.get("/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get a single job by ID."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/logs", response_model=schemas.JobLogsOut)
def get_job_logs(job_id: str, db: Session = Depends(get_db)):
    """Get the log output of a job."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return schemas.JobLogsOut(id=job.id, logs=job.logs or "")
