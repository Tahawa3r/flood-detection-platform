import numpy as np
import os
from pathlib import Path

# Create a dummy dataset ID
dataset_id = "dummy_train_dataset"
processed_dir = Path(r"c:\Users\tahaa\OneDrive\Desktop\flood-project\backend\data\processed") / dataset_id
os.makedirs(processed_dir, exist_ok=True)

# Generate dummy data (N, C, H, W)
N = 16
C = 3
H, W = 256, 256

X = np.random.rand(N, C, H, W).astype(np.float32)
y = np.random.randint(0, 2, (N, H, W)).astype(np.float32)

# Split 80/20
n_train = int(0.8 * N)

np.save(str(processed_dir / "train_X.npy"), X[:n_train])
np.save(str(processed_dir / "train_y.npy"), y[:n_train])
np.save(str(processed_dir / "val_X.npy"), X[n_train:])
np.save(str(processed_dir / "val_y.npy"), y[n_train:])

print(f"Dummy dataset created at {processed_dir}")
print(f"X_train shape: {X[:n_train].shape}")
print(f"y_train shape: {y[:n_train].shape}")
