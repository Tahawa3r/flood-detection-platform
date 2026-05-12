"""
FastAPI application entry point.
Registers all routers, configures CORS, and creates DB tables on startup.
"""

import logging
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import engine, Base

# Import all models so they are registered with Base.metadata
from app.db import models  # noqa: F401

from app.api.routes import health, regions, datasets, jobs, models as models_router, predict, train


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Flood Detection & Risk Platform",
    description="Backend API for satellite-based flood detection using Sentinel-1 + U-Net.",
    version="0.1.0",
)

# CORS - explicit origins required when allow_credentials=True
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(regions.router)
app.include_router(datasets.router)
app.include_router(jobs.router)
app.include_router(models_router.router)
app.include_router(predict.router)
app.include_router(train.router)


@app.on_event("startup")
async def startup_event():
    """Preload cache on server startup for faster predictions."""
    from app.services.predict_service import get_cache_dir

    cache_dir = get_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    logger.info("Server started")
    logger.info("Cache directory ready: %s", cache_dir)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=False)

