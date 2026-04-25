"""
Prediction endpoints: create, list, get, serve output files.
"""

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models, schemas
from app.services import job_service, predict_service, storage_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("", response_model=schemas.PredictionCreateResponse)
def create_prediction(payload: schemas.PredictionCreate, db: Session = Depends(get_db)):
    """Start a new flood prediction job."""
    # Validate model
    ml_model = db.query(models.MLModel).filter(models.MLModel.id == payload.model_id).first()
    if not ml_model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Validate region
    region = db.query(models.Region).filter(models.Region.id == payload.region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Create job
    job = job_service.create_job(db, job_type="predict")

    # Create prediction record
    prediction = models.Prediction(
        model_id=payload.model_id,
        region_id=payload.region_id,
        dataset_id=payload.dataset_id,
        job_id=job.id,
        start_pre=payload.start_pre,
        end_pre=payload.end_pre,
        start_post=payload.start_post,
        end_post=payload.end_post,
        status="running",
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    # Run prediction in background
    job_service.run_in_background(
        job.id,
        predict_service.run_prediction,
        prediction_id=prediction.id,
        model_id=payload.model_id,
        region_id=payload.region_id,
        dataset_id=payload.dataset_id,
        start_pre=payload.start_pre,
        end_pre=payload.end_pre,
        start_post=payload.start_post,
        end_post=payload.end_post,
    )

    return schemas.PredictionCreateResponse(
        prediction_id=prediction.id,
        job_id=job.id,
    )


@router.get("", response_model=List[schemas.PredictionOut])
def list_predictions(db: Session = Depends(get_db)):
    """List all predictions."""
    return db.query(models.Prediction).order_by(models.Prediction.created_at.desc()).all()


@router.get("/{prediction_id}", response_model=schemas.PredictionOut)
def get_prediction(prediction_id: str, db: Session = Depends(get_db)):
    """Get a single prediction by ID."""
    pred = db.query(models.Prediction).filter(
        models.Prediction.id == prediction_id
    ).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return pred


@router.get("/{prediction_id}/overlay.png")
def get_overlay(prediction_id: str):
    """Serve the overlay PNG image for a prediction."""
    out_dir = storage_service.predictions_dir(prediction_id)
    path = str(out_dir / "overlay.png")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Overlay not found")
    return FileResponse(path, media_type="image/png")


@router.get("/{prediction_id}/mask.tif")
def get_mask(prediction_id: str):
    """Serve the binary mask GeoTIFF for a prediction."""
    out_dir = storage_service.predictions_dir(prediction_id)
    path = str(out_dir / "mask.tif")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Mask not found")
    return FileResponse(path, media_type="image/tiff")


@router.get("/{prediction_id}/meta.json")
def get_meta(prediction_id: str):
    """Serve the metadata JSON for a prediction."""
    out_dir = storage_service.predictions_dir(prediction_id)
    path = str(out_dir / "meta.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Metadata not found")
    data = storage_service.read_json(path)
    return JSONResponse(content=data)
