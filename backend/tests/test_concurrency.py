"""
Concurrency test: 5 parallel predictions on same dataset

Verifies state machine under concurrent load:
1. Create 5 predictions simultaneously for same dataset
2. All predictions should complete without race conditions
3. Row-level locking prevents state corruption
4. No deadlocks or blocking issues
"""

import logging
import sys
import time
import threading
from pathlib import Path
from typing import List

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.db.database import SessionLocal
from app.db import models as db_models
from app.services import job_service, predict_service, storage_service
from tests.test_utils import assert_predictions_integrity

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

NUM_PARALLEL = 5
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


def run_single_prediction(model_id, region_id, dataset_id, prediction_id, job_id):
    """Run a single prediction in a thread."""
    try:
        predict_service.run_prediction(
            job_id=job_id,
            prediction_id=prediction_id,
            model_id=model_id,
            region_id=region_id,
            dataset_id=dataset_id,
            start_pre="2023-01-01",
            end_pre="2023-01-15",
            start_post="2023-02-01",
            end_post="2023-02-15"
        )
    except Exception as e:
        logger.error(f"Prediction {prediction_id} failed: {e}")


def poll_concurrent_predictions(prediction_ids: List[str]):
    """Poll all concurrent predictions to completion."""
    db = SessionLocal()
    try:
        completed = set()
        
        for attempt in range(MAX_RETRIES):
            logger.info(f"Concurrency poll {attempt + 1}/{MAX_RETRIES}")
            
            for pred_id in prediction_ids:
                if pred_id in completed:
                    continue
                
                prediction = db.query(db_models.Prediction).filter(
                    db_models.Prediction.id == pred_id
                ).first()
                
                if not prediction:
                    logger.error(f"Prediction {pred_id} not found")
                    continue
                
                logger.info(
                    f"  Prediction {pred_id[:8]}: status={prediction.status}, "
                    f"data_source={prediction.data_source}, result_version={prediction.result_version}"
                )
                
                # Check if completed (any terminal state)
                if prediction.status in ["completed", "upgraded", "fallback_completed", "failed"]:
                    completed.add(pred_id)
                    logger.info(f"  Prediction {pred_id[:8]} reached terminal state: {prediction.status}")
            
            if len(completed) == len(prediction_ids):
                logger.info(f"All {len(prediction_ids)} predictions completed")
                return True
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(POLLING_INTERVAL)
        
        logger.error(f"CONCURRENCY TEST FAILED: Only {len(completed)}/{len(prediction_ids)} completed")
        return False
    finally:
        db.close()


def run_concurrency_test():
    """Run concurrency test with 5 parallel predictions."""
    logger.info("=" * 70)
    logger.info(f"CONCURRENCY TEST: {NUM_PARALLEL} parallel predictions")
    logger.info("=" * 70)
    
    db = SessionLocal()
    prediction_ids = []
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
        
        logger.info(f"Created dataset: {dataset_id}")
        
        # Create parallel predictions
        threads = []
        for i in range(NUM_PARALLEL):
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
            prediction_ids.append(prediction.id)
            
            logger.info(f"Created prediction {i + 1}/{NUM_PARALLEL}: {prediction.id}")
        
        # Start all predictions in parallel
        logger.info("Starting all predictions in parallel...")
        for i, pred_id in enumerate(prediction_ids):
            job = db.query(db_models.Job).filter(
                db_models.Job.id == db.query(db_models.Prediction).filter(
                    db_models.Prediction.id == pred_id
                ).first().job_id
            ).first()
            
            thread = threading.Thread(
                target=run_single_prediction,
                args=(model.id, region.id, dataset.id, pred_id, job.id),
                daemon=True
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to start
        time.sleep(2)
        
        # Poll for completion
        success = poll_concurrent_predictions(prediction_ids)
        
        if success:
            # Verify final state integrity for all predictions
            logger.info("Running integrity check for all predictions...")
            assert_predictions_integrity(prediction_ids)
            
            # Verify final states
            logger.info("Verifying final states...")
            for pred_id in prediction_ids:
                prediction = db.query(db_models.Prediction).filter(
                    db_models.Prediction.id == pred_id
                ).first()
                if prediction:
                    logger.info(
                        f"Final state for {pred_id[:8]}: status={prediction.status}, "
                        f"data_source={prediction.data_source}, result_version={prediction.result_version}"
                    )
            
            logger.info("=" * 70)
            logger.info("CONCURRENCY TEST PASSED")
            logger.info("=" * 70)
            return True
        else:
            logger.info("=" * 70)
            logger.info("CONCURRENCY TEST FAILED")
            logger.info("=" * 70)
            return False
            
    except Exception as e:
        logger.error(f"CONCURRENCY TEST ERROR: {e}")
        logger.info("=" * 70)
        logger.info("CONCURRENCY TEST FAILED")
        logger.info("=" * 70)
        return False
    finally:
        # Cleanup all predictions
        if prediction_ids and dataset_id:
            try:
                for pred_id in prediction_ids:
                    prediction = db.query(db_models.Prediction).filter(
                        db_models.Prediction.id == pred_id
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
    success = run_concurrency_test()
    sys.exit(0 if success else 1)
