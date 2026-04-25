"""
FastAPI application entry point.
Registers all routers, configures CORS, and creates DB tables on startup.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import engine, Base

# Import all models so they are registered with Base.metadata
from app.db import models  # noqa: F401

from app.api.routes import health, regions, datasets, jobs, models as models_router, predict, train

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Flood Detection & Risk Platform",
    description="Backend API for satellite-based flood detection using Sentinel-1 + U-Net.",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
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
