# ClauseGuard Deployment Guide

This document provides step-by-step production deployment instructions for **ClauseGuard: AI Contract Risk Analyzer**.

---

## 1. System Overview & Deployment Architecture

```
                      ┌──────────────────────────────────────────────┐
                      │               Client Browser                 │
                      └──────────────────────┬───────────────────────┘
                                             │
                       HTTPS / REST API      │ Static SPA Assets
                                             ▼
        ┌────────────────────────────────────┬────────────────────────────────────┐
        │                                    │                                    │
        ▼                                    ▼                                    ▼
┌───────────────────────────────┐  ┌───────────────────────────────┐  ┌───────────────────────────────┐
│     Option 1: Railway/Render  │  │   Option 2: Vercel/Netlify    │  │ Option 3: HF Spaces (Docker)  │
│  FastAPI Backend (CPU PyTorch)│  │     React Vite Frontend       │  │ All-In-One Unified Container  │
│  + Managed PostgreSQL 16      │  │     (Static edge CDN)         │  │ (Free CPU Tier, Port 7860)    │
└───────────────────────────────┘  └───────────────────────────────┘  └───────────────────────────────┘
```

---

## 2. Environment Variables Reference

| Variable | Description | Example / Default | Required In |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://clauseguard:pass@db:5432/clauseguard` | Backend |
| `MODEL_PATH` | Path to fine-tuned Legal-BERT weights | `ml/artifacts/legal_bert` or `/app/model_artifacts/legal_bert` | Backend |
| `LABEL_MAP_PATH` | Path to label mapping JSON | `ml/artifacts/label_map.json` or `/app/model_artifacts/label_map.json` | Backend |
| `METRICS_PATH` | Path to evaluated metrics JSON | `ml/artifacts/metrics.json` or `/app/model_artifacts/metrics.json` | Backend |
| `SBERT_MODEL` | Hugging Face repo for sentence embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Backend |
| `MAX_FILE_SIZE_MB` | Maximum allowed file upload size | `10` | Backend |
| `LOG_LEVEL` | Python logging verbosity | `INFO` | Backend |
| `CORS_ORIGINS` | Comma-separated allowed origins | `https://clauseguard.vercel.app,http://localhost:3000` | Backend |
| `VITE_API_URL` | Base URL of deployed backend API | `https://api-clauseguard.up.railway.app` | Frontend |

---

## 3. Option A: Railway / Render (Backend + PostgreSQL)

### Railway Deployment (Recommended for Backend + DB)

1. **Create a Railway Project**:
   - Sign in to [Railway](https://railway.app/).
   - Click **New Project** -> **Provision PostgreSQL**.

2. **Deploy the Backend Service**:
   - In the same project, click **New Service** -> **GitHub Repo** -> select `clauseguard`.
   - Set **Root Directory** to `/` or `/backend`.
   - Railway will detect the `backend/Dockerfile`.

3. **Configure Environment Variables in Railway**:
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}` (Railway reference variable).
   - `MODEL_PATH`: `/app/model_artifacts/legal_bert` (or include weights in repo artifact storage).
   - `LABEL_MAP_PATH`: `/app/model_artifacts/label_map.json`.
   - `METRICS_PATH`: `/app/model_artifacts/metrics.json`.
   - `SBERT_MODEL`: `sentence-transformers/all-MiniLM-L6-v2`.
   - `CORS_ORIGINS`: `https://your-frontend-domain.vercel.app,http://localhost:3000`.
   - `PORT`: `8000`.

4. **Health Check Configuration**:
   - Path: `/api/v1/health`.
   - Timeout: 10s.

---

## 4. Option B: Vercel / Netlify (Frontend)

### Vercel Deployment

1. **Import Repository**:
   - Go to [Vercel Dashboard](https://vercel.com/) -> **Add New** -> **Project**.
   - Select the `clauseguard` repository.

2. **Configure Build Settings**:
   - **Framework Preset**: `Vite`.
   - **Root Directory**: `frontend`.
   - **Build Command**: `npm run build`.
   - **Output Directory**: `dist`.

3. **Set Environment Variables**:
   - `VITE_API_URL`: Your deployed backend URL (e.g., `https://api-clauseguard.up.railway.app`).

4. **SPA Client Routing**:
   - Ensure `frontend/vercel.json` exists for client-side routing fallback:
   ```json
   {
     "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
   }
   ```

---

## 5. Option C: Hugging Face Spaces (Free Docker Demo)

Hugging Face Spaces provides 16 GB RAM and 2 vCPUs on the free tier, ideal for demonstration purposes.

1. Create a new Space on [Hugging Face](https://huggingface.co/spaces) with **SDK: Docker**.
2. Set Space Port: Hugging Face Spaces routes traffic to port **7860**.
3. Create `Dockerfile` at root:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   RUN apt-get update && apt-get install -y --no-install-recommends gcc curl && rm -rf /var/lib/apt/lists/*
   COPY backend/requirements.txt .
   RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
       pip install --no-cache-dir -r requirements.txt
   COPY backend/app ./app
   COPY ml/artifacts ./ml/artifacts
   ENV DATABASE_URL="sqlite:///./clauseguard.db"
   ENV MODEL_PATH="ml/artifacts/legal_bert"
   ENV LABEL_MAP_PATH="ml/artifacts/label_map.json"
   ENV METRICS_PATH="ml/artifacts/metrics.json"
   EXPOSE 7860
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
   ```

---

## 6. Option D: Local Docker Compose (One-Command Run)

For local or self-hosted virtual machines (AWS EC2, DigitalOcean Droplet, GCP Compute Engine):

### Prerequisites
- Docker Engine 24.0+
- Docker Compose v2.20+

### Steps
```bash
# 1. Clone repository
git clone https://github.com/your-username/clauseguard.git
cd clauseguard

# 2. Start all services (Database, Backend API, Frontend Nginx)
docker compose up --build -d

# 3. Verify services are healthy
docker compose ps

# 4. Access the application
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# API Docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/api/v1/health

# 5. Stop services
docker compose down -v
```
