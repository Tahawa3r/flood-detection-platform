"""
Test utilities for prediction integrity verification.

This module provides the single source of truth for correctness
by enforcing strict state machine invariants.
"""

import logging
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.db.database import SessionLocal
from app.db import models as db_models

logger = logging.getLogger(__name__)

# Valid terminal states
TERMINAL_STATES = {"completed", "upgraded", "fallback_completed", "failed"}

# Valid intermediate states
INTERMEDIATE_STATES = {"pending", "fetching_data", "processing_data", "running_model", "upgrade_pending"}

# All valid states
VALID_STATES = TERMINAL_STATES | INTERMEDIATE_STATES

# State → result_version mapping
STATE_VERSION_MAP = {
    "fallback_completed": 1,
    "upgraded": 2,
    "completed": 1,  # real/cached data
    "failed": 1,
}

# State → data_source mapping
STATE_DATASOURCE_MAP = {
    "fallback_completed": "fallback",
    "upgraded": "real",
    "completed": None,  # can be real or cached
    "failed": None,
}


def assert_prediction_integrity(prediction_id: str) -> bool:
    """
    Verify prediction state machine integrity.
    
    Checks:
    1. State is valid (no illegal transitions)
    2. result_version matches state
    3. data_source matches version
    4. completed state is immutable (verified by guards)
    5. No intermediate state leaks in terminal state
    
    Raises AssertionError if any invariant is violated.
    Returns True if all checks pass.
    """
    db = SessionLocal()
    try:
        prediction = db.query(db_models.Prediction).filter(
            db_models.Prediction.id == prediction_id
        ).first()
        
        if not prediction:
            raise AssertionError(f"Prediction {prediction_id} not found")
        
        logger.info(f"Integrity check for {prediction_id[:8]}: status={prediction.status}, "
                   f"data_source={prediction.data_source}, result_version={prediction.result_version}")
        
        # Check 1: State is valid
        if prediction.status not in VALID_STATES:
            raise AssertionError(
                f"INVALID STATE: prediction {prediction_id} has invalid status '{prediction.status}'. "
                f"Valid states: {VALID_STATES}"
            )
        
        # Check 2: result_version matches state
        if prediction.status in STATE_VERSION_MAP:
            expected_version = STATE_VERSION_MAP[prediction.status]
            if prediction.result_version != expected_version:
                raise AssertionError(
                    f"VERSION MISMATCH: prediction {prediction_id} in state '{prediction.status}' "
                    f"has result_version={prediction.result_version}, expected {expected_version}"
                )
        
        # Check 3: data_source matches version
        if prediction.status in STATE_DATASOURCE_MAP:
            expected_datasource = STATE_DATASOURCE_MAP[prediction.status]
            if expected_datasource is not None and prediction.data_source != expected_datasource:
                raise AssertionError(
                    f"DATASOURCE MISMATCH: prediction {prediction_id} in state '{prediction.status}' "
                    f"has data_source='{prediction.data_source}', expected '{expected_datasource}'"
                )
        
        # Check 4: result_version consistency with data_source
        if prediction.result_version == 2 and prediction.data_source != "real":
            raise AssertionError(
                f"VERSION/DATASOURCE MISMATCH: prediction {prediction_id} has result_version=2 "
                f"but data_source='{prediction.data_source}' (must be 'real')"
            )
        
        if prediction.result_version == 1 and prediction.data_source == "real" and prediction.status != "completed":
            raise AssertionError(
                f"VERSION/DATASOURCE MISMATCH: prediction {prediction_id} has result_version=1 "
                f"with data_source='real' but status='{prediction.status}' (should be 'completed')"
            )
        
        # Check 5: No intermediate state leaks in terminal state
        if prediction.status in TERMINAL_STATES:
            # Verify no intermediate states are mixed
            if prediction.status == "upgraded":
                if prediction.result_version != 2:
                    raise AssertionError(
                        f"TERMINAL STATE CORRUPTION: prediction {prediction_id} in 'upgraded' state "
                        f"has result_version={prediction.result_version} (must be 2)"
                    )
                if prediction.data_source != "real":
                    raise AssertionError(
                        f"TERMINAL STATE CORRUPTION: prediction {prediction_id} in 'upgraded' state "
                        f"has data_source='{prediction.data_source}' (must be 'real')"
                    )
            
            if prediction.status == "fallback_completed":
                if prediction.result_version != 1:
                    raise AssertionError(
                        f"TERMINAL STATE CORRUPTION: prediction {prediction_id} in 'fallback_completed' state "
                        f"has result_version={prediction.result_version} (must be 1)"
                    )
                if prediction.data_source != "fallback":
                    raise AssertionError(
                        f"TERMINAL STATE CORRUPTION: prediction {prediction_id} in 'fallback_completed' state "
                        f"has data_source='{prediction.data_source}' (must be 'fallback')"
                    )
        
        logger.info(f"Integrity check PASSED for {prediction_id[:8]}")
        return True
        
    finally:
        db.close()


def assert_predictions_integrity(prediction_ids: list) -> bool:
    """
    Verify integrity for multiple predictions.
    
    Returns True only if all predictions pass integrity checks.
    Raises AssertionError on first failure.
    """
    for pred_id in prediction_ids:
        assert_prediction_integrity(pred_id)
    return True
