"""
Geospatial utilities: flood statistics, GeoTIFF I/O, overlay PNG generation.
"""

import numpy as np
from typing import Dict, Any


def compute_flood_stats(mask_path: str) -> Dict[str, Any]:
    """
    Compute flood area statistics from a binary mask GeoTIFF.
    
    Returns:
        Dict with total_pixels, flood_pixels, flood_percentage,
        and estimated flood_area_km2 (if pixel size is available).
    """
    import rasterio

    with rasterio.open(mask_path) as src:
        mask = src.read(1)
        transform = src.transform

        total_pixels = int(mask.size)
        flood_pixels = int((mask >= 0.5).sum())
        flood_pct = (flood_pixels / total_pixels * 100) if total_pixels > 0 else 0.0

        # Estimate area: pixel_width * pixel_height in map units (usually meters)
        pixel_w = abs(transform.a)
        pixel_h = abs(transform.e)
        pixel_area_m2 = pixel_w * pixel_h
        flood_area_km2 = flood_pixels * pixel_area_m2 / 1e6

    return {
        "total_pixels": total_pixels,
        "flood_pixels": flood_pixels,
        "flood_percentage": round(flood_pct, 2),
        "flood_area_km2": round(flood_area_km2, 2),
        "pixel_resolution_m": round(pixel_w, 2),
    }


def create_overlay_png(
    raster_path: str,
    mask_path: str,
    output_path: str,
    flood_color: tuple = (0, 100, 255, 150),
):
    """
    Create an overlay PNG showing flood pixels on top of the raster.
    
    The raster's first band is used as a grayscale background.
    Flood pixels are drawn in semi-transparent blue.
    """
    import rasterio
    from PIL import Image

    # Read background (first band)
    with rasterio.open(raster_path) as src:
        band = src.read(1)

    # Normalize to 0-255 for display
    band = np.nan_to_num(band, nan=0.0)
    vmin, vmax = np.percentile(band[band != 0], [2, 98]) if (band != 0).any() else (0, 1)
    if vmax == vmin:
        vmax = vmin + 1
    band_norm = np.clip((band - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)

    # Create RGBA image
    h, w = band_norm.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, 0] = band_norm
    rgba[:, :, 1] = band_norm
    rgba[:, :, 2] = band_norm
    rgba[:, :, 3] = 255

    # Read mask and overlay flood pixels
    with rasterio.open(mask_path) as src:
        mask = src.read(1)

    flood_mask = mask >= 0.5
    rgba[flood_mask, 0] = flood_color[0]
    rgba[flood_mask, 1] = flood_color[1]
    rgba[flood_mask, 2] = flood_color[2]
    rgba[flood_mask, 3] = flood_color[3]

    img = Image.fromarray(rgba, mode="RGBA")
    img.save(output_path, format="PNG")


def read_raster_bands(path: str) -> np.ndarray:
    """Read all bands from a GeoTIFF as a numpy array (bands, H, W)."""
    import rasterio

    with rasterio.open(path) as src:
        return src.read().astype(np.float32)


def write_raster(
    path: str,
    data: np.ndarray,
    reference_path: str,
    dtype: str = "float32",
):
    """
    Write a numpy array as a GeoTIFF, copying CRS and transform
    from a reference raster.
    """
    import rasterio

    with rasterio.open(reference_path) as ref:
        profile = ref.profile.copy()

    if data.ndim == 2:
        data = data[np.newaxis, :, :]

    profile.update(
        count=data.shape[0],
        dtype=dtype,
        height=data.shape[1],
        width=data.shape[2],
    )

    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)


def extract_flood_locations(mask_path: str, max_locations: int = 3) -> list:
    """
    Extract the human-readable names of the flooded locations using reverse geocoding.
    Finds the largest flood clusters, gets their geographic centroids, 
    and uses Geopy to look up the village/city/road names.
    """
    import rasterio
    import rasterio.features
    from geopy.geocoders import Nominatim
    import time
    
    locations = []
    
    with rasterio.open(mask_path) as src:
        mask = src.read(1)
        transform = src.transform

        # We only want flood pixels (>= 0.5)
        flood_mask = mask >= 0.5
        if not flood_mask.any():
            return []

        # Find connected components (polygons) of the flood mask
        shapes = list(rasterio.features.shapes(flood_mask.astype('uint8'), mask=flood_mask, transform=transform))
        
    if not shapes:
        return []

    # Sort shapes by the number of coordinates as a rough proxy for size to get biggest flooded areas
    shapes.sort(key=lambda s: len(s[0]['coordinates'][0]), reverse=True)
    
    geolocator = Nominatim(user_agent="flood_platform_app")
    top_shapes = shapes[:max_locations]
    
    for geom, val in top_shapes:
        coords = geom['coordinates'][0]
        lon = sum(c[0] for c in coords) / len(coords)
        lat = sum(c[1] for c in coords) / len(coords)
        
        try:
            location = geolocator.reverse(f"{lat}, {lon}", exactly_one=True, timeout=5)
            if location and location.raw.get('address'):
                addr = location.raw['address']
                name = addr.get('village') or addr.get('town') or addr.get('city') or addr.get('road') or addr.get('county')
                if name and name not in locations:
                    locations.append(name)
            time.sleep(1) # Rate limiting
        except Exception as e:
            print(f"Geocoding error: {e}")
            continue

    return locations
