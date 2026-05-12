import sys
import os
from pathlib import Path
import requests

# Add backend directory to path
backend_dir = Path(os.getcwd())
sys.path.append(str(backend_dir))

from app.services import gee_service
from app.services import predict_service
import json

# Dummy region (Morocco/Casablanca or somewhere)
geojson = {
  "type": "Polygon",
  "coordinates": [
    [
      [-7.7, 33.5],
      [-7.7, 33.6],
      [-7.5, 33.6],
      [-7.5, 33.5],
      [-7.7, 33.5]
    ]
  ]
}

try:
    print("Initializing EE...")
    gee_service._init_ee()
    print("EE Initialized.")
    
    print("Building composite...")
    composite, geometry = gee_service._build_composite(
        geojson,
        "2024-01-01", "2024-01-15",
        "2024-01-16", "2024-01-30"
    )
    
    print("Requesting download URL...")
    url = composite.getDownloadURL({
        'scale': 100,
        'region': geometry,
        'format': 'GEO_TIFF'
    })
    print(f"Success! URL: {url}")

    print("Downloading...")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    print("Downloaded!")

    content = r.content
    print(f"Content length: {len(content)}")

    tif_bytes = None
    try:
        import zipfile
        import io
        zip_file = zipfile.ZipFile(io.BytesIO(content))
        print("Zip contents:", zip_file.namelist())
        tif_filename = [name for name in zip_file.namelist() if name.endswith('.tif')][0]
        tif_bytes = zip_file.read(tif_filename)
        print("Extracted TIF successfully")
    except zipfile.BadZipFile:
        print("Not a ZIP file. Assuming raw TIF.")
        tif_bytes = content
    except Exception as e:
        print(f"Extraction error: {e}")
        tif_bytes = content

    out_path = "test.tif"
    with open(out_path, "wb") as f:
        f.write(tif_bytes)
        
    print(f"Validating raster {out_path}...")
    try:
        predict_service.validate_raster(out_path)
        print("Raster is valid!")
    except Exception as e:
        print(f"Validation failed: {e}")

except Exception as e:
    print(f"Error occurred: {e}")
