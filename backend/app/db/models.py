"""
SQLAlchemy ORM models for the flood detection platform.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Region(Base):
    __tablename__ = "regions"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    geojson = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    datasets = relationship("Dataset", back_populates="region")
    predictions = relationship("Prediction", back_populates="region")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=_uuid)
    region_id = Column(String, ForeignKey("regions.id"), nullable=False)
    start_pre = Column(String, nullable=False)
    end_pre = Column(String, nullable=False)
    start_post = Column(String, nullable=False)
    end_post = Column(String, nullable=False)
    scale = Column(Float, default=100)
    patch_size = Column(Float, default=256)
    status = Column(String, default="created")  # created | script_ready | synced | prepared
    gee_script_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    region = relationship("Region", back_populates="datasets")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False)       # sync_drive | prepare | predict
    status = Column(String, default="pending")  # pending | running | completed | failed
    progress = Column(Float, default=0.0)
    logs = Column(Text, default="")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    weights_path = Column(String, nullable=True)
    config = Column(JSON, default=dict)
    metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    predictions = relationship("Prediction", back_populates="model")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String, primary_key=True, default=_uuid)
    model_id = Column(String, ForeignKey("ml_models.id"), nullable=False)
    region_id = Column(String, ForeignKey("regions.id"), nullable=False)
    dataset_id = Column(String, nullable=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True)
    start_pre = Column(String, nullable=True)
    end_pre = Column(String, nullable=True)
    start_post = Column(String, nullable=True)
    end_post = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending | running | completed | failed
    created_at = Column(DateTime, default=_utcnow)

    model = relationship("MLModel", back_populates="predictions")
    region = relationship("Region", back_populates="predictions")
