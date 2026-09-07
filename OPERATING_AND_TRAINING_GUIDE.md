# Docket — Operating & Training Guide

**Project:** Docket Legal Metrology Compliance System (SIH26034)
**Audience:** Developers, ML/Demo operators, judges running the Grand Finale demo
**Last updated:** 2026-09-07

This guide explains how to:

1. Set up a **new Windows machine** from a fresh Git clone.
2. **Start the application** (Docker path and native path).
3. **Acquire datasets and train the ML models** (classifier, detector, OCR).
4. **Verify** every service is healthy before a demo.

---

## 1. System Requirements & Windows Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Windows | 10/11 64-bit | WSL2 backend enabled for Docker |
| Docker Desktop | 4.30+ | WSL2 backend, ≥8 GB RAM allocated to the VM |
| Git for Windows | any recent | needed for clone |
| Python | **3.12.x** | must match `backend/Dockerfile` (`python:3.12-slim`); see note below |
| Node.js | v22+ (v20 works) | only needed for native frontend dev / builds |
| npm | 10+ | ships with Node 22 |

> **Why Python 3.12, not 3.13?** The pinned scientific stack
> (`numpy==1.26.4`, `asyncpg`, `paddlepaddle`, `torch`) ships prebuilt wheels
> for cp312. On 3.13 pip falls back to **building numpy from source**
> (20–30+ min, frequently fails). Use 3.12 for the venv and the Docker base
> image stays `python:3.12-slim`.

### One-time Git line-ending setup (crucial on Windows)

```bash
git config --global core.autocrlf true
```

This prevents CRLF/LF churn across the whole repo (shell scripts, Dockerfiles
and CI steps all assume LF inside containers).

### Package managers used

- **Python:** `venv` + `pip` (requirements pinned in `backend/requirements.txt`)
- **Node:** `npm` (lockfile in `frontend/`)

---

## 2. Migrating to Another Windows System via Git

### Step 1 — Clone the repository

```cmd
git clone <repository-url> sih26034-legal-metrology
cd sih26034-legal-metrology
```

### Step 2 — Environment configuration

Copy the example env file to `.env` in the **project root** (the same file
feeds every service via `env_file: .env` in `docker-compose.yml`):

```cmd
copy .env.example .env
```

Then edit `.env` and set **real values** for the keys below
(never commit the edited `.env`):

| Variable | Purpose | Example / default |
|---|---|---|
| `POSTGRES_DB` | database name | `legal_metrology` |
| `POSTGRES_USER` | DB user | `app_user` |
| `POSTGRES_PASSWORD` | DB password | strong random string |
| `DATABASE_URL` | async SQLAlchemy DSN | `postgresql+asyncpg://app_user:<pw>@postgres:5432/legal_metrology` |
| `REDIS_URL` | RQ broker | `redis://redis:6379/0` |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | object storage admin | strong random string |
| `S3_ENDPOINT_URL` | MinIO API endpoint | `http://minio:9000` |
| `S3_BUCKET_IMAGES` / `S3_BUCKET_EVIDENCE` / `S3_BUCKET_REPORTS` | buckets (auto-created) | `lm-images`, `lm-evidence`, `lm-reports` |
| `JWT_SECRET_KEY` | token signing key | `openssl rand -hex 32` equivalent, 32+ bytes |
| `JWT_ALGORITHM` | signing alg | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | access token TTL | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | refresh token TTL | `14` |
| `ENVIRONMENT` | app profile | `development` (demo uses the prod image profile) |
| `CORS_ALLOWED_ORIGINS` | frontend origins | `http://localhost:5173` |
| `LOG_LEVEL` | logging | `INFO` |
| `YOLO_MODEL_PATH` | detector artifact | `/models/package_label_detector.onnx` |
| `PRODUCT_CLASSIFIER_PATH` | classifier artifact | `/models/product_classifier.joblib` |
| `PADDLEOCR_LANG` | OCR languages | `en,hi` |

> **Native (non-Docker) runs only:** change the host part of
> `DATABASE_URL` / `S3_ENDPOINT_URL` from `postgres` / `minio` to
> `localhost` because there is no Docker DNS on your host machine.

### Step 3 — Backend virtual environment (optional; only for native runs)

```cmd
py -3.12 -m venv venv
.\venv\Scripts\activate
pip install -r backend\requirements.txt
```

### Step 4 — Frontend dependencies (optional; only for native runs)

```cmd
cd frontend
npm install
cd ..
```

> If you intend to run **everything in Docker** (recommended), Steps 3–4 are
> unnecessary — the images install their own dependencies.

---

## 3. Manually Starting the Application

### Path A — Docker-based startup (recommended)

**A1. Start infrastructure first** (PostgreSQL, Redis, MinIO):

```cmd
docker compose up -d postgres redis minio
```

Wait until `docker compose ps` shows postgres/redis as `(healthy)`.

**A2. Apply database migrations** (Alembic):

```cmd
docker compose run --rm backend alembic upgrade head
```

**A3. Seed reference data** (categories, users, rules, demo dataset):

```cmd
docker compose run --rm backend python -m scripts.seed_categories
docker compose run --rm backend python -m scripts.seed_users
docker compose run --rm backend python -m scripts.seed_rules
docker compose run --rm backend python -m scripts.seed_data
```

**A4. Start the application services:**

```cmd
docker compose up -d backend worker frontend
```

**A5. Verify** — see §5 (Verification Checklist).

### Path B — Native development startup (fast iterate, hot reload)

Terminal 1 — infra via Docker, app natively:

```cmd
docker compose up -d postgres redis minio
```

Terminal 2 — backend (remember the `localhost` DSN change from §2 Step 2):

```cmd
.\venv\Scripts\activate
cd backend
alembic upgrade head
python -m scripts.seed_users
uvicorn app.main:app --reload --port 8000
```

Terminal 3 — RQ worker (async analysis pipeline):

```cmd
.\venv\Scripts\activate
rq worker --url redis://localhost:6379/0 inspection-pipeline
```

Terminal 4 — frontend:

```cmd
cd frontend
npm run dev -- --host
```

### Path C — Grand Finale demo (100% offline)

`docker-compose.demo.yml` runs pre-built production images (frontend served
by nginx on port 80, no volume mounts, no dev servers) so the demo needs
**no network and no package installs** on the presentation machine.
Demo service names differ from dev: `sih-db`, `sih-redis`, `sih-minio`,
`sih-backend`, `sih-frontend`:

```cmd
docker compose -f docker-compose.demo.yml up -d
```

Build the demo images ahead of time on a connected machine:

```cmd
docker compose -f docker-compose.demo.yml build
docker save sih26034-backend sih26034-frontend -o docket-images.tar
```

…and on the offline machine:

```cmd
docker load -i docket-images.tar
docker compose -f docker-compose.demo.yml up -d
```

### Service / port map

| Service | URL / port | Notes |
|---|---|---|
| Backend API | `http://localhost:8000` | Swagger docs at `/docs`, ReDoc at `/redoc` |
| Health probe | `http://localhost:8000/health` | returns `{"status": "ok"}` |
| Frontend (dev) | `http://localhost:5173` | Vite dev server |
| Frontend (demo) | `http://localhost` (port 80) | nginx static build, service `sih-frontend` |
| MinIO API | `http://localhost:9000` | S3-compatible |
| MinIO console | `http://localhost:9001` | login with `MINIO_ROOT_USER/PASSWORD` |
| PostgreSQL | `localhost:5432` | `legal_metrology` database |
| Redis | `localhost:6379` | RQ broker, queue `inspection-pipeline` |

---

## 4. Datasets & ML Model Training

The system has three learned components. Their artifacts live in the repo so
that a fresh clone works out of the box:

| Component | File | Artifact | Trained when? |
|---|---|---|---|
| Product category classifier | `backend/app/services/classification.py` | `backend/ml/models/product_classifier.joblib` | Auto-trains on first classification request if the artifact is missing, then saves it |
| Package/label detector | `backend/app/services/cv_detection.py` | `/models/package_label_detector.onnx` (YOLOv8n exported to ONNX) | Shipped artifact; retrain externally (below) |
| Multilingual OCR | `backend/app/services/ocr_service.py` | PaddleOCR `en` + `hi` models | Downloaded automatically by PaddleOCR on first run (needs network once, then cached in the image) |

### 4.1 Product category classifier (TF-IDF + GradientBoosting)

The baseline trains on the seeded taxonomy of packaged-commodity product
names defined in `classification.py` (categories per prd.md §13.1).

**Retrain / refresh the artifact:**

```cmd
:: from the backend folder (native venv)
python -c "from app.services.classification import _train_model, _save_model; _save_model(_train_model())"
```

Or force the running container to retrain by deleting the artifact and
letting the next request re-train:

```cmd
del backend\ml\models\product_classifier.joblib
```

**Adding your own training data:** extend the seeded `(text, label)` pairs in
`classification.py` (section *Training data*) with real product names per
category, then retrain as above. Keep the 15 taxonomy keys from prd.md §13.1
unchanged — downstream rule applicability depends on them.

**Expectations:** training completes in seconds on CPU (TF-IDF + 100-tree
GradientBoosting); inference is <50 ms per request; confidence <0.6 routes
the product to manual category selection per prd.md §10.4.

### 4.2 Package & label detector (YOLOv8n → ONNX)

The runtime consumes `package_label_detector.onnx` (path from
`YOLO_MODEL_PATH`) and detects package/label regions with a ≥0.5 confidence
threshold, falling back to full-image analysis (`manual_crop_used`) when no
package is found.

**To retrain on your own dataset:**

1. Collect ~200+ photos of packaged commodities with bounding boxes around
   the package and its label; annotate in YOLO format
   (`images/` + `labels/` with `classes.txt`: `0 = package`, `1 = label`).
2. Train with Ultralytics (can be done on any machine with GPU or CPU):
   ```bash
   pip install ultralytics
   yolo detect train data=dataset.yaml model=yolov8n.pt imgsz=640 epochs=50
   ```
3. Export to ONNX and drop it in the location `YOLO_MODEL_PATH` points to:
   ```bash
   yolo export model=runs/detect/train/weights/best.pt format=onnx
   ```
4. Restart the backend so the new model is loaded.

**Datasets to start from (public, legal to use for research):**

- **Roboflow Universe** — search "package detection" / "product label";
  many LMPC-style packaged-goods sets can be exported directly in YOLO format.
- **COCO** subset — `bottle`, `cup`, `box` classes give a weak baseline that
  can be fine-tuned with your own labeled photos.
- **Self-captured set** — 50–100 phone photos of real packaged commodities
  (net weight, MRP, unit name visible) annotated with CVAT
  (https://www.cvat.ai) or Roboflow Annotate gives the best domain match.

### 4.3 OCR models (PaddleOCR, English + Hindi)

No manual training is required. `ocr_service.py` initializes PaddleOCR with
`en` and `hi` models, angle classification enabled, 2–4× bicubic upscaling
for small fonts, and filters results <0.5 confidence
(per prd.md §11.2–11.3, §10.4).

- **First run online:** PaddleOCR fetches the model files once and caches
  them in `~/.paddleocr` (Docker: baked into the image layer after first run —
  commit a cached layer for offline demos, or pre-download on the demo box).
- **Fine-tuning (optional, advanced):** PaddleOCR fine-tuning needs the
  PaddleOCR repo toolchain and text-line datasets (e.g., ICDAR-style crops +
  synthetic Hindi label renders). Only pursue this if baseline accuracy on
  real Indian labels is insufficient — the MVP scope explicitly uses the
  pretrained models.

---

## 5. Verification Checklist (run before any demo)

```cmd
:: 1. All six containers up
docker compose ps

:: 2. Backend healthy (JWT/CORS/audit middleware loaded)
curl http://localhost:8000/health

:: 3. API docs render
start http://localhost:8000/docs

:: 4. Frontend loads
start http://localhost:5173

:: 5. MinIO console shows the 3 buckets (lm-images, lm-evidence, lm-reports)
start http://localhost:9001

:: 6. Worker consumes the pipeline queue
docker compose logs worker --tail 20
```

Expected: postgres/redis `healthy`, backend serving `/health` →
`{"status": "ok", "environment": ...}`, frontend renders the login page,
MinIO console lists the three buckets, worker log shows
`*** Listening on inspection-pipeline...`.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pip` builds numpy from source for ages | Python 3.13 venv (no cp313 wheels) | Recreate venv with Python 3.12 |
| Backend exits: `no such table` / migration errors | Migrations not applied | `docker compose run --rm backend alembic upgrade head` |
| `401` from every API call in the frontend | `JWT_SECRET_KEY` changed after tokens were issued / CORS origin mismatch | Re-login; check `CORS_ALLOWED_ORIGINS` includes the frontend origin exactly |
| MinIO bucket errors on upload | Buckets not initialized | Backend creates them on startup; restart `backend` once MinIO is healthy |
| Worker idle, inspections stuck in `processing` | RQ worker not running | `docker compose up -d worker`; check `docker compose logs worker` |
| OCR very slow on first request | Model files downloading | Pre-warm once online, or bake models into the image |
| `docker compose up` says container name already in use | Stale container from a killed run | `docker compose down --remove-orphans`, then retry |
| Docker build stalls at pip install | Network flake or huge wheels (paddle/torch ~1.5 GB) | Retry; if repeated stalls, `docker builder prune --all --force` (reclaim cache) and rebuild |
| Port already in use (5432/6379/8000/5173) | Local service occupying the port | Stop the local service or change the host-side mapping in `docker-compose.yml` |

---

## 7. Quick Reference — Day-to-day Commands

```cmd
:: start everything
docker compose up -d

:: stop (keeps data volumes)
docker compose down

:: stop and wipe data (fresh start)
docker compose down -v

:: tail logs
docker compose logs -f backend worker

:: run the backend test suite (540 tests)
docker compose run --rm backend pytest tests/ -q

:: frontend type-check + tests
cd frontend && npm run type-check && npm test
```

**State files to keep in sync while developing:** `master.md` (navigation &
protocols), `todo.md` (task roadmap), `current_progress.md` (changelog).
Read them before starting a task; update them at the end of every task.
