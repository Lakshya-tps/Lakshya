# Lakshya Test 1 — Deploy to Render from Docker Hub

This README contains the exact commands and Render steps to push the Docker image and deploy the app so it's publicly accessible.

Important: Docker Hub image names must be lowercase. This project uses `ganeshkunche/version1`.

1) Build the image locally (after making changes):

```bash
docker build -t lakshya-test1:local .
```

2) Tag the image for Docker Hub and push (image used in `render.yaml`):

```bash
# replace ganeshkunche/version1 with your Docker Hub repo if different
docker tag lakshya-test1:local ganeshkunche/version1:latest
docker login
docker push ganeshkunche/version1:latest
```

3) Render — create service from Docker image

- Go to Render → New → Web Service → Deploy from Docker Image.
- Set Image: `ganeshkunche/version1:latest` and Port: `5001`.
- Advanced → add a Persistent Disk:
  - Name: `lakshya-data`
  - Size: `1 GB` (or larger)
  - Mount path: `/app/data`
- Enable Auto-deploy on new image versions.

4) Render — set environment variables (Service → Environment):

- `PORT` = `5001`
- `SMTP_HOST` = `smtp.gmail.com`
- `SMTP_PORT` = `587`
- `SMTP_USER` = (your SMTP user) — mark as secret
- `SMTP_PASSWORD` = (your SMTP password/token) — mark as secret
- `NOTIFICATION_EMAIL` = (notification address)

5) Verify deployment

- Open the Render service URL shown in the dashboard (public). Use `curl -I https://<render-url>` to check response.
- Submit a form and check that `data/*.csv` appears under `/app/data` in Render after a restart.

Notes about the public URL

- Render will generate a default URL based on the service name. The service name in `render.yaml` is `lakshya-version1` so the default URL will be `https://lakshya-version1.onrender.com`.
