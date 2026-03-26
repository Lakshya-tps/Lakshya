import sys
import os
import traceback

# Ensure backend directory is in the path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "backend"))

from database import init_db, ADMIN_DB_PATH, DB_PATH

log_path = os.path.join(BASE_DIR, "debug_init.log")

with open(log_path, "w") as f:
    f.write("Starting manual database initialization...\n")
    try:
        f.write(f"ADMIN_DB_PATH: {os.path.abspath(ADMIN_DB_PATH)}\n")
        f.write(f"DB_PATH: {os.path.abspath(DB_PATH)}\n")
        init_db()
        f.write("Initialization finished successfully.\n")
        
        if os.path.exists(ADMIN_DB_PATH):
            f.write(f"SUCCESS: {ADMIN_DB_PATH} was created.\n")
        else:
            f.write(f"FAILURE: {ADMIN_DB_PATH} was NOT created.\n")
            
    except Exception as e:
        f.write("An error occurred during initialization:\n")
        f.write(traceback.format_exc())
