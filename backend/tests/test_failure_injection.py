"""
Failure injection test: ML crash mid-upgrade

Verifies failure recovery mechanism:
1. Initial prediction uses fallback (status=fallback_completed)
2. Background upgrade starts (status=upgrade_pending)
3. ML inference fails mid-upgrade
4. System recovers to fallback_completed state
5. Fallback result remains intact
"""

import logging
import sys
import time
from pathlib import Path
from unittest.mock import patch

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
MAX_RETRIES = 20


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


def mock_inference_failure(*args, **kwargs):
    """Mock function that simulates ML inference failure."""
    logger.error("INJECTED FAILURE: Simulating ML inference crash")
    raise RuntimeError("Injected ML inference failure for testing")


def poll_failure_recovery(prediction_id):
    """Poll prediction to verify failure recovery."""
    db = SessionLocal()
    try:
        for attempt in range(MAX_RETRIES):
            prediction = db.query(db_models.Prediction).filter(
                db_models.Prediction.id == prediction_id
            ).first()
            
            if not prediction:
                raise ValueError(f"Prediction {prediction_id} not found")
            
            logger.info(
                f"Recovery poll {attempt + 1}/{MAX_RETRIES}: "
                f"status={prediction.status}, "
                f"data_source={prediction.data_source}, "
                f"result_version={prediction.result_version}"
            )
            
            # Success condition: recovered to fallback_completed
            if (prediction.status == "fallback_completed" and 
                prediction.data_source == "fallback" and 
                prediction.result_version == 1):
                logger.info("FAILURE RECOVERY SUCCESSFUL: Retained fallback result")
                return True
            
            # Check if upgrade was attempted
            if prediction.status == "upgrade_pending":
                logger.info("Upgrade was initiated (as expected)")
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(POLLING_INTERVAL)
        
        # Max retries reached
        db.refresh(prediction)
        logger.error(
            f"RECOVERY FAILED: Final state: status={prediction.status}, "
            f"data_source={prediction.data_source}, result_version={prediction.result_version}"
        )
        return False
    finally:
        db.close()


def run_failure_injection_test():
    """Run failure injection test."""
    logger.info("=" * 70)
    logger.info("FAILURE INJECTION TEST: ML crash mid-upgrade")
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
        
        logger.info(f"Starting prediction with failure injection: {prediction_id}")
        
        # Patch run_inference to inject failure
        with patch('app.ml.inference.run.run_inference', side_effect=mock_inference_failure):
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
        
        # Poll for failure recovery
        success = poll_failure_recovery(prediction_id)
        
        if success:
            # Verify final state integrity
            logger.info("Running integrity check...")
            assert_prediction_integrity(prediction_id)
            
            logger.info("=" * 70)
            logger.info("FAILURE INJECTION TEST PASSED")
            logger.info("=" * 70)
            return True
        else:
            logger.info("=" * 70)
            logger.info("FAILURE INJECTION TEST FAILED")
            logger.info("=" * 70)
            return False
            
    except Exception as e:
        logger.error(f"FAILURE INJECTION TEST ERROR: {e}")
        logger.info("=" * 70)
        logger.info("FAILURE INJECTION TEST FAILED")
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
    success = run_failure_injection_test()
    sys.exit(0 if success else 1)
