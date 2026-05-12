
import sqlite3
import os
import shutil
from pathlib import Path

db_path = 'app.db'
models_to_remove = ["UNet-Flood-v1", "UNet-Flood-v2-Trained"]

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        for name in models_to_remove:
            print(f"Checking for model: {name}")
            cursor.execute("SELECT id, weights_path FROM ml_models WHERE name=?", (name,))
            row = cursor.fetchone()
            if row:
                model_id = row[0]
                weights_path = row[1]
                
                # 1. Delete predictions referencing this model
                cursor.execute("DELETE FROM predictions WHERE model_id=?", (model_id,))
                print(f"  Deleted predictions for {name}")
                
                # 2. Delete model from DB
                cursor.execute("DELETE FROM ml_models WHERE id=?", (model_id,))
                print(f"  Deleted model {name} from database")
                
                # 3. Delete weights directory
                if weights_path:
                    weights_dir = Path(weights_path).parent
                    if weights_dir.exists() and "models_registry" in str(weights_dir):
                        shutil.rmtree(weights_dir)
                        print(f"  Deleted weights directory: {weights_dir}")
            else:
                print(f"  Model {name} not found in DB.")
        
        conn.commit()
        print("\nCleanup complete.")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()
else:
    print("Database not found.")
