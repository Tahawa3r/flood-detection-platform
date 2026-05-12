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
    config: Optional[Dict[str, Any]] = {}
    metrics: Optional[Dict[str, Any]] = {}
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Coerce None -> {} for config and metrics
        if hasattr(obj, 'config') and obj.config is None:
            obj.config = {}
        if hasattr(obj, 'metrics') and obj.metrics is None:
            obj.metrics = {}
        return super().model_validate(obj, *args, **kwargs)


# ─── Prediction ───────────────────────────────────────────────────────

class PredictionCreate(BaseModel):
    model_id: str
    region_id: str
    region_geojson: Optional[Dict[str, Any]] = None
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
    data_source: Optional[str] = None
    result_version: Optional[int] = None
    start_pre: Optional[str] = None
    end_pre: Optional[str] = None
    start_post: Optional[str] = None
    end_post: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PredictionCreateResponse(BaseModel):
    prediction_id: str
    job_id: str
    status: Optional[str] = None
    message: Optional[str] = None
    risk_assessment: Optional[Dict[str, Any]] = None
