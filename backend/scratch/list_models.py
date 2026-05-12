
import sqlite3
import os

db_path = 'app.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, config, metrics FROM ml_models")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}")
            print(f"Config: {row[2]}")
            print(f"Metrics: {row[3]}")
            print("-" * 20)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("Database not found.")
