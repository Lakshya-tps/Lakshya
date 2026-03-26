import subprocess
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(BASE_DIR, "server_debug.log")

print(f"Starting server and logging to {log_file}...")

with open(log_file, "w") as f:
    process = subprocess.Popen(
        ["python", "backend/app.py"],
        stdout=f,
        stderr=subprocess.STDOUT,
        cwd=BASE_DIR
    )
    time.sleep(15) # Wait for it to crash or start
    if process.poll() is not None:
        print(f"Process exited with code {process.returncode}")
    else:
        print("Process is still running.")
