"""
Google Earth Engine service — automated export via the Python API.

Authenticates with the GEE-registered service account, builds a
Sentinel-1 composite, and submits an Export.image.toDrive task
that lands in the user's Google Drive folder automatically.

Falls back to JS script generation if EE auth fails.
"""

import json
import ee
from typing import Dict, Any, Optional

from app.core.config import settings
from app.services.job_service import update_job


_ee_initialized = False


def _init_ee():
    """Initialize the Earth Engine API with the service account credentials."""
    global _ee_initialized
    if _ee_initialized:
        return

    try:
        # Read the email from the service account JSON
        with open(settings.GOOGLE_APPLICATION_CREDENTIALS, "r", encoding="utf-8") as f:
            sa_info = json.load(f)
            client_email = sa_info.get("client_email")

        credentials = ee.ServiceAccountCredentials(
            email=client_email,
            key_file=settings.GOOGLE_APPLICATION_CREDENTIALS,
        )
        ee.Initialize(credentials)
        _ee_initialized = True
    except Exception as exc:
        raise RuntimeError(
            f"Failed to initialize Earth Engine: {exc}\n"
            "Make sure your service account is registered with EE at:\n"
            "https://signup.earthengine.google.com/#!/service_accounts"
        ) from exc


def _build_composite(geojson: Dict[str, Any],
                     start_pre: str, end_pre: str,
                     start_post: str, end_post: str) -> tuple:
    """Build the Sentinel-1 pre/post/diff composite and geometry."""
    geometry = ee.Geometry.Polygon(geojson["coordinates"])

    def get_s1(start: str, end: str):
        return (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(geometry)
            .filterDate(start, end)
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .select("VV")
            .median()
            .clip(geometry)
        )

    pre = get_s1(start_pre, end_pre)
    post = get_s1(start_post, end_post)
    diff = post.subtract(pre).rename("diffVV")

    composite = (
        pre.rename("pre_VV")
        .addBands(post.rename("post_VV"))
        .addBands(diff)
    )
    return composite, geometry


# ── Public API ────────────────────────────────────────────────────


def submit_export_task(
    dataset_id: str,
    geojson: Dict[str, Any],
    start_pre: str,
    end_pre: str,
    start_post: str,
    end_post: str,
    scale: float = 100,
    drive_folder: str = "GEE_Exports",
) -> Dict[str, Any]:
    """
    Submit a GEE export task that writes a GeoTIFF to Google Drive.

    Returns:
        Dict with 'task_id', 'description', 'state' from the started task.
    """
    _init_ee()

    composite, geometry = _build_composite(
        geojson, start_pre, end_pre, start_post, end_post
    )

    description = f"flood_composite_{dataset_id}"

    task = ee.batch.Export.image.toDrive(
        image=composite,
        description=description,
        folder=drive_folder,
        fileNamePrefix=description,
        region=geometry,
        scale=scale,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
    )
    task.start()

    return {
        "task_id": task.id,
        "description": description,
        "state": task.status().get("state", "SUBMITTED"),
    }


def check_task_status(task_id: str) -> Dict[str, Any]:
    """Check the status of a GEE export task."""
    _init_ee()
    tasks = ee.batch.Task.list()
    for t in tasks:
        if t.id == task_id:
            status = t.status()
            return {
                "task_id": task_id,
                "state": status.get("state", "UNKNOWN"),
                "description": status.get("description", ""),
                "error_message": status.get("error_message", ""),
            }
    return {"task_id": task_id, "state": "NOT_FOUND"}


def submit_and_track(
    job_id: str,
    dataset_id: str,
    geojson: Dict[str, Any],
    start_pre: str,
    end_pre: str,
    start_post: str,
    end_post: str,
    scale: float = 100,
):
    """Background task: fetch image directly from GEE and download it."""
    import time
    import requests
    import io
    import zipfile
    from app.services import storage_service

    update_job(job_id, log_line="Initializing Earth Engine...")
    _init_ee()

    update_job(job_id, progress=10.0, log_line="Building composite rules...")
    composite, geometry = _build_composite(
        geojson, start_pre, end_pre, start_post, end_post
    )

    update_job(job_id, progress=20.0, log_line="Requesting direct download URL from Google (this may take a minute)...")
    try:
        url = composite.getDownloadURL({
            'scale': scale,
            'region': geometry,
            'format': 'GEO_TIFF'
        })
        update_job(job_id, progress=50.0, log_line="URL acquired! Downloading massive multi-band TIF...")
    except Exception as exc:
        update_job(job_id, log_line=f"GEE link request failed: {exc}")
        raise RuntimeError(f"Payload too large or EE failed: {exc}")

    # Start Downloading the bytes
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        
        update_job(job_id, progress=75.0, log_line="Extracting GeoTIFF from downloaded package...")
        
        content = r.content
        out_dir = storage_service.raw_dir(dataset_id)
        out_path = out_dir / f"{dataset_id}.tif"
        
        try:
            import zipfile
            import io
            zip_file = zipfile.ZipFile(io.BytesIO(content))
            tif_filename = [name for name in zip_file.namelist() if name.endswith('.tif')][0]
            tif_bytes = zip_file.read(tif_filename)
            update_job(job_id, log_line="Successfully extracted ZIP package")
        except zipfile.BadZipFile:
            update_job(job_id, log_line=f"Not a ZIP file. Assuming raw TIF. First 10 bytes: {content[:10]}")
            tif_bytes = content
        except Exception as e:
            update_job(job_id, log_line=f"Unknown extraction error: {e}")
            tif_bytes = content
            
        with open(out_path, "wb") as f:
            f.write(tif_bytes)
            
        update_job(job_id, progress=100.0, log_line=f"GEE Download successful! File saved natively to {out_path}")
        
    except Exception as exc:
        update_job(job_id, log_line=f"GEE download/extraction failed: {exc}")
        raise RuntimeError(f"Failed to process download: {exc}")


def submit_inference_export(
    prediction_id: str,
    geojson: Dict[str, Any],
    start_pre: str,
    end_pre: str,
    start_post: str,
    end_post: str,
    scale: float = 100,
    drive_folder: str = "GEE_Exports",
) -> Dict[str, Any]:
    """Submit a GEE export for inference raster."""
    _init_ee()

    composite, geometry = _build_composite(
        geojson, start_pre, end_pre, start_post, end_post
    )

    description = f"inference_{prediction_id}"

    task = ee.batch.Export.image.toDrive(
        image=composite,
        description=description,
        folder=drive_folder,
        fileNamePrefix=description,
        region=geometry,
        scale=scale,
        maxPixels=1e13,
        fileFormat="GeoTIFF",
    )
    task.start()

    return {
        "task_id": task.id,
        "description": description,
        "state": task.status().get("state", "SUBMITTED"),
    }


# ── JS fallback (kept for manual workflow) ────────────────────────


def generate_gee_script(
    dataset_id: str,
    geojson: Dict[str, Any],
    start_pre: str,
    end_pre: str,
    start_post: str,
    end_post: str,
    scale: float = 100,
) -> str:
    """Return a GEE JavaScript string (fallback for manual use)."""

    coords_json = json.dumps(geojson["coordinates"])

    script = f"""
// Auto-generated GEE export script for dataset: {dataset_id}
// Paste into https://code.earthengine.google.com/ → Run → Tasks → Run

var geometry = ee.Geometry.Polygon({coords_json});

function getS1(startDate, endDate) {{
  return ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(geometry)
    .filterDate(startDate, endDate)
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .select('VV')
    .median()
    .clip(geometry);
}}

var pre  = getS1('{start_pre}', '{end_pre}');
var post = getS1('{start_post}', '{end_post}');
var diff = post.subtract(pre).rename('diffVV');

var composite = pre.rename('pre_VV')
  .addBands(post.rename('post_VV'))
  .addBands(diff);

Map.centerObject(geometry, 9);
Map.addLayer(diff, {{min: -10, max: 2, palette: ['blue','white','red']}}, 'Diff VV');

Export.image.toDrive({{
  image: composite,
  description: 'flood_composite_{dataset_id}',
  folder: 'GEE_Exports',
  fileNamePrefix: 'flood_composite_{dataset_id}',
  region: geometry,
  scale: {scale},
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
}});
"""
    return script.strip()


def generate_inference_script(
    prediction_id: str,
    geojson: Dict[str, Any],
    start_pre: str,
    end_pre: str,
    start_post: str,
    end_post: str,
    scale: float = 100,
) -> str:
    """Generate a GEE JS script for inference-time export (fallback)."""
    coords_json = json.dumps(geojson["coordinates"])
    script = f"""
// GEE inference export for prediction: {prediction_id}
var geometry = ee.Geometry.Polygon({coords_json});

function getS1(s, e) {{
  return ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(geometry).filterDate(s, e)
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .select('VV').median().clip(geometry);
}}

var pre = getS1('{start_pre}', '{end_pre}');
var post = getS1('{start_post}', '{end_post}');
var diff = post.subtract(pre).rename('diffVV');
var composite = pre.rename('pre_VV').addBands(post.rename('post_VV')).addBands(diff);

Export.image.toDrive({{
  image: composite, description: 'inference_{prediction_id}',
  folder: 'GEE_Exports', fileNamePrefix: 'inference_{prediction_id}',
  region: geometry, scale: {scale}, maxPixels: 1e13, fileFormat: 'GeoTIFF'
}});
"""
    return script.strip()
