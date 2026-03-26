import os
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROXIES = [
    "https://ghp.ci/",
    "https://ghproxy.net/",
    "https://github.moeyy.xyz/",
    "https://mirror.ghproxy.com/",
    ""
]

def download(base_url, dest):
    print(f"--- Downloading to {dest} ---")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for proxy in PROXIES:
        url = proxy + base_url
        print(f"Trying: {url}...")
        try:
            response = requests.get(url, headers=headers, stream=True, verify=False, timeout=15)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            if total_size < 1000000:
                print("File too small, implies failure or block page. Skipping.")
                continue
                
            block_size = 1024 * 1024 # 1 MB
            downloaded: int = 0
            with open(dest, 'wb') as f:
                for data in response.iter_content(block_size):
                    if data:
                        chunk = bytes(data)
                        f.write(chunk)
                        downloaded = int(downloaded) + len(chunk)
                        print(f"Downloaded {downloaded / 1024 / 1024:.2f} MB", end='\r')
            print(f"\nSUCCESS! {dest} downloaded.")
            return True
        except Exception as e:
            print(f"Failed via {proxy}: {e}")
            
    print(f"\nALL PROXIES FAILED FOR {dest}. You must download this manually from a browser.")
    return False

dest_dir = os.path.join(os.path.expanduser("~"), ".deepface", "weights")
os.makedirs(dest_dir, exist_ok=True)

base_facenet = "https://github.com/serengil/deepface_models/releases/download/v1.0/facenet_weights.h5"
base_fasnet = "https://github.com/serengil/deepface_models/releases/download/v1.0/fasnet_weights.h5"

download(base_facenet, os.path.join(dest_dir, "facenet_weights.h5"))
download(base_fasnet, os.path.join(dest_dir, "fasnet_weights.h5"))
