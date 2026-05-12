import sys
import os
import time
import requests
from pathlib import Path

backend_url = "http://127.0.0.1:8000"

def test_prediction():
    print("Fetching models...")
    models_res = requests.get(f"{backend_url}/models")
    if not models_res.ok:
        print("Models failed", models_res.text)
        return
    
    models = models_res.json()
    if not models:
        print("No models available")
        return
        
    model_id = models[0]['id']
    print(f"Using model {model_id}")

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
    
    payload = {
        "model_id": model_id,
        "region_id": "test_region_1",
        "region_geojson": geojson,
        "start_pre": "2024-01-01",
        "end_pre": "2024-01-15",
        "start_post": "2024-01-16",
        "end_post": "2024-01-30"
    }
    
    print("Submitting prediction...")
    pred_res = requests.post(f"{backend_url}/predictions/", json=payload)
    if not pred_res.ok:
        print("Prediction failed", pred_res.text)
        return
        
    pred_data = pred_res.json()
    pred_id = pred_data['prediction_id']
    print(f"Prediction started! ID: {pred_id}")
    
    while True:
        status_res = requests.get(f"{backend_url}/predictions/{pred_id}/results")
        if status_res.ok:
            data = status_res.json()
            print(f"Status: {data.get('status')} - {data.get('message')}")
            if data.get('status') in ['completed', 'error', 'failed', 'fallback_completed', 'upgraded']:
                print(data)
                break
        time.sleep(2)

if __name__ == "__main__":
    test_prediction()
