# 🚀 वज्रSense (VajraSense) — Production Deployment Guide

This guide covers step-by-step instructions to deploy **वज्रSense** across cloud platforms, container services, and on-premise infrastructure.

---

## 📋 Pre-Deployment Overview

| Component | Specification |
| :--- | :--- |
| **Framework** | Flask 3.x (Python >= 3.10) |
| **Production WSGI** | Gunicorn (Linux/Docker), Waitress (Windows/Cross-platform) |
| **Inference Footprint** | CPU-optimized (~180 MB RAM idle, ~350 MB under active multi-horizon load) |
| **Health Check Endpoint** | `GET /health` or `GET /api/health` (returns HTTP 200) |
| **Default Port** | Configured via `$PORT` environment variable (defaults to `5000`) |
| **Default Host** | `0.0.0.0` (binds to all network interfaces) |

---

## 🌟 Option 1: 1-Click Deployment on Render (Recommended Free/Low-Cost Cloud)

Render provides an automated Web Service environment with free SSL certificates and automatic Git push deployments.

### Steps:
1. Push your repository to **GitHub** or **GitLab**.
2. Log in to [Render.com](https://render.com/) and click **New +** &rarr; **Web Service**.
3. Select your repository `SEMV-Capstone`.
4. Render will automatically detect `render.yaml` or you can configure manually:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
   - **Health Check Path:** `/health`
5. Under **Environment Variables**, optionally set:
   - `CARTO_API_KEY`: `cb1_4qhk_1_857570c78f1776c27331ce8c`
   - `FLASK_ENV`: `production`
   - `PYTHON_VERSION`: `3.11.9`
6. Click **Create Web Service**. Your application will be live at `https://your-app-name.onrender.com`.

---

## 🚆 Option 2: Railway Deployment

Railway supports automatic zero-configuration deployments via Nixpacks and Gunicorn.

### Steps:
1. Go to [Railway.app](https://railway.app/) and click **New Project** &rarr; **Deploy from GitHub repo**.
2. Select your `SEMV-Capstone` repository.
3. Railway will automatically pick up `railway.json` and `Procfile`.
4. In project settings, add a public domain under **Settings** &rarr; **Networking** &rarr; **Generate Domain**.
5. Once built, verify the health status at `https://your-domain.up.railway.app/health`.

---

## 🐳 Option 3: Docker Container Deployment (AWS, GCP, Azure, DigitalOcean)

The repository includes an optimized multi-stage `Dockerfile` with automated container health probes.

### Build and Run Locally:
```bash
# Build the Docker image
docker build -t vajrasense:latest .

# Run the container mapping host port 5000 to container port 5000
docker run -d -p 5000:5000 --name vajrasense-app vajrasense:latest

# Check container health status
docker ps
curl http://localhost:5000/health
```

### Deploy to Google Cloud Run:
```bash
# Authenticate & submit build
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/vajrasense

# Deploy to Cloud Run
gcloud run deploy vajrasense \
  --image gcr.io/YOUR_PROJECT_ID/vajrasense \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --port 5000
```

### Deploy to AWS Lightsail / ECS:
1. Push `vajrasense:latest` to Amazon ECR.
2. Launch a Container Service with image URI, set container port to `5000`, and health check to `/health`.

---

## 🖥️ Option 4: Production Linux VPS (Ubuntu / Debian + Nginx + Systemd)

For dedicated virtual private servers (Linode, DigitalOcean Droplet, Hetzner, AWS EC2):

### 1. Clone & Setup Virtual Environment:
```bash
cd /var/www
git clone https://github.com/your-username/SEMV-Capstone.git vajrasense
cd vajrasense

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Create Systemd Service (`/etc/systemd/system/vajrasense.service`):
```ini
[Unit]
Description=वज्रSense (VajraSense) Convective Nowcasting WSGI Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/vajrasense
Environment="PATH=/var/www/vajrasense/venv/bin"
Environment="PORT=5000"
Environment="HOST=127.0.0.1"
ExecStart=/var/www/vajrasense/venv/bin/gunicorn wsgi:app \
    --bind 127.0.0.1:5000 \
    --workers 3 \
    --threads 4 \
    --timeout 120 \
    --access-logfile /var/log/vajrasense_access.log \
    --error-logfile /var/log/vajrasense_error.log

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vajrasense
sudo systemctl start vajrasense
sudo systemctl status vajrasense
```

### 3. Configure Nginx Reverse Proxy (`/etc/nginx/sites-available/vajrasense`):
```nginx
server {
    listen 80;
    server_name nowcaster.yourdomain.com;

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /static/ {
        alias /var/www/vajrasense/static/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }
}
```

Enable site and install SSL with Certbot:
```bash
sudo ln -s /etc/nginx/sites-available/vajrasense /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d nowcaster.yourdomain.com
```

---

## 🧪 Local Production Verification Test

You can test production serving right on your development machine using **Waitress** (Windows) or **Gunicorn** (Linux/macOS):

```bash
# Windows local production test using Waitress:
$env:USE_WAITRESS="1"; python wsgi.py

# Linux / Mac local production test using Gunicorn:
gunicorn wsgi:app --bind 127.0.0.1:5000 --workers 2
```

Then verify health endpoint in another terminal:
```bash
curl http://127.0.0.1:5000/health
```
Expected output:
```json
{
  "service": "vajrasense-nowcaster",
  "status": "healthy",
  "timestamp": "2026-10-22T02:20:00.000000+00:00",
  "version": "1.0.0"
}
```

---

## 🔒 Security & Performance Best Practices Checklist

- [x] **No Hardcoded Secrets:** Sensitive configurations (e.g. `CARTO_API_KEY`, `SECRET_KEY`) can be overridden via `.env` or cloud environment variables.
- [x] **Production WSGI Server:** Replaced Flask development server with Gunicorn (multithreaded workers) and Waitress.
- [x] **Automated Health Probes:** `/health` and `/api/health` routes return HTTP 200 with JSON status.
- [x] **Clean Model Artifacts:** Pre-trained Random Forest model (`models/vajra_rf_model.joblib`) is under 1MB, ensuring fast deploys without heavy LFS requirements.
- [x] **Dynamic Port Binding:** Reads dynamic `$PORT` assigned by cloud providers.
- [x] **Mobile-Responsive UI:** Full responsive support on desktop, tablets, and smartphones.
