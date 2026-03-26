import os
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download(url, dest):
    print(f"Downloading {url} to {dest}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers, stream=True, verify=False)
    response.raise_for_status()
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024 * 1024 # 1 MB
    downloaded: int = 0
    with open(dest, 'wb') as f:
        for data in response.iter_content(block_size):
            if data:
                chunk = bytes(data)
                f.write(chunk)
                downloaded = int(downloaded) + len(chunk)
                print(f"Downloaded {downloaded / 1024 / 1024:.2f} MB / {total_size / 1024 / 1024:.2f} MB", end='\r')
    print(f"\n{dest} Download Done!")

dest_dir = os.path.join(os.path.expanduser("~"), ".deepface", "weights")
os.makedirs(dest_dir, exist_ok=True)

download("https://github.com/serengil/deepface_models/releases/download/v1.0/facenet_weights.h5", os.path.join(dest_dir, "facenet_weights.h5"))
download("https://github.com/serengil/deepface_models/releases/download/v1.0/fasnet_weights.h5", os.path.join(dest_dir, "fasnet_weights.h5"))
