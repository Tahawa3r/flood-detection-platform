
import sqlite3
import uuid
from datetime import datetime, timezone

db_path = r'C:\Users\tahaa\flood_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables if not exist (though Base.metadata should do it)
cursor.execute('''CREATE TABLE IF NOT EXISTS ml_models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    weights_path TEXT,
    config TEXT,
    metrics TEXT,
    created_at DATETIME
)''')

# Register models
models = [
    ("d3e79f0b-aa1a-4c57-ad73-a86c57cfcf75", "UNet-Flood-v2-FineTuned", r"C:\Users\tahaa\flood_platform_models\d3e79f0b-aa1a-4c57-ad73-a86c57cfcf75\weights.pt"),
    ("77f189b4-ad14-4705-9a2c-177294644c3a", "UNet-Flood-Final", r"C:\Users\tahaa\flood_platform_models\77f189b4-ad14-4705-9a2c-177294644c3a\weights.pt")
]

for m_id, name, path in models:
    cursor.execute("INSERT OR REPLACE INTO ml_models (id, name, weights_path, created_at) VALUES (?, ?, ?, ?)",
                   (m_id, name, path, datetime.now(timezone.utc)))

conn.commit()
conn.close()
print("Models registered in new DB.")
