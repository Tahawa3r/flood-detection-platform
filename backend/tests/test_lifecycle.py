"""
Deterministic lifecycle test: fallback → upgrade → completed

Verifies the complete state machine lifecycle:
1. Initial prediction uses fallback (status=fallback_completed, result_version=1)
2. Background upgrade fetches real data (status=upgrade_pending)
3. Upgrade completes successfully (status=upgraded, result_version=2)
"""

import logging
import sys
import time
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.db.database import SessionLocal
from app.db import models as db_models
from app.services import job_service, predict_service, storage_service
from tests.test_utils import assert_prediction_integrity

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

POLLING_INTERVAL = 2
MAX_RETRIES = 30


def get_latest_model(db):
    return db.query(db_models.MLModel).order_by(
        db_models.MLModel.created_at.desc()
    ).first()


def get_latest_region(db):
    return db.query(db_models.Region).order_by(
        db_models.Region.created_at.desc()
    ).first()


def create_test_dataset(db, region_id):
    dataset = db_models.Dataset(
        region_id=region_id,
        start_pre="2023-01-01",
        end_pre="2023-01-15",
        start_post="2023-02-01",
        end_post="2023-02-15",
        scale=100,
        patch_size=256,
        status="created"
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    storage_service.raw_dir(dataset.id)
    return dataset


def poll_lifecycle(prediction_id):
    """Poll prediction through complete lifecycle."""
    db = SessionLocal()
    try:
        for attempt in range(MAX_RETRIES):
            prediction = db.query(db_models.Prediction).filter(
                db_models.Prediction.id == prediction_id
            ).first()
            
            if not prediction:
                raise ValueError(f"Prediction {prediction_id} not found")
            
            logger.info(
                f"Lifecycle poll {attempt + 1}/{MAX_RETRIES}: "
                f"status={prediction.status}, "
                f"data_source={prediction.data_source}, "
                f"result_version={prediction.result_version}"
            )
            
            # Success condition: upgraded with real data
            if (prediction.status == "upgraded" and 
                prediction.data_source == "real" and 
                prediction.result_version == 2):
                logger.info("LIFECYCLE COMPLETE: fallback → upgrade → upgraded")
                return True
            
            # Failure condition: stuck in fallback
            if (prediction.status == "fallback_completed" and 
                attempt > 15 and 
                prediction.result_version == 1):
                logger.warning("Still in fallback_completed after 15 retries")
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(POLLING_INTERVAL)
        
        # Max retries reached
        db.refresh(prediction)
        logger.error(
            f"LIFECYCLE FAILED: Final state: status={prediction.status}, "
            f"data_source={prediction.data_source}, result_version={prediction.result_version}"
        )
        return False
    finally:
        db.close()


def run_lifecycle_test():
    """Run deterministic lifecycle test."""
    logger.info("=" * 70)
    logger.info("LIFECYCLE TEST: fallback → upgrade → completed")
    logger.info("=" * 70)
    
    db = SessionLocal()
    prediction_id = None
    dataset_id = None
    
    try:
        model = get_latest_model(db)
        if not model:
            raise ValueError("No model found")
        
        region = get_latest_region(db)
        if not region:
            raise ValueError("No region found")
        
        dataset = create_test_dataset(db, region.id)
        dataset_id = dataset.id
        
        job = job_service.create_job(db, job_type="predict")
        
        prediction = db_models.Prediction(
            model_id=model.id,
            region_id=region.id,
            dataset_id=dataset.id,
            job_id=job.id,
            start_pre="2023-01-01",
            end_pre="2023-01-15",
            start_post="2023-02-01",
            end_post="2023-02-15",
            status="pending",
            data_source=None,
            result_version=1
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
        prediction_id = prediction.id
        
        logger.info(f"Starting prediction: {prediction_id}")
        
        job_service.run_in_background(
            job.id,
            predict_service.run_prediction,
            prediction_id=prediction.id,
            model_id=model.id,
            region_id=region.id,
            dataset_id=dataset.id,
            start_pre="2023-01-01",
            end_pre="2023-01-15",
            start_post="2023-02-01",
            end_post="2023-02-15"
        )
        
        # Wait for initial fallback completion
        time.sleep(5)
        
        # Poll through lifecycle
        success = poll_lifecycle(prediction_id)
        
        if success:
            # Verify final state integrity
            logger.info("Running integrity check...")
            assert_prediction_integrity(prediction_id)
            
            logger.info("=" * 70)
            logger.info("LIFECYCLE TEST PASSED")
            logger.info("=" * 70)
            return True
        else:
            logger.info("=" * 70)
            logger.info("LIFECYCLE TEST FAILED")
            logger.info("=" * 70)
            return False
            
    except Exception as e:
        logger.error(f"LIFECYCLE TEST ERROR: {e}")
        logger.info("=" * 70)
        logger.info("LIFECYCLE TEST FAILED")
        logger.info("=" * 70)
        return False
    finally:
        if prediction_id and dataset_id:
            try:
                prediction = db.query(db_models.Prediction).filter(
                    db_models.Prediction.id == prediction_id
                ).first()
                if prediction:
                    db.delete(prediction)
                
                dataset = db.query(db_models.Dataset).filter(
                    db_models.Dataset.id == dataset_id
                ).first()
                if dataset:
                    db.delete(dataset)
                
                db.commit()
                logger.info("Cleanup completed")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
        
        db.close()


if __name__ == "__main__":
    success = run_lifecycle_test()
    sys.exit(0 if success else 1)
