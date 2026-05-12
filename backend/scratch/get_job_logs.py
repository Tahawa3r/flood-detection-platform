
import sqlite3
import os

db_path = 'app.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        job_id = '750c422b-2ecd-4fdf-a32d-aaa8b2da3740'
        cursor.execute("SELECT logs, error FROM jobs WHERE id=?", (job_id,))
        row = cursor.fetchone()
        if row:
            print(f"--- Logs for Job {job_id} ---")
            print(row[0])
            if row[1]:
                print(f"\n--- Error ---\n{row[1]}")
        else:
            print(f"Job {job_id} not found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("Database not found.")
