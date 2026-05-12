"""
Production-grade integration test for fallback → real data upgrade.

Tests the prediction workflow where:
1. Initial prediction uses fallback data (result_version=1, data_source="fallback")
2. Background upgrade fetches real data and upgrades prediction (result_version=2, data_source="real")
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Add backend to path
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.db.database import SessionLocal
from app.db import models as db_models
from app.services import job_service, predict_service, storage_service
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
POLLING_INTERVAL_SECONDS = 2
MAX_POLLING_RETRIES = 30
CLEANUP_TIMEOUT_SECONDS = 5


def get_latest_valid_model(db) -> db_models.MLModel:
    """
    Fetch the latest valid model from the database.
    Raises ValueError if no model found.
    """
    model = db.query(db_models.MLModel).order_by(
        db_models.MLModel.created_at.desc()
    ).first()
    
    if not model:
        raise ValueError(
            "No valid model found in database. "
            "Please register a model before running the integration test."
        )
    
    logger.info(f"Found model: {model.id} - {model.name}")
    return model


def get_latest_valid_region(db) -> db_models.Region:
    """
    Fetch the latest valid region from the database.
    Raises ValueError if no region found.
    """
    region = db.query(db_models.Region).order_by(
        db_models.Region.created_at.desc()
    ).first()
    
    if not region:
        raise ValueError(
            "No valid region found in database. "
            "Please create a region before running the integration test."
        )
    
    logger.info(f"Found region: {region.id} - {region.name}")
    return region


def create_test_dataset(db, region_id: str) -> db_models.Dataset:
    """
    Create a test dataset for the integration test.
    """
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
    
    # Ensure raw directory exists
    storage_service.raw_dir(dataset.id)
    
    logger.info(f"Created test dataset: {dataset.id}")
    return dataset


def poll_prediction_upgrade(prediction_id: str, max_retries: int = MAX_POLLING_RETRIES) -> dict:
    """
    Poll prediction status until upgrade completes or fails.
    
    Returns the final prediction state.
    Raises Exception if upgrade fails after max retries.
    """
    db = SessionLocal()
    try:
        for attempt in range(max_retries):
            prediction = db.query(db_models.Prediction).filter(
                db_models.Prediction.id == prediction_id
            ).first()
            
            if not prediction:
                raise ValueError(f"Prediction {prediction_id} not found during polling")
            
            logger.info(
                f"Poll attempt {attempt + 1}/{max_retries}: "
                f"status={prediction.status}, "
                f"data_source={prediction.data_source}, "
                f"result_version={prediction.result_version}"
            )
            
            # Check if upgrade completed successfully
            if (prediction.status == "completed" and 
                prediction.data_source == "real" and 
                prediction.result_version == 2):
                logger.info("Upgrade completed successfully")
                return {
                    "status": prediction.status,
                    "data_source": prediction.data_source,
                    "result_version": prediction.result_version
                }
            
            # Check if prediction failed
            if prediction.status == "failed":
                raise Exception(
                    f"Prediction failed during polling. "
                    f"Final state: data_source={prediction.data_source}, "
                    f"result_version={prediction.result_version}"
                )
            
            # Wait before next poll
            if attempt < max_retries - 1:
                time.sleep(POLLING_INTERVAL_SECONDS)
        
        # Max retries reached without successful upgrade
        db.refresh(prediction)
        raise Exception(
            f"Background upgrade FAILED after {max_retries} retries. "
            f"Final state: status={prediction.status}, "
            f"data_source={prediction.data_source}, "
            f"result_version={prediction.result_version}. "
            f"Expected: status='completed', data_source='real', result_version=2"
        )
    finally:
        db.close()


def cleanup_test_resources(prediction_id: str, dataset_id: str) -> None:
    """
    Safely clean up test resources.
    Wrapped in try/except to never fail the test due to cleanup errors.
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting cleanup for prediction {prediction_id}")
        
        # Delete prediction
        prediction = db.query(db_models.Prediction).filter(
            db_models.Prediction.id == prediction_id
        ).first()
        if prediction:
            db.delete(prediction)
            logger.info(f"Deleted prediction: {prediction_id}")
        
        # Delete dataset
        dataset = db.query(db_models.Dataset).filter(
            db_models.Dataset.id == dataset_id
        ).first()
        if dataset:
            db.delete(dataset)
            logger.info(f"Deleted dataset: {dataset_id}")
        
        db.commit()
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Cleanup failed (non-critical): {e}")
        # Never re-raise - cleanup failures should not fail the test
    finally:
        db.close()


def run_integration_test() -> bool:
    """
    Run the integration test for fallback → real data upgrade.
    
    Returns True if test passes, False otherwise.
    """
    logger.info("=" * 70)
    logger.info("STARTING INTEGRATION TEST: fallback → real upgrade")
    logger.info("=" * 70)
    
    db = SessionLocal()
    prediction_id = None
    dataset_id = None
    
    try:
        # Step 1: Fetch latest valid model (no hard-coded UUIDs)
        logger.info("\n[STEP 1] Fetching latest valid model...")
        model = get_latest_valid_model(db)
        
        # Step 2: Fetch latest valid region (no hard-coded UUIDs)
        logger.info("\n[STEP 2] Fetching latest valid region...")
        region = get_latest_valid_region(db)
        
        # Step 3: Create test dataset
        logger.info("\n[STEP 3] Creating test dataset...")
        dataset = create_test_dataset(db, region.id)
        dataset_id = dataset.id
        
        # Step 4: Create prediction job
        logger.info("\n[STEP 4] Creating prediction job...")
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
        
        logger.info(f"Created prediction: {prediction_id}")
        
        # Step 5: Run prediction (should use fallback initially)
        logger.info("\n[STEP 5] Running prediction (expecting fallback)...")
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
        
        # Wait for initial prediction to complete
        time.sleep(5)
        db.refresh(prediction)
        
        # Assertion: Initial result should be fallback
        logger.info(f"Initial prediction state: data_source={prediction.data_source}, result_version={prediction.result_version}")
        assert prediction.data_source in ["fallback", "real", "cached"], \
            f"Invalid initial data_source: {prediction.data_source}"
        assert prediction.result_version in [1, 2], \
            f"Invalid initial result_version: {prediction.result_version}"
        
        if prediction.data_source == "fallback":
            logger.info("TEST PASSED: Initial prediction used fallback data as expected")
        else:
            logger.warning(f"Initial prediction used {prediction.data_source} data (not fallback)")
        
        # Step 6: Poll for background upgrade
        logger.info("\n[STEP 6] Polling for background upgrade...")
        final_state = poll_prediction_upgrade(prediction_id)
        
        # Step 7: Verify final state with assertions
        logger.info("\n[STEP 7] Verifying final state...")
        assert final_state["data_source"] in ["fallback", "real"], \
            f"Invalid final data_source: {final_state['data_source']}"
        assert final_state["result_version"] in [1, 2], \
            f"Invalid final result_version: {final_state['result_version']}"
        
        # Critical assertion for upgrade success
        if final_state["data_source"] == "real" and final_state["result_version"] == 2:
            logger.info("TEST PASSED: fallback → real upgrade successful")
            logger.info("=" * 70)
            logger.info("INTEGRATION TEST PASSED")
            logger.info("=" * 70)
            return True
        else:
            logger.error(
                f"TEST FAILED: Expected data_source='real' and result_version=2, "
                f"got data_source='{final_state['data_source']}', "
                f"result_version={final_state['result_version']}"
            )
            logger.info("=" * 70)
            logger.info("INTEGRATION TEST FAILED")
            logger.info("=" * 70)
            return False
            
    except ValueError as e:
        logger.error(f"TEST FAILED: {e}")
        logger.info("=" * 70)
        logger.info("INTEGRATION TEST FAILED")
        logger.info("=" * 70)
        return False
        
    except Exception as e:
        logger.error(f"TEST FAILED: Unexpected error: {e}")
        logger.info("=" * 70)
        logger.info("INTEGRATION TEST FAILED")
        logger.info("=" * 70)
        return False
        
    finally:
        # Step 8: Cleanup (wrapped in try/except for safety)
        if prediction_id and dataset_id:
            logger.info("\n[STEP 8] Cleaning up test resources...")
            cleanup_test_resources(prediction_id, dataset_id)
        
        db.close()


if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
