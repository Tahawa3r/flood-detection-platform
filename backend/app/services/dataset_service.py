"""
Dataset preparation service.
Converts raw GeoTIFF rasters into NumPy patches with pseudo-labels
for training the flood detection model.
"""

import os
import glob
import numpy as np
from pathlib import Path

from app.services.job_service import update_job
from app.services import storage_service


def prepare_dataset(job_id: str, dataset_id: str, patch_size: int = 256):
    """
    Background task: read raw GeoTIFF(s) for a dataset, extract
    fixed-size patches, generate pseudo-labels, and save as .npy files.

    Pseudo-labels are generated from the diffVV band using Otsu-like
    thresholding (simple threshold for now).
    """
    raw = storage_service.raw_dir(dataset_id)
    out = storage_service.processed_dir(dataset_id)

    tif_files = glob.glob(str(raw / "*.tif"))
    if not tif_files:
        update_job(job_id, log_line=f"No .tif files found in {raw}")
        raise FileNotFoundError(f"No .tif files in {raw}")

    update_job(job_id, log_line=f"Found {len(tif_files)} raster file(s)")

    try:
        import rasterio
    except ImportError:
        update_job(job_id, log_line="rasterio not installed — skipping patch extraction")
        raise

    all_patches_X = []
    all_patches_y = []

    for tif_path in tif_files:
        update_job(job_id, log_line=f"Processing {os.path.basename(tif_path)}...")

        with rasterio.open(tif_path) as src:
            data = src.read()  # (bands, H, W)
            bands, height, width = data.shape

            update_job(job_id, log_line=f"  Shape: {data.shape} ({bands} bands, {height}x{width})")

            # Extract non-overlapping patches
            n_rows = height // patch_size
            n_cols = width // patch_size

            for r in range(n_rows):
                for c in range(n_cols):
                    y0 = r * patch_size
                    x0 = c * patch_size
                    patch = data[:, y0:y0 + patch_size, x0:x0 + patch_size]

                    # Skip patches that are mostly nodata
                    if np.isnan(patch).mean() > 0.5:
                        continue

                    # Pseudo-label: use last band (diffVV) with threshold
                    diff_band = patch[-1]
                    label = (diff_band < -2.0).astype(np.float32)  # negative diff → flood
                    all_patches_y.append(label)
                    
                    # Normalization Step: clamp dB outliers and map softly into [0, 1] for neural network
                    norm_patch = np.nan_to_num(patch, nan=0.0).astype(np.float32)
                    norm_patch = np.clip(norm_patch, -30.0, 0.0)
                    norm_patch = (norm_patch + 30.0) / 30.0
                    all_patches_X.append(norm_patch)

    if not all_patches_X:
        update_job(job_id, log_line="No valid patches extracted")
        raise ValueError("No valid patches could be extracted from the raster(s)")

    X = np.stack(all_patches_X)  # (N, C, H, W)
    y = np.stack(all_patches_y)  # (N, H, W)

    update_job(job_id, log_line=f"Extracted {len(X)} patches of shape {X.shape[1:]}")

    # Split 80/20 train/val
    n_train = int(0.8 * len(X))
    np.save(str(out / "train_X.npy"), X[:n_train])
    np.save(str(out / "train_y.npy"), y[:n_train])
    np.save(str(out / "val_X.npy"), X[n_train:])
    np.save(str(out / "val_y.npy"), y[n_train:])

    update_job(job_id, log_line=f"Saved {n_train} train + {len(X) - n_train} val patches to {out}")
