"""
ML model registration and listing endpoints.
"""

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models, schemas
from app.services import model_service

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/register", response_model=schemas.ModelOut)
def register_model(payload: schemas.ModelRegisterRequest, db: Session = Depends(get_db)):
    """Register a model from a local weights file path."""
    try:
        ml_model = model_service.register_model(
            db=db,
            name=payload.name,
            weights_file_path=payload.weights_file_path,
            config=payload.config,
            metrics=payload.metrics,
        )
        return ml_model
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/upload", response_model=schemas.ModelOut)
async def upload_model(
    name: str = Form(...),
    config_json: str = Form("{}"),
    weights: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload model weights as a multipart form."""
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid config_json")

    data = await weights.read()
    ml_model = model_service.register_model_upload(
        db=db,
        name=name,
        weights_data=data,
        config=config,
    )
    return ml_model


@router.get("", response_model=List[schemas.ModelOut])
def list_models(db: Session = Depends(get_db)):
    """List all registered models."""
    return db.query(models.MLModel).all()


@router.get("/{model_id}", response_model=schemas.ModelOut)
def get_model(model_id: str, db: Session = Depends(get_db)):
    """Get a single model by ID."""
    ml_model = db.query(models.MLModel).filter(models.MLModel.id == model_id).first()
    if not ml_model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ml_model
