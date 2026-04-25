"""
Local GPU training service.
Trains the U-Net on prepared patches using PyTorch CUDA.
Reports progress via the job service.
"""

import os
import uuid
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from app.services.job_service import update_job
from app.services import storage_service
from app.ml.models.unet import UNet
from app.db.database import SessionLocal
from app.db import models as db_models


class FloodPatchDataset(Dataset):
    """PyTorch dataset wrapping NumPy patch arrays."""

    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.from_numpy(X).float()
        self.y = torch.from_numpy(y).unsqueeze(1).float()

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


def train_model(
    job_id: str,
    dataset_id: str,
    model_name: str = "UNet-flood",
    epochs: int = 50,
    batch_size: int = 8,
    learning_rate: float = 1e-3,
    base_filters: int = 32,
):
    """
    Background task: train a U-Net on prepared patches.

    1. Loads train_X.npy / train_y.npy from data/processed/{dataset_id}/
    2. Trains with BCELoss + Adam on CUDA (falls back to CPU)
    3. Saves weights.pt to models_registry/
    4. Registers the model in the database
    """
    processed = storage_service.processed_dir(dataset_id)

    train_x_path = str(processed / "train_X.npy")
    train_y_path = str(processed / "train_y.npy")

    if not os.path.isfile(train_x_path) or not os.path.isfile(train_y_path):
        update_job(job_id, log_line=f"Training data not found in {processed}")
        raise FileNotFoundError(
            f"Run dataset preparation first (POST /datasets/{dataset_id}/prepare)"
        )

    # Load data
    update_job(job_id, log_line="Loading training data...", progress=5.0)
    X_train = np.load(train_x_path)
    y_train = np.load(train_y_path)
    update_job(job_id, log_line=f"  X_train shape: {X_train.shape}  y_train shape: {y_train.shape}")

    in_channels = X_train.shape[1]

    # Load validation data if exists
    val_x_path = str(processed / "val_X.npy")
    val_y_path = str(processed / "val_y.npy")
    has_val = os.path.isfile(val_x_path) and os.path.isfile(val_y_path)
    if has_val:
        X_val = np.load(val_x_path)
        y_val = np.load(val_y_path)
        update_job(job_id, log_line=f"  X_val shape: {X_val.shape}")

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    update_job(job_id, log_line=f"Training on: {device}")
    if device.type == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1e9
        update_job(job_id, log_line=f"  GPU: {gpu_name} ({gpu_mem:.1f} GB)")

    # Model
    model = UNet(in_channels=in_channels, base_filters=base_filters).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.BCELoss()

    train_dataset = FloodPatchDataset(X_train, y_train)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True,
                              num_workers=0, pin_memory=True)

    update_job(job_id, log_line=f"Starting training: {epochs} epochs, batch_size={batch_size}, lr={learning_rate}")
    update_job(job_id, progress=10.0)

    best_loss = float("inf")
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)

            pred = model(xb)
            loss = loss_fn(pred, yb)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        avg_train_loss = epoch_loss / max(n_batches, 1)

        # Validation
        val_info = ""
        if has_val:
            model.eval()
            with torch.no_grad():
                val_ds = FloodPatchDataset(X_val, y_val)
                val_loader = DataLoader(val_ds, batch_size=batch_size, num_workers=0)
                val_loss = 0.0
                val_n = 0
                for xb, yb in val_loader:
                    xb, yb = xb.to(device), yb.to(device)
                    pred = model(xb)
                    val_loss += loss_fn(pred, yb).item()
                    val_n += 1
                avg_val_loss = val_loss / max(val_n, 1)
                val_info = f"  val_loss={avg_val_loss:.4f}"

        if avg_train_loss < best_loss:
            best_loss = avg_train_loss
            best_epoch = epoch

        progress = 10 + (epoch / epochs) * 80
        if epoch % max(1, epochs // 20) == 0 or epoch == epochs:
            update_job(
                job_id, progress=progress,
                log_line=f"Epoch {epoch}/{epochs}  train_loss={avg_train_loss:.4f}{val_info}"
            )

    update_job(job_id, log_line=f"Best train loss: {best_loss:.4f} at epoch {best_epoch}")

    # Save & register model
    model_id = str(uuid.uuid4())
    dest_dir = storage_service.model_dir(model_id)
    weights_path = str(dest_dir / "weights.pt")
    torch.save(model.state_dict(), weights_path)
    update_job(job_id, log_line=f"Weights saved to {weights_path}", progress=95.0)

    # Register in DB
    db = SessionLocal()
    try:
        ml_model = db_models.MLModel(
            id=model_id,
            name=model_name,
            weights_path=weights_path,
            config={"in_channels": in_channels, "base_filters": base_filters},
            metrics={
                "best_train_loss": round(best_loss, 6),
                "best_epoch": best_epoch,
                "total_epochs": epochs,
            },
        )
        db.add(ml_model)
        db.commit()
        update_job(job_id, log_line=f"Model registered: {model_id} ({model_name})")
    finally:
        db.close()

    update_job(job_id, progress=100.0, log_line="Training complete!")
