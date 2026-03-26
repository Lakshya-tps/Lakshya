import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB = os.path.join(BASE_DIR, "backend", "database", "users.db")
ADMINS_DB = os.path.join(BASE_DIR, "backend", "database", "admins.db")

def wipe_db(db_path):
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path, timeout=10)
        cur = conn.cursor()
        cur.execute("DELETE FROM users;")
        cur.execute("DELETE FROM verification_logs;")
        conn.commit()
        
        cur.execute("SELECT COUNT(*) FROM users;")
        count = cur.fetchone()[0]
        print(f"Wiped {db_path}. Remaining rows: {count}")
        conn.close()
    else:
        print(f"{db_path} does not exist.")

wipe_db(USERS_DB)
wipe_db(ADMINS_DB)
