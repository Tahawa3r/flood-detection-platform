"""
Local filesystem helpers: directory management, file listing, JSON I/O.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any

from app.core.config import settings


def ensure_dir(path: str) -> Path:
    """Create directory (and parents) if it doesn't exist. Returns Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def raw_dir(dataset_id: str) -> Path:
    """Return the raw data directory for a dataset."""
    return ensure_dir(os.path.join(settings.DATA_DIR, "raw", dataset_id))


def processed_dir(dataset_id: str) -> Path:
    """Return the processed data directory for a dataset."""
    return ensure_dir(os.path.join(settings.DATA_DIR, "processed", dataset_id))


def predictions_dir(prediction_id: str) -> Path:
    """Return the predictions output directory."""
    return ensure_dir(os.path.join(settings.DATA_DIR, "predictions", prediction_id))


def model_dir(model_id: str) -> Path:
    """Return the model registry directory for a model."""
    return ensure_dir(os.path.join(settings.MODELS_DIR, model_id))


def list_files(directory: str, extension: str = None) -> List[str]:
    """List files in a directory, optionally filtering by extension."""
    p = Path(directory)
    if not p.exists():
        return []
    files = []
    for f in p.iterdir():
        if f.is_file():
            if extension is None or f.suffix.lower() == extension.lower():
                files.append(str(f))
    return files


def read_json(path: str) -> Dict[str, Any]:
    """Read a JSON file and return its contents."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Dict[str, Any]):
    """Write data to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def write_text(path: str, content: str):
    """Write text content to a file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
