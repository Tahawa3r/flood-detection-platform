"""
Tile-based inference pipeline.
Reads a GeoTIFF window-by-window, runs the U-Net model, and writes the
output mask as a single-band GeoTIFF.
"""

import numpy as np
import torch

from app.services.job_service import update_job


PATCH_SIZE = 256
OVERLAP = 32


def run_inference(
    raster_path: str,
    weights_path: str,
    output_path: str,
    model_config: dict = None,
    job_id: str = None,
):
    """
    Run tile-based inference on a GeoTIFF raster.
    
    Args:
        raster_path:  Path to the input GeoTIFF (multi-band composite).
        weights_path: Path to the model weights (.pt file).
        output_path:  Path where the binary mask GeoTIFF will be saved.
        model_config: Dict with 'in_channels' and 'base_filters'.
        job_id:       Optional job ID for progress reporting.
    """
    import rasterio
    from rasterio.windows import Window
    from app.ml.models.unet import UNet

    config = model_config or {}
    in_channels = config.get("in_channels", 3)
    base_filters = config.get("base_filters", 32)

    # Load model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = UNet(in_channels=in_channels, base_filters=base_filters).to(device)
    model.load_state_dict(torch.load(weights_path, map_location=device))
    model.eval()

    if job_id:
        update_job(job_id, log_line=f"Model loaded on {device}")

    with rasterio.open(raster_path) as src:
        height = src.height
        width = src.width
        
        # Profile for the output mask (1 band)
        out_profile = src.profile.copy()
        out_profile.update(count=1, dtype="float32", nodata=0)

        # Step size with overlap
        step = PATCH_SIZE - OVERLAP

        # Pre-allocate output arrays
        mask_sum = np.zeros((height, width), dtype=np.float32)
        mask_count = np.zeros((height, width), dtype=np.float32)

        total_tiles = ((height + step - 1) // step) * ((width + step - 1) // step)
        tile_idx = 0

        for row in range(0, height, step):
            for col in range(0, width, step):

                    # Clamp window to raster bounds
                    win_h = min(PATCH_SIZE, height - row)
                    win_w = min(PATCH_SIZE, width - col)

                    window = Window(col, row, win_w, win_h)
                    data = src.read(window=window)  # (bands, h, w)

                    # Ensure data has in_channels dimensions and is PATCH_SIZE x PATCH_SIZE
                    padded = np.zeros((in_channels, PATCH_SIZE, PATCH_SIZE), dtype=np.float32)
                    actual_bands = min(in_channels, data.shape[0])
                    padded[:actual_bands, :win_h, :win_w] = data[:actual_bands, :win_h, :win_w]
                    data = padded

                    # Clean, clamp and Normalize identically to dataset_server.py
                    data = np.nan_to_num(data, nan=0.0).astype(np.float32)
                    data = np.clip(data, -30.0, 0.0)
                    data = (data + 30.0) / 30.0

                    # Inference
                    tensor = torch.from_numpy(data).unsqueeze(0).to(device)
                    with torch.no_grad():
                        pred = model(tensor).squeeze().cpu().numpy()

                    # Accumulate (crop to valid area)
                    mask_sum[row:row + win_h, col:col + win_w] += pred[:win_h, :win_w]
                    mask_count[row:row + win_h, col:col + win_w] += 1.0

                    tile_idx += 1
                    if job_id and tile_idx % 10 == 0:
                        progress = 20 + (tile_idx / total_tiles) * 65
                        update_job(job_id, progress=progress,
                                   log_line=f"Processed tile {tile_idx}/{total_tiles}")

        # Average overlapping predictions
        mask_count = np.maximum(mask_count, 1.0)
        final_mask = mask_sum / mask_count

        # Binarize at 0.5 threshold
        binary_mask = (final_mask >= 0.5).astype(np.float32)

        # Write output
        with rasterio.open(output_path, "w", **out_profile) as dst:
            dst.write(binary_mask, 1)

    if job_id:
        update_job(job_id, log_line=f"Mask saved to {output_path}")
