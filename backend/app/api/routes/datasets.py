"""
Dataset endpoints: build & auto-export from GEE, sync from Drive, prepare patches.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models, schemas
from app.services import gee_service, storage_service, job_service, drive_service, dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/build", response_model=schemas.DatasetBuildResponse)
def build_dataset(payload: schemas.DatasetBuildRequest, db: Session = Depends(get_db)):
    """
    Create a dataset record, auto-submit the GEE export to Google Drive,
    and also save the JS script as fallback.
    """
    # Validate region
    region = db.query(models.Region).filter(models.Region.id == payload.region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Create dataset record
    ds = models.Dataset(
        region_id=payload.region_id,
        start_pre=payload.start_pre,
        end_pre=payload.end_pre,
        start_post=payload.start_post,
        end_post=payload.end_post,
        scale=payload.scale,
        patch_size=payload.patch_size,
        status="created",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    # Save JS script as fallback
    raw = storage_service.raw_dir(ds.id)
    script = gee_service.generate_gee_script(
        dataset_id=ds.id,
        geojson=region.geojson,
        start_pre=payload.start_pre,
        end_pre=payload.end_pre,
        start_post=payload.start_post,
        end_post=payload.end_post,
        scale=payload.scale,
    )
    script_path = str(raw / "gee_export.js")
    storage_service.write_text(script_path, script)
    ds.gee_script_path = script_path

    # Auto-submit GEE export via Python API
    job = job_service.create_job(db, job_type="gee_export")
    job_service.run_in_background(
        job.id,
        gee_service.submit_and_track,
        dataset_id=ds.id,
        geojson=region.geojson,
        start_pre=payload.start_pre,
        end_pre=payload.end_pre,
        start_post=payload.start_post,
        end_post=payload.end_post,
        scale=payload.scale,
    )

    ds.status = "exporting"
    db.commit()

    return schemas.DatasetBuildResponse(
        dataset_id=ds.id,
        gee_script_path=script_path,
    )


@router.get("", response_model=List[schemas.DatasetOut])
def list_datasets(db: Session = Depends(get_db)):
    """List all datasets."""
    return db.query(models.Dataset).all()


@router.get("/{dataset_id}", response_model=schemas.DatasetOut)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """Get a single dataset by ID."""
    ds = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


@router.post("/{dataset_id}/sync-drive", response_model=schemas.JobOut)
def sync_drive(dataset_id: str, db: Session = Depends(get_db)):
    """
    Start a background job to download GEE exports from Google Drive
    into the dataset's raw directory.
    """
    ds = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    job = job_service.create_job(db, job_type="sync_drive")
    dest = str(storage_service.raw_dir(dataset_id))

    job_service.run_in_background(
        job.id,
        drive_service.sync_drive_to_local,
        dataset_id=dataset_id,
        dest_dir=dest,
    )

    return job


@router.post("/{dataset_id}/prepare", response_model=schemas.JobOut)
def prepare_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """
    Start a background job to extract patches from raw GeoTIFFs
    and generate pseudo-labels for training.
    """
    ds = db.query(models.Dataset).filter(models.Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    job = job_service.create_job(db, job_type="prepare")

    job_service.run_in_background(
        job.id,
        dataset_service.prepare_dataset,
        dataset_id=dataset_id,
        patch_size=int(ds.patch_size),
    )

    return job
