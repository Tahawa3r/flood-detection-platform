"""
Pydantic schemas for API request / response validation.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


# ─── Region ───────────────────────────────────────────────────────────

class RegionCreate(BaseModel):
    name: str
    geojson: Dict[str, Any]


class RegionOut(BaseModel):
    id: str
    name: str
    geojson: Dict[str, Any]
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Dataset ──────────────────────────────────────────────────────────

class DatasetBuildRequest(BaseModel):
    region_id: str
    start_pre: str
    end_pre: str
    start_post: str
    end_post: str
    scale: float = 100
    patch_size: int = 256


class DatasetOut(BaseModel):
    id: str
    region_id: str
    start_pre: str
    end_pre: str
    start_post: str
    end_post: str
    scale: float
    patch_size: float
    status: str
    gee_script_path: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DatasetBuildResponse(BaseModel):
    dataset_id: str
    gee_script_path: str


# ─── Job ──────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: str
    type: str
    status: str
    progress: float
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobLogsOut(BaseModel):
    id: str
    logs: str


# ─── ML Model ────────────────────────────────────────────────────────

class ModelRegisterRequest(BaseModel):
    name: str
    weights_file_path: str
    config: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}


class ModelOut(BaseModel):
    id: str
    name: str
    weights_path: Optional[str] = None
    config: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Prediction ───────────────────────────────────────────────────────

class PredictionCreate(BaseModel):
    model_id: str
    region_id: str
    start_pre: Optional[str] = None
    end_pre: Optional[str] = None
    start_post: Optional[str] = None
    end_post: Optional[str] = None
    dataset_id: Optional[str] = None


class PredictionOut(BaseModel):
    id: str
    model_id: str
    region_id: str
    dataset_id: Optional[str] = None
    job_id: Optional[str] = None
    status: str
    start_pre: Optional[str] = None
    end_pre: Optional[str] = None
    start_post: Optional[str] = None
    end_post: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PredictionCreateResponse(BaseModel):
    prediction_id: str
    job_id: str
