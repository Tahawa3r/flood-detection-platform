"""
Generate a valid UNet weights file and register it in the DB.
This creates an untrained model with random weights that can still run inference.
"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import torch
from app.ml.models.unet import UNet
from app.db.database import SessionLocal
from app.db import models as db_models
from app.services import storage_service

def setup():
    db = SessionLocal()
    try:
        # Delete old broken model records
        old_models = db.query(db_models.MLModel).all()
        for m in old_models:
            print(f"Removing old model record: {m.id} ({m.name})")
            # Delete predictions referencing this model first
            db.query(db_models.Prediction).filter(
                db_models.Prediction.model_id == m.id
            ).delete()
            db.delete(m)
        db.commit()

        # Create a fresh UNet with proper architecture
        in_channels = 3
        base_filters = 32
        model = UNet(in_channels=in_channels, base_filters=base_filters)
        
        # Generate model ID and create directory
        import uuid
        model_id = str(uuid.uuid4())
        dest_dir = storage_service.model_dir(model_id)
        weights_path = str(dest_dir / "weights.pt")
        
        # Save the state_dict
        torch.save(model.state_dict(), weights_path)
        file_size = os.path.getsize(weights_path)
        print(f"Saved weights to {weights_path} ({file_size:,} bytes)")
        
        # Verify it loads correctly
        test_model = UNet(in_channels=in_channels, base_filters=base_filters)
        test_model.load_state_dict(torch.load(weights_path, map_location="cpu"))
        test_model.eval()
        
        # Quick forward pass test
        dummy_input = torch.randn(1, in_channels, 256, 256)
        with torch.no_grad():
            output = test_model(dummy_input)
        print(f"Forward pass test: input {dummy_input.shape} -> output {output.shape}")
        assert output.shape == (1, 1, 256, 256), f"Unexpected output shape: {output.shape}"
        print("Model verification passed!")
        
        # Register in DB
        ml_model = db_models.MLModel(
            id=model_id,
            name="UNet-Flood-v1",
            weights_path=weights_path,
            config={"in_channels": in_channels, "base_filters": base_filters},
            metrics={},
        )
        db.add(ml_model)
        db.commit()
        db.refresh(ml_model)
        
        print(f"\nModel registered successfully!")
        print(f"  ID:           {ml_model.id}")
        print(f"  Name:         {ml_model.name}")
        print(f"  Weights:      {ml_model.weights_path}")
        print(f"  Config:       {ml_model.config}")
        print(f"  File size:    {file_size:,} bytes")
        
    finally:
        db.close()

if __name__ == "__main__":
    setup()
