"""
Prediction orchestration service.
Loads a registered model, runs tile-based inference on a raster,
and saves the output mask, overlay, and metadata.
"""

import os
import json
import glob

from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import SessionLocal
from app.services import storage_service
from app.services.job_service import update_job
from app.services.gee_service import generate_inference_script


def run_prediction(
    job_id: str,
    prediction_id: str,
    model_id: str,
    region_id: str,
    dataset_id: str = None,
    start_pre: str = None,
    end_pre: str = None,
    start_post: str = None,
    end_post: str = None,
):
    """
    Background task: run flood prediction using a registered model.
    
    1. Locate the input raster (from dataset or generate a GEE script).
    2. Load the model weights.
    3. Run tile-based inference.
    4. Save mask.tif, overlay.png, meta.json.
    """
    db = SessionLocal()
    try:
        # Fetch model info
        ml_model = db.query(db_models.MLModel).filter(
            db_models.MLModel.id == model_id
        ).first()
        if not ml_model:
            raise ValueError(f"Model {model_id} not found")

        region = db.query(db_models.Region).filter(
            db_models.Region.id == region_id
        ).first()
        if not region:
            raise ValueError(f"Region {region_id} not found")

        out_dir = storage_service.predictions_dir(prediction_id)
        update_job(job_id, log_line=f"Output directory: {out_dir}", progress=5.0)

        # Find input raster
        raster_path = None
        if dataset_id:
            raw = storage_service.raw_dir(dataset_id)
            tifs = glob.glob(str(raw / "*.tif"))
            if tifs:
                raster_path = tifs[0]

        if raster_path is None:
            # No local raster — generate a GEE script
            update_job(job_id, log_line="No local raster found, generating GEE script...")
            script = generate_inference_script(
                prediction_id=prediction_id,
                geojson=region.geojson,
                start_pre=start_pre or "",
                end_pre=end_pre or "",
                start_post=start_post or "",
                end_post=end_post or "",
            )
            script_path = str(out_dir / "gee_inference.js")
            storage_service.write_text(script_path, script)
            update_job(
                job_id,
                log_line=f"GEE script saved to {script_path}. "
                         "Run it in the Code Editor, export, sync, then re-run prediction.",
            )
            # Update prediction status
            pred = db.query(db_models.Prediction).filter(
                db_models.Prediction.id == prediction_id
            ).first()
            if pred:
                pred.status = "awaiting_data"
                db.commit()
            return

        update_job(job_id, log_line=f"Using raster: {raster_path}", progress=10.0)

        # Run inference
        try:
            from app.ml.inference.run import run_inference
            from app.ml.utils.geo import compute_flood_stats, create_overlay_png

            mask_path = str(out_dir / "mask.tif")
            update_job(job_id, log_line="Loading model and running inference...", progress=20.0)

            run_inference(
                raster_path=raster_path,
                weights_path=ml_model.weights_path,
                output_path=mask_path,
                model_config=ml_model.config,
                job_id=job_id,
            )

            update_job(job_id, log_line="Computing flood statistics...", progress=85.0)
            stats = compute_flood_stats(mask_path)
            
            update_job(job_id, log_line="Extracting flooded place names...", progress=88.0)
            from app.ml.utils.geo import extract_flood_locations
            flooded_places = extract_flood_locations(mask_path, max_locations=5)

            update_job(job_id, log_line="Creating overlay image...", progress=90.0)
            overlay_path = str(out_dir / "overlay.png")
            create_overlay_png(raster_path, mask_path, overlay_path)

            # Save metadata
            meta = {
                "prediction_id": prediction_id,
                "model_id": model_id,
                "region_id": region_id,
                "dataset_id": dataset_id,
                "raster_path": raster_path,
                "stats": stats,
                "locations_flooded": flooded_places,
            }
            storage_service.write_json(str(out_dir / "meta.json"), meta)
            
            # --- Auto-Cleanup ---
            import shutil
            if dataset_id:
                raw_dir_path = storage_service.raw_dir(dataset_id)
                if raw_dir_path.exists():
                    update_job(job_id, log_line="Auto-cleanup: Deleting raw dataset files to save space.", progress=95.0)
                    shutil.rmtree(raw_dir_path, ignore_errors=True)
            # --------------------

            update_job(job_id, log_line="Prediction complete", progress=100.0)

        except ImportError as exc:
            update_job(
                job_id,
                log_line=f"ML dependencies not available: {exc}. "
                         "Install torch and rasterio for inference.",
            )
            raise

        # Update prediction status
        pred = db.query(db_models.Prediction).filter(
            db_models.Prediction.id == prediction_id
        ).first()
        if pred:
            pred.status = "completed"
            db.commit()

    finally:
        db.close()
