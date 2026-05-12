"""
Training endpoint: start a local GPU training job.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import schemas
from app.services import job_service, training_service

router = APIRouter(prefix="/train", tags=["training"])


class TrainRequest(BaseModel):
    dataset_id: str
    model_name: str = "UNet-flood"
    epochs: int = 50
    batch_size: int = 8
    learning_rate: float = 1e-3
    base_filters: int = 32
    base_model_id: str = None


class TrainResponse(BaseModel):
    job_id: str
    message: str


@router.post("", response_model=TrainResponse)
def start_training(payload: TrainRequest, db: Session = Depends(get_db)):
    """
    Start a background training job on the local GPU (RTX 3050).
    
    Requires that dataset patches have been prepared first
    (POST /datasets/{id}/prepare).
    """
    job = job_service.create_job(db, job_type="train")

    job_service.run_in_background(
        job.id,
        training_service.train_model,
        dataset_id=payload.dataset_id,
        model_name=payload.model_name,
        epochs=payload.epochs,
        batch_size=payload.batch_size,
        learning_rate=payload.learning_rate,
        base_filters=payload.base_filters,
        base_model_id=payload.base_model_id,
    )

    return TrainResponse(
        job_id=job.id,
        message=f"Training started for dataset {payload.dataset_id} — "
                f"{payload.epochs} epochs on GPU",
    )
