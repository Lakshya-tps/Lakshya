import sqlite3
import os

DB_DIR = "database"
DBS = ["users.db", "admins.db"]

for db_name in DBS:
    path = os.path.join(DB_DIR, db_name)
    print(f"\n--- Inspecting {db_name} ---")
    if not os.path.exists(path):
        print(f"File {path} DOES NOT EXIST.")
        continue
        
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        
        # Check tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]
        print(f"Tables: {tables}")
        
        # Check users count
        if 'users' in tables:
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
            print(f"Users Count: {count}")
            
            # Check columns in users
            cur.execute("PRAGMA table_info(users)")
            cols = [row[1] for row in cur.fetchall()]
            print(f"Users Columns: {cols}")
            
        conn.close()
    except Exception as e:
        print(f"Error inspecting {db_name}: {e}")
