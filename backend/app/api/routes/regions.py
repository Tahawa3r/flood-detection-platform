"""
Region CRUD endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models, schemas

router = APIRouter(prefix="/regions", tags=["regions"])


@router.post("", response_model=schemas.RegionOut)
def create_region(payload: schemas.RegionCreate, db: Session = Depends(get_db)):
    """Create a new geographic region."""
    region = models.Region(name=payload.name, geojson=payload.geojson)
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


@router.get("", response_model=List[schemas.RegionOut])
def list_regions(db: Session = Depends(get_db)):
    """List all registered regions."""
    return db.query(models.Region).all()


@router.get("/{region_id}", response_model=schemas.RegionOut)
def get_region(region_id: str, db: Session = Depends(get_db)):
    """Get a single region by ID."""
    region = db.query(models.Region).filter(models.Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return region
