"""
Prediction orchestration service.
Loads a registered model, resolves the best available raster,
and saves mask, overlay, and metadata for a prediction.
"""

import glob
import hashlib
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Optional

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.core.config import settings
from app.db import models as db_models
from app.db.database import SessionLocal
from app.services import gee_service, storage_service, report_service
from app.services.job_service import update_job


logger = logging.getLogger(__name__)
FETCH_RETRY_INTERVAL_SECONDS = 2
FETCH_RETRY_ATTEMPTS = 15
FAST_FALLBACK_ATTEMPTS = 1
UPGRADE_RETRY_ATTEMPTS = 20


def get_cache_key(region_id: str, start_pre: str, end_pre: str, start_post: str, end_post: str) -> str:
    """Generate unique cache key based on region and date parameters."""
    key_string = f"{region_id}_{start_pre}_{end_pre}_{start_post}_{end_post}"
    return hashlib.md5(key_string.encode("utf-8")).hexdigest()


def get_cache_dir() -> str:
    """Get the cache directory for downloaded datasets."""
    cache_dir = os.path.join(settings.data_dir_path, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_fallback_dataset_path() -> str:
    """Return the validated fallback GeoTIFF path."""
    fallback_path = os.path.join(settings.data_dir_path, "fallback", "default_flood_data.tif")
    if not os.path.isfile(fallback_path):
        raise FileNotFoundError(f"Fallback dataset not found: {fallback_path}")
    validate_raster(fallback_path)
    return fallback_path


def resolve_weights_path(weights_path: str) -> str:
    """Resolve model weights path relative to the backend root if needed."""
    path = Path(weights_path)
    if path.is_absolute():
        return str(path)
    return str((BACKEND_DIR / path).resolve())


def validate_raster(raster_path: str) -> str:
    """Validate that a raster exists and is readable by rasterio."""
    import rasterio

    if not os.path.isfile(raster_path):
        raise FileNotFoundError(f"Raster not found: {raster_path}")
    with rasterio.open(raster_path) as src:
        if src.count < 1 or src.width < 1 or src.height < 1:
            raise ValueError(f"Invalid raster dimensions for {raster_path}")
    return raster_path


def set_prediction_state(prediction_id: str, **fields) -> None:
    """Update prediction fields in a short-lived session with row-level lock.
    
    STRICT STATE RULES:
    - completed: FINAL immutable state, no further updates allowed
    - upgraded: upgrade successfully applied, no regression allowed
    - fallback_completed: final fallback result stored, allows upgrade
    """
    db = SessionLocal()
    try:
        prediction = db.query(db_models.Prediction).filter(
            db_models.Prediction.id == prediction_id
        ).with_for_update().first()
        if not prediction:
            return
        
        # DB-level guard: reject updates to completed state
        if prediction.status == "completed":
            logger.warning(
                "REJECTED: Attempt to update prediction %s in completed state (immutable)",
                prediction_id
            )
            return
        
        # Guard: prevent state regression from upgraded
        if prediction.status == "upgraded" and fields.get("status") in ["fallback_completed", "upgrade_pending"]:
            logger.warning(
                "REJECTED: Attempt to regress prediction %s from upgraded to %s",
                prediction_id, fields.get("status")
            )
            return
        
        # Guard: prevent overwriting upgraded results
        if prediction.result_version == 2 and fields.get("result_version", 2) < 2:
            logger.warning(
                "REJECTED: Attempt to downgrade result_version for prediction %s",
                prediction_id
            )
            return
        
        for key, value in fields.items():
            setattr(prediction, key, value)
        db.commit()
    finally:
        db.close()


def locate_real_raster(dataset_id: Optional[str]) -> Optional[str]:
    """Return the first valid real raster from the dataset raw directory."""
    if not dataset_id:
        return None
    raw_dir = storage_service.raw_dir(dataset_id)
    for candidate in sorted(glob.glob(str(raw_dir / "*.tif")) + glob.glob(str(raw_dir / "*.tiff"))):
        try:
            return validate_raster(candidate)
        except Exception:
            continue
    return None


def get_cached_raster_path(cache_key: str) -> str:
    return os.path.join(get_cache_dir(), f"{cache_key}.tif")


def copy_raster_to_cache(source_path: str, cache_path: str, job_id: str) -> None:
    """Cache a validated real raster locally for reuse."""
    if os.path.abspath(source_path) == os.path.abspath(cache_path):
        return
    if not os.path.exists(cache_path):
        shutil.copy2(source_path, cache_path)
        update_job(job_id, log_line=f"Using cached data: stored {cache_path}", progress=44.0)


def fetch_real_data(job_id: str, dataset_id: str, region_geojson: dict, start_pre: str, end_pre: str, start_post: str, end_post: str) -> None:
    """Fetch and download a real raster into the dataset raw directory."""
    update_job(job_id, log_line="Fetching data", progress=22.0)
    logger.info("Fetching data for dataset %s", dataset_id)
    gee_service.submit_and_track(
        job_id=job_id,
        dataset_id=dataset_id,
        geojson=region_geojson,
        start_pre=start_pre or "",
        end_pre=end_pre or "",
        start_post=start_post or "",
        end_post=end_post or "",
    )


def wait_for_real_raster(dataset_id: str, attempts: int) -> Optional[str]:
    """Poll the dataset directory until a valid raster appears."""
    for i in range(attempts):
        raster_path = locate_real_raster(dataset_id)
        if raster_path:
            return raster_path
        if i < attempts - 1:
            time.sleep(FETCH_RETRY_INTERVAL_SECONDS)
    return None


def execute_prediction_artifacts(job_id: str, prediction_id: str, model_id: str, region_id: str, dataset_id: Optional[str], raster_path: str, weights_path: str, model_config: dict) -> None:
    """Run inference and persist all generated artifacts."""
    from app.ml.inference.run import run_inference
    from app.ml.utils.geo import compute_flood_stats, create_overlay_png, extract_flood_locations

    out_dir = storage_service.predictions_dir(prediction_id)
    mask_path = str(out_dir / "mask.tif")
    overlay_path = str(out_dir / "overlay.png")
    meta_path = str(out_dir / "meta.json")

    set_prediction_state(prediction_id, status="processing_data")
    update_job(job_id, log_line="processing_data", progress=50.0)

    set_prediction_state(prediction_id, status="running_model")
    update_job(job_id, log_line="Running model", progress=65.0)
    logger.info("Running model for prediction %s", prediction_id)

    run_inference(
        raster_path=raster_path,
        weights_path=weights_path,
        output_path=mask_path,
        model_config=model_config or {},
        job_id=job_id,
    )

    stats = compute_flood_stats(mask_path)
    flooded_places = extract_flood_locations(mask_path, max_locations=5)
    create_overlay_png(raster_path, mask_path, overlay_path)

    meta = {
            "prediction_id": prediction_id,
            "model_id": model_id,
            "region_id": region_id,
            "dataset_id": dataset_id,
            "raster_path": raster_path,
            "stats": stats,
            "locations_flooded": flooded_places,
        }
    storage_service.write_json(meta_path, meta)
    
    # Auto-generate PDF report
    try:
        report_path = str(out_dir / "report.pdf")
        report_service.generate_flood_report(prediction_id, meta, report_path)
        logger.info("Auto-generated PDF report for prediction %s", prediction_id)
    except Exception as e:
        logger.error("Failed to auto-generate PDF report: %s", e)


def background_upgrade_prediction(job_id: str, prediction_id: str, model_id: str, region_id: str, dataset_id: str, weights_path: str, model_config: dict, cache_path: str) -> None:
    """Wait for real data after a fallback result and upgrade the prediction.
    
    ATOMIC TRANSACTION: All operations commit together or rollback together.
    FAILURE RECOVERY: On failure, retains fallback result in fallback_completed state.
    """
    db = SessionLocal()
    try:
        # Acquire row-level lock and check current state
        prediction = db.query(db_models.Prediction).filter(
            db_models.Prediction.id == prediction_id
        ).with_for_update().first()
        
        if not prediction:
            logger.error("Prediction %s not found, cannot upgrade", prediction_id)
            return
        
        # Guard: Do not overwrite if already upgraded
        if prediction.result_version == 2:
            logger.info("Prediction %s already at result_version=2, skipping upgrade", prediction_id)
            logger.info("FINAL STATE LOCKED - NO FURTHER UPDATES ALLOWED")
            return
        
        # Only proceed if in fallback_completed state
        if prediction.status != "fallback_completed":
            logger.info(
                "Prediction %s not in fallback_completed state (current: %s), skipping upgrade",
                prediction_id, prediction.status
            )
            return
        
        # Transition to upgrade_pending
        prediction.status = "upgrade_pending"
        db.commit()
        logger.info("UPGRADE TRIGGERED: Background update started for prediction %s", prediction_id)
        update_job(job_id, log_line="Background update started", progress=96.0)
        
        # Release lock during long-running operations
        db.close()
        
        # Phase 1: Wait for and validate real data
        real_raster = wait_for_real_raster(dataset_id, UPGRADE_RETRY_ATTEMPTS)
        if not real_raster:
            update_job(job_id, log_line="Background update finished without real data", progress=96.0)
            logger.warning("Background upgrade finished without real data for prediction %s", prediction_id)
            # Revert to fallback_completed state
            db = SessionLocal()
            try:
                prediction = db.query(db_models.Prediction).filter(
                    db_models.Prediction.id == prediction_id
                ).with_for_update().first()
                if prediction:
                    prediction.status = "fallback_completed"
                    db.commit()
                    logger.info("UPGRADE FAILED - RETAINING FALLBACK: prediction %s", prediction_id)
            finally:
                db.close()
            return
        
        update_job(job_id, log_line=f"Real data detected: {real_raster}", progress=97.0)
        logger.info("Real data detected for prediction %s: %s", prediction_id, real_raster)

        validate_raster(real_raster)
        copy_raster_to_cache(real_raster, cache_path, job_id)
        update_job(job_id, log_line="Prediction re-run started", progress=98.0)
        logger.info("UPGRADING RESULT VERSION: Re-running prediction with real data for %s", prediction_id)
        
        # Phase 2: Execute ML inference (this handles meta.json and report.pdf automatically)
        execute_prediction_artifacts(
            job_id=job_id,
            prediction_id=prediction_id,
            model_id=model_id,
            region_id=region_id,
            dataset_id=dataset_id,
            raster_path=real_raster,
            weights_path=weights_path,
            model_config=model_config,
        )

        # Phase 3: Atomic database update
        db = SessionLocal()
        try:
            prediction = db.query(db_models.Prediction).filter(
                db_models.Prediction.id == prediction_id
            ).with_for_update().first()
            
            if prediction:
                # Final guard check before update
                if prediction.result_version == 2:
                    logger.info("Prediction %s already upgraded by another process, skipping", prediction_id)
                    logger.info("FINAL STATE LOCKED - NO FURTHER UPDATES ALLOWED")
                else:
                    prediction.status = "upgraded"
                    prediction.data_source = "real"
                    prediction.result_version = 2
                    db.commit()
                    logger.info("DATABASE UPDATED SUCCESSFULLY: prediction_id=%s, data_source=real, result_version=2", prediction_id)
                    logger.info("FINAL STATE LOCKED - NO FURTHER UPDATES ALLOWED")
            else:
                logger.error("Failed to update database: prediction %s not found", prediction_id)
        finally:
            db.close()
        
        update_job(job_id, log_line="Prediction upgraded", progress=100.0)
        logger.info("Prediction upgraded successfully: %s", prediction_id)
        
    except Exception as exc:
        logger.exception("Background update failed for prediction %s", prediction_id)
        update_job(job_id, log_line=f"Background update failed: {exc}", progress=100.0)
        
        # Failure recovery: retain fallback result
        db = SessionLocal()
        try:
            prediction = db.query(db_models.Prediction).filter(
                db_models.Prediction.id == prediction_id
            ).with_for_update().first()
            if prediction and prediction.status == "upgrade_pending":
                prediction.status = "fallback_completed"
                db.commit()
                logger.info("UPGRADE FAILED - RETAINING FALLBACK: prediction %s", prediction_id)
        except Exception as recovery_exc:
            logger.error("Failed to recover fallback state for prediction %s: %s", prediction_id, recovery_exc)
        finally:
            db.close()
    finally:
        # Final cleanup
        db.close()


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
    """Background task: run flood prediction using a registered model."""
    db = SessionLocal()
    try:
        update_job(job_id, log_line="running", progress=1.0)
        logger.info("Prediction job started: %s", prediction_id)

        model = db.query(db_models.MLModel).filter(db_models.MLModel.id == model_id).first()
        if not model:
            raise ValueError(f"Model {model_id} not found")

        region = db.query(db_models.Region).filter(db_models.Region.id == region_id).first()
        if not region:
            raise ValueError(f"Region {region_id} not found")

        if not dataset_id:
            raise ValueError("Prediction dataset_id is required")

        weights_path = resolve_weights_path(model.weights_path or "")
        if not os.path.isfile(weights_path):
            raise FileNotFoundError(f"Model weights file not found: {weights_path}")

        raw_dir = storage_service.raw_dir(dataset_id)
        storage_service.predictions_dir(prediction_id)
        cache_key = get_cache_key(region_id, start_pre or "", end_pre or "", start_post or "", end_post or "")
        cache_path = get_cached_raster_path(cache_key)

        update_job(job_id, log_line=f"Dataset created: {raw_dir}", progress=10.0)
        logger.info("Dataset created: %s", raw_dir)

        set_prediction_state(prediction_id, status="fetching_data")
        update_job(job_id, log_line="fetching_data", progress=15.0)

        raster_path: Optional[str] = locate_real_raster(dataset_id)
        data_source: Optional[str] = None
        fetch_initiated = False

        if raster_path:
            data_source = "real"
            update_job(job_id, log_line="Using real data", progress=20.0)
        elif os.path.isfile(cache_path):
            raster_path = validate_raster(cache_path)
            data_source = "cached"
            update_job(job_id, log_line="Using cached data", progress=20.0)
            logger.info("Using cached data for prediction %s", prediction_id)
        else:
            fetch_state = {"error": None}
            fetch_initiated = True

            def fetch_wrapper() -> None:
                try:
                    fetch_real_data(
                        job_id,
                        dataset_id,
                        region.geojson,
                        start_pre,
                        end_pre,
                        start_post,
                        end_post,
                    )
                except Exception as exc:
                    fetch_state["error"] = exc
                    logger.exception("Fetch failed for dataset %s", dataset_id)

            threading.Thread(target=fetch_wrapper, daemon=True).start()
            # Fast response: fall back immediately if no local/cached raster.
            raster_path = wait_for_real_raster(dataset_id, FAST_FALLBACK_ATTEMPTS)
            if raster_path:
                data_source = "real"
                update_job(job_id, log_line="Using real data", progress=35.0)
            else:
                if fetch_state["error"]:
                    update_job(job_id, log_line=f"Real data fetch failed: {fetch_state['error']}", progress=35.0)
                raster_path = get_fallback_dataset_path()
                data_source = "fallback"
                update_job(job_id, log_line="Using fallback", progress=35.0)
                logger.warning("Using fallback for prediction %s", prediction_id)

        raster_path = validate_raster(raster_path)
        if data_source == "real":
            copy_raster_to_cache(raster_path, cache_path, job_id)

        set_prediction_state(
            prediction_id,
            status="running",
            data_source=data_source,
            result_version=1,
        )

        execute_prediction_artifacts(
            job_id=job_id,
            prediction_id=prediction_id,
            model_id=model_id,
            region_id=region_id,
            dataset_id=dataset_id,
            raster_path=raster_path,
            weights_path=weights_path,
            model_config=model.config,
        )

        # Set final state based on data source
        # Frontend compatibility: processing -> completed/upgraded
        if data_source == "fallback":
            set_prediction_state(
                prediction_id,
                status="fallback_completed",
                data_source=data_source,
                result_version=1,
            )
            update_job(job_id, log_line="Prediction completed with fallback", progress=100.0)
            logger.info("Prediction completed: %s with data_source=fallback, status=fallback_completed", prediction_id)
        else:
            # For real/cached data, go directly to completed (no upgrade needed)
            set_prediction_state(
                prediction_id,
                status="completed",
                data_source=data_source,
                result_version=1,
            )
            update_job(job_id, log_line="Prediction completed", progress=100.0)
            logger.info("Prediction completed: %s with data_source=%s, status=completed", prediction_id, data_source)
            logger.info("FINAL STATE LOCKED - NO FURTHER UPDATES ALLOWED")

        # Trigger background upgrade ONLY if in fallback_completed state
        # This ensures fallback result commits BEFORE upgrade starts
        if data_source == "fallback":
            logger.info("UPGRADE TRIGGERED: Starting background upgrade for prediction %s", prediction_id)
            upgrade_thread = threading.Thread(
                target=background_upgrade_prediction,
                args=(
                    job_id,
                    prediction_id,
                    model_id,
                    region_id,
                    dataset_id,
                    weights_path,
                    model.config,
                    cache_path,
                ),
                daemon=True,
            )
            upgrade_thread.start()
        else:
            logger.info("No upgrade needed: prediction %s not using fallback data", prediction_id)

    except Exception as exc:
        logger.exception("Prediction failed: %s", prediction_id)
        update_job(job_id, log_line=f"Task failed: {exc}", progress=100.0)
        set_prediction_state(prediction_id, status="failed")
        raise
    finally:
        db.close()
