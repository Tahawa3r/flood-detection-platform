
import sqlite3
import os
from datetime import datetime

db_path = 'app.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        print("--- Active/Recent Predictions ---")
        cursor.execute("SELECT id, status, data_source, created_at, updated_at FROM predictions ORDER BY created_at DESC LIMIT 10")
        for row in cursor.fetchall():
            print(f"ID: {row[0]}, Status: {row[1]}, Source: {row[2]}")
            print(f"  Created: {row[3]}")
            print(f"  Updated: {row[4]}")
        
        print("\n--- Active/Recent Jobs ---")
        cursor.execute("SELECT id, type, status, progress, error, created_at, updated_at FROM jobs ORDER BY created_at DESC LIMIT 10")
        for row in cursor.fetchall():
            print(f"ID: {row[0]}, Type: {row[1]}, Status: {row[2]}, Progress: {row[3]}%")
            print(f"  Created: {row[5]}")
            print(f"  Updated: {row[6]}")
            if row[4]: print(f"  Error: {row[4]}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("Database not found.")
