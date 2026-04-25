"""
Model registration service.
Copies weight files into the models_registry and manages model metadata.
"""

import os
import shutil
import uuid

from sqlalchemy.orm import Session

from app.db import models
from app.services import storage_service


def register_model(
    db: Session,
    name: str,
    weights_file_path: str,
    config: dict = None,
    metrics: dict = None,
) -> models.MLModel:
    """
    Register a model by copying its weights file into the registry
    and creating a database record.
    """
    model_id = str(uuid.uuid4())
    dest_dir = storage_service.model_dir(model_id)
    dest_path = str(dest_dir / "weights.pt")

    # Copy weights file to registry
    if os.path.isfile(weights_file_path):
        shutil.copy2(weights_file_path, dest_path)
    else:
        raise FileNotFoundError(f"Weights file not found: {weights_file_path}")

    ml_model = models.MLModel(
        id=model_id,
        name=name,
        weights_path=dest_path,
        config=config or {},
        metrics=metrics or {},
    )
    db.add(ml_model)
    db.commit()
    db.refresh(ml_model)
    return ml_model


def register_model_upload(
    db: Session,
    name: str,
    weights_data: bytes,
    config: dict = None,
) -> models.MLModel:
    """
    Register a model from an uploaded file (bytes).
    """
    model_id = str(uuid.uuid4())
    dest_dir = storage_service.model_dir(model_id)
    dest_path = str(dest_dir / "weights.pt")

    with open(dest_path, "wb") as f:
        f.write(weights_data)

    ml_model = models.MLModel(
        id=model_id,
        name=name,
        weights_path=dest_path,
        config=config or {},
        metrics={},
    )
    db.add(ml_model)
    db.commit()
    db.refresh(ml_model)
    return ml_model
