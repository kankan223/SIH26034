# Technology Stack — SIH26034
**Legal Metrology Packaged-Commodities Compliance Platform**

Companion to `prd.md` (§6–§7, §44) and `design.md`. This document is the single source of truth for exact versions, libraries, and configuration choices — a developer or AI coding agent should be able to run `docker compose up` against the manifests in §17 with no further decisions to make.

---

## 1. How to Use This Document

`prd.md` §7 named the stack and gave the one-paragraph rationale per layer. This document goes one level deeper: pinned version lines, the full dependency list per service, why each *specific* library (not just each *category*) was chosen over its alternatives, licensing, environment configuration, and copy-pasteable manifests. Where `prd.md` and this document could drift, `prd.md` §7's technology choices are authoritative — this document elaborates them, it does not override them.

---

## 2. Stack at a Glance

| Layer | Choice | Version line |
|---|---|---|
| Frontend framework | React + Vite + TypeScript | React 18.x, Vite 5.x, TS 5.x |
| Frontend styling | Tailwind CSS | 3.x |
| Frontend state/data | TanStack Query + Zustand | Query 5.x, Zustand 4.x |
| Backend framework | FastAPI | 0.11x on Python 3.13 |
| Backend runtime | Python | 3.13.x |
| ORM / migrations | SQLAlchemy 2.x + Alembic | SQLAlchemy 2.0.x, Alembic 1.13.x |
| Job queue | Redis + RQ | Redis 7.x, RQ 1.16.x |
| Computer vision | OpenCV + Ultralytics YOLOv8 | opencv-python 4.10.x, ultralytics 8.3.x |
| OCR | PaddleOCR (PP-OCRv4) | PaddleOCR 2.8.x / PaddlePaddle 2.6.x |
| Classical ML | scikit-learn | 1.5.x |
| Database | PostgreSQL | 17.x |
| Object storage | MinIO | RELEASE.2024-xx (S3-compatible, self-hosted) |
| Auth | JWT via `python-jose` + `passlib[bcrypt]` | jose 3.3.x, passlib 1.7.x |
| Reports | WeasyPrint + Jinja2 | WeasyPrint 62.x, Jinja2 3.1.x |
| Reverse proxy | Nginx | 1.27.x |
| Containerization | Docker + Docker Compose | Compose spec 3.9 |
| CI | GitHub Actions | — |
| Testing (backend) | pytest + httpx | pytest 8.x, httpx 0.27.x |
| Testing (frontend) | Vitest + React Testing Library + Playwright | latest stable |
| Load testing | Locust | 2.29.x |
| Logging | `structlog` (JSON) | 24.x |

---

## 3. Architecture-to-Stack Mapping

Cross-referenced to the component diagram in `prd.md` §6.

| `prd.md` §6 component | Implemented as |
|---|---|
| Client (Web/PWA) | React + Vite SPA, `vite-plugin-pwa` for installability/offline queueing (§27) |
| API Gateway | FastAPI app, single process, routers per domain (`auth`, `inspections`, `rules`, `dashboard`) |
| Inspection Service | FastAPI router + SQLAlchemy models, no separate process in MVP (see §16.1 for why) |
| Auth Service | FastAPI router + `python-jose`/`passlib`, same process |
| Job Queue | Redis + RQ workers (separate container) |
| Image Processing | OpenCV, invoked inside an RQ worker task |
| OCR Service | PaddleOCR, invoked inside the same worker task (in-process call, not a network hop, to avoid unnecessary latency at hackathon scale) |
| CV/Detection | Ultralytics YOLOv8, ONNX-exported for inference, invoked in-process in the worker |
| Information Extraction | Pure Python (regex + `python-dateutil`), in-process |
| Product Classification | scikit-learn `Pipeline` (TF-IDF + GradientBoosting), loaded once at worker startup, in-process |
| Font/Layout Analysis | OpenCV geometry calculations, in-process |
| Rule Engine | Python module reading `rule_versions.content` (JSONB) from Postgres, in-process |
| Compliance Engine | Python module, in-process |
| Evidence Engine | Pillow (crop generation) + boto3/MinIO client (upload), in-process |
| PostgreSQL | PostgreSQL 17.x container |
| Object Storage | MinIO container, S3 API via `boto3` |
| Report Generator | WeasyPrint + Jinja2 HTML templates, invoked on `/inspections/{id}/submit` |
| Analytics/Dashboard | SQL aggregate queries (materialized views, refreshed via a scheduled RQ job) |
| Logging/Monitoring/Audit | `structlog` → stdout (Compose log driver); `audit_logs` table for the application-level audit trail (distinct from infra logs) |

---

## 4. Frontend Stack (Detail)

| Concern | Library | Why this one, not an alternative |
|---|---|---|
| Framework | **React 18.x** | Largest hackathon-relevant ecosystem/StackOverflow coverage for a 6-person student team; concurrent features (`useTransition`) genuinely help here — the Processing Screen (`prd.md` §22, page 5) polls a job status without janking the UI. |
| Build tool | **Vite 5.x** | Sub-second HMR versus Create React App's (deprecated) or webpack's slower rebuild loop; native TS support; trivial PWA plugin integration. Next.js was considered and rejected in `prd.md` §7 — this is an authenticated internal tool, not a marketing site, so SSR/SEO buys nothing and costs the team a mental model (server vs. client components) they don't need to learn under deadline. |
| Language | **TypeScript 5.x** | The API surface in `prd.md` §21 is large (15+ endpoints, nested evidence/violation objects) — untyped JS would let a frontend/backend contract drift go unnoticed until a demo-day bug. Types are generated from the FastAPI OpenAPI schema (see `openapi-typescript` in §4.1) so the contract is enforced automatically, not hand-maintained. |
| Styling | **Tailwind CSS 3.x** | Matches the token-driven design system in `design.md` §12 (CSS custom properties) — Tailwind's `theme.extend` maps directly onto Docket's color/type/spacing tokens, so the design system is enforced in code, not just in a doc. Rejected: CSS-in-JS (styled-components/Emotion) — adds a runtime cost and a learning curve with no benefit for a team that already has a fixed token system to implement, not invent. |
| Data fetching / server cache | **TanStack Query (React Query) 5.x** | The Processing Screen (`prd.md` §22 page 5) needs polling with automatic retry/backoff — TanStack Query's `refetchInterval` + `retry` options implement `prd.md` §33's failure-handling table directly, without hand-rolled polling logic. |
| Client/UI state | **Zustand 4.x** | Minimal boilerplate versus Redux Toolkit for the small amount of genuinely client-only state (capture-flow step, offline queue status, UI theme mode from `design.md` §7.1). Redux was considered and rejected — this app's state is overwhelmingly server state (owned by TanStack Query), and Redux's ceremony isn't justified for the sliver that's left. |
| Forms & validation | **React Hook Form 7.x + Zod 3.x** | Rule Management (`prd.md` §22 page 13) has a nontrivial nested form (the rule schema in `prd.md` §12.2) — Zod schemas validate client-side and can be shared/mirrored against the Pydantic schema on the backend, keeping validation logic from diverging. |
| Charts | **Recharts 2.x** | Dashboard KPIs (`prd.md` §23) — bar/line/stacked-bar are all first-class Recharts chart types with a declarative API a student team can style to match `design.md` tokens quickly. Rejected: D3 directly — far more powerful, far more time-expensive; not justified for standard KPI charts. |
| Camera capture | Native `getUserMedia` (no library) | `prd.md` FR-002 needs a live preview + capture-to-blob — this is ~40 lines of native browser API; adding a dependency (e.g., `react-webcam`) buys convenience but another point of version drift for a core, safety-relevant flow. Hand-rolled with a thin wrapper hook instead. |
| PWA / offline shell | **`vite-plugin-pwa`** (Workbox under the hood) | Implements `prd.md` §27's capture-and-queue MVP — service worker caches the app shell and queues unsent inspection payloads in IndexedDB via the Background Sync API where supported, with a manual retry fallback where it isn't. |
| Icons | **Lucide React** | MIT-licensed, tree-shakeable, matches the restrained/functional visual language in `design.md` (no decorative icon packs). |
| Routing | **React Router 6.x** | Standard choice; nested routes map cleanly onto the inspection detail sub-pages (Extracted Info → Compliance Results → Violation Evidence are nested views of one `/inspections/:id` route tree). |

### 4.1 Type-safety bridge
`openapi-typescript` generates a `schema.d.ts` from FastAPI's auto-generated OpenAPI spec (`/openapi.json`) on every backend schema change (wired into the `dev` npm script and a CI check that fails if the checked-in types are stale). This is what makes `prd.md` §21's API table a contract, not documentation that can silently drift.

---

## 5. Backend Stack (Detail)

| Concern | Library | Why |
|---|---|---|
| Runtime | **Python 3.13.x** | Current stable line as of 2026 with full bugfix support; every library in this document (FastAPI, SQLAlchemy 2.x, Ultralytics, scikit-learn) has confirmed 3.13 wheels. Python 3.14 is newer but the CV/ML ecosystem (PaddlePaddle in particular) historically lags a Python release behind on prebuilt wheels — pin to 3.13 to avoid the team losing a day to a missing binary wheel. Re-evaluate 3.14 after PaddlePaddle publishes 3.14 wheels. |
| Web framework | **FastAPI 0.11x** | Async-native (matters for the job-status polling endpoint under concurrent load), automatic OpenAPI generation (feeds §4.1's type bridge), Pydantic-based validation gives the field-level `{field, issue}` error shape `prd.md` §21/§22 requires for free. |
| Data validation | **Pydantic 2.x** | Ships with FastAPI; v2's Rust core gives a real performance win over v1 for the nested evidence/violation payloads. |
| ORM | **SQLAlchemy 2.0.x (async)** | The relational integrity requirements in `prd.md` §20 (rule_versions ↔ compliance_checks ↔ violations ↔ evidence, with real foreign keys) are exactly SQLAlchemy's strength; 2.0's async engine keeps the whole request path non-blocking end-to-end with FastAPI. |
| Migrations | **Alembic 1.13.x** | Standard SQLAlchemy migration tool; every schema change in `prd.md` §20 is a reviewable, versioned migration file — required for the rule-versioning system's own auditability story to be credible. |
| Password hashing | **`passlib[bcrypt]` 1.7.x** | bcrypt with cost ≥12 per `prd.md` §25.1; `passlib` gives a stable hashing API that isolates the app from bcrypt-library churn. |
| JWT | **`python-jose[cryptography]` 3.3.x** | Access + refresh token issuance/verification per `prd.md` §7/§21/§25.2. |
| Rate limiting | **`slowapi` 0.1.x** (Starlette middleware, Redis-backed) | Implements the login rate-limiting and general API rate-limiting from `prd.md` §25.1, reusing the Redis instance already required for the job queue — no new infrastructure. |
| Background jobs | **RQ (Redis Queue) 1.16.x** on **Redis 7.x** | Chosen over Celery in `prd.md` §7 for lower operational complexity; RQ's `Retry` class implements the "retry ×2 with backoff" requirement in `prd.md` §9/§33 directly. |
| HTTP client (internal/testing) | **`httpx` 0.27.x** | Async-compatible, used both by the app (if any internal HTTP calls are ever needed) and by the test suite (§13). |
| Structured logging | **`structlog` 24.x** | JSON logs with a per-request correlation ID (`prd.md` §9's observability target), configured to bind `request_id` at the FastAPI middleware layer and propagate it into RQ job logs so a single inspection's full trace is greppable end-to-end. |
| Image handling | **Pillow 10.x** | Evidence crop generation (`prd.md` §18.2), EXIF auto-orientation, re-encoding on upload (`prd.md` §25.5's "strip embedded payloads" requirement). |
| Date parsing | **`python-dateutil` 2.9.x** | Normalizing OCR'd manufacture/packing dates (`prd.md` §14.2) — handles the many raggedy real-world date-string shapes OCR will produce more robustly than hand-written regex alone. |
| PDF generation | **WeasyPrint 62.x** + **Jinja2 3.1.x** | HTML/CSS → PDF per `prd.md` §7/§24; Jinja2 templates the report structure from `prd.md` §24.1, styled with the same `design.md` tokens as the web UI (via a shared CSS-variables partial) so the report and the app look like one product. |
| Object storage client | **`boto3` 1.34.x** (S3-compatible API against MinIO) | Same client works unmodified against real AWS S3 later — no code change if the team ever moves off self-hosted MinIO (`prd.md` §7's stated rationale). |


---

## 6. Computer Vision & OCR Stack (Detail)

| Concern | Library | Why |
|---|---|---|
| Image preprocessing | **OpenCV (`opencv-python`) 4.10.x** | Blur scoring (Laplacian variance), exposure histogram checks, perspective correction (`getPerspectiveTransform`) — all specified in `prd.md` §10.1/§11.3. Battle-tested, CPU-efficient, zero licensing cost (Apache 2.0). |
| Object detection | **Ultralytics YOLOv8n 8.3.x**, exported to **ONNX** for inference | Fastest realistic path from a few hundred labeled images (`prd.md` §29) to a usable package/label detector (`prd.md` §10.2); the nano variant hits the CPU latency budget in `prd.md` §9 (≤8s p50 end-to-end, of which detection is ~150–300ms). ONNX export (via `model.export(format="onnx")`) decouples the inference runtime from the PyTorch training environment, so the demo-day worker container doesn't need a full PyTorch install. |
| ONNX inference runtime | **`onnxruntime` 1.18.x** (CPU build) | Lighter dependency footprint than shipping full PyTorch to the inference worker; GPU build (`onnxruntime-gpu`) is a drop-in swap if the team gets GPU access for the demo machine, with no code change. |
| OCR engine | **PaddleOCR 2.8.x** on **PaddlePaddle 2.6.x** (CPU build) | Selected in `prd.md` §11.1 over Tesseract/EasyOCR/cloud APIs/multimodal VLMs specifically for multilingual (English + Hindi) support, curved/rotated text handling, and self-hostability (required for `prd.md` §27's offline field mode and to keep no image data leaving the device). Use the `PP-OCRv4` model set (`en_PP-OCRv4` + a Devanagari/Hindi-capable multilingual model) — verify the exact current Hindi-model artifact name against PaddleOCR's model zoo at build time, since PaddleOCR periodically renames/upgrades released model bundles. |
| Angle/orientation classification | PaddleOCR's built-in `use_angle_cls=True` | No separate library — bundled with PaddleOCR, implements the rotated-text handling in `prd.md` §11.3. |
| Numeric/scientific base | **NumPy 1.26.x** | Underpins OpenCV, PaddleOCR, and scikit-learn array operations — pinned to one version across all three to avoid ABI mismatches (a very common real-world source of "works on my machine" failures in a CV+ML Python stack). |

### 6.1 Why CV/OCR runs in-process inside the RQ worker, not as separate microservices
`prd.md` §6.1 already states the monolith-with-logical-separation decision; the concrete consequence for this document is that OpenCV/YOLO/PaddleOCR/scikit-learn are all Python dependencies of **one** worker container/image, not four separate services with their own HTTP APIs. This avoids serialization overhead (images are typically 1–15MB — an internal HTTP hop per pipeline stage would add real, avoidable latency against the `prd.md` §9 targets) and avoids four times the deployment surface for a 6-person team. The architecture diagram in `prd.md` §6 remains the correct target if/when the team later splits these into real services — nothing here forecloses that.

---

## 7. Classical ML Stack (Product Classification)

| Concern | Library | Why |
|---|---|---|
| Baseline classifier | **scikit-learn 1.5.x** — `TfidfVectorizer` + `GradientBoostingClassifier` (or `HistGradientBoostingClassifier` for speed) | `prd.md` §7/§10.2's stated MVP approach — ships in days on a few hundred labeled product names, no GPU, sub-50ms inference. |
| Model persistence | **`joblib` 1.4.x** | Standard scikit-learn model serialization; the trained pipeline (vectorizer + classifier as one `sklearn.pipeline.Pipeline`) is saved as a single `.joblib` artifact loaded once at worker startup. |
| Tabular/data prep | **pandas 2.2.x** | Dataset assembly and train/val/test splitting (`prd.md` §29.3 — split by physical product, implemented as a `groupby` on a `product_instance_id` column before the split, to prevent the data leakage `prd.md` explicitly warns against). |
| Upgrade path (if baseline accuracy is insufficient, per `prd.md` §30) | **CLIP image embeddings** (`open_clip_torch`, pretrained, no fine-tuning) **+ `LogisticRegression`** | A ready-made escalation that stays within "pretrained, no GPU training required" — only reach for this if the text-only baseline's F1 (per `prd.md` §30.1) is below the team's calibrated threshold. |

---

## 8. Database & Storage

| Concern | Choice | Why |
|---|---|---|
| Primary database | **PostgreSQL 17.x** | Current, mature major version (18.x exists but is very recently released as of this writing — 17.x has the longer track record and the widest confirmed driver/tool compatibility, the safer choice for a fixed hackathon deadline; upgrading to 18 later is a routine `pg_upgrade`, not an architecture change). Relational integrity + `JSONB` for the rule-content flexibility described in `prd.md` §7/§20. |
| Async driver | **`asyncpg` 0.29.x** (via SQLAlchemy's async engine) | Fastest available async Postgres driver for Python; pairs with FastAPI's async request handling end-to-end. |
| Full-text search | Postgres native (`tsvector` + GIN index, `pg_trgm` extension for fuzzy/typo-tolerant product-name search) | No external search engine (Elasticsearch/Meilisearch) — unjustified operational overhead at this data scale (`prd.md` §9's concurrency targets); Postgres FTS comfortably covers Workflow F (`prd.md` §5/§20.2). |
| Object storage | **MinIO** (latest stable `RELEASE.*` tag), S3-compatible | Self-hosted, zero cloud dependency (works fully offline on the demo machine, `prd.md` §38.3), API-identical to AWS S3 if the team deploys to cloud later (`prd.md` §7). |
| Cache / job broker | **Redis 7.x** | Backs both RQ (job queue, §5) and `slowapi` (rate limiting, §5) — one piece of infrastructure serving two needs. |

---

## 9. Authentication & Security Libraries

| Concern | Library | Notes |
|---|---|---|
| Password hashing | `passlib[bcrypt]` 1.7.x | Cost factor 12 minimum, per `prd.md` §25.1 |
| JWT issuance/verification | `python-jose[cryptography]` 3.3.x | Access token ≤60min expiry, refresh rotation, per `prd.md` §9/§25.2 |
| Input validation | Pydantic 2.x (backend) + Zod 3.x (frontend) | Shared validation intent, independently enforced on both sides — never trust client-side validation alone |
| Rate limiting | `slowapi` 0.1.x | Redis-backed, applied to `/auth/login` and globally per `prd.md` §25.1 |
| CORS | FastAPI's built-in `CORSMiddleware` | Restricted to the known frontend origin(s) in every non-local environment |
| Security headers | `secure` 0.3.x (Python) or hand-set middleware | HSTS, `X-Content-Type-Options`, `X-Frame-Options` on all responses |
| Dependency vulnerability scanning | `pip-audit` (Python) + `npm audit` (JS), run in CI | Catches known-CVE dependencies before merge, not after |
| Secrets | `.env` (local/demo) via `python-dotenv` 1.0.x | Never committed — see §18 for `.env.example` |


---

## 10. DevOps, CI/CD & Deployment

| Concern | Choice | Notes |
|---|---|---|
| Containerization | **Docker** (multi-stage Dockerfiles per service) | Backend: `python:3.13-slim` base; frontend: `node:22-alpine` build stage → static files served via Nginx |
| Orchestration (local + demo) | **Docker Compose** (Compose spec 3.9) | `docker-compose.yml` (dev) and `docker-compose.demo.yml` (offline-ready demo build) per `prd.md` §43 — Kubernetes explicitly rejected there as unjustified overhead for this team/scale |
| Reverse proxy | **Nginx 1.27.x** | Serves the built frontend static assets and proxies `/api/*` to the FastAPI container; also the natural place to enforce TLS termination in any non-local deployment |
| CI | **GitHub Actions** | Pipeline: lint (ruff + eslint) → type-check (mypy + tsc) → unit/integration tests (§13) → build Docker images → (on `main`) push images. Matches the repo/branching strategy in `prd.md` §42 |
| Python linting/formatting | **`ruff`** (lint + format, replacing separate flake8/black/isort) | One fast tool instead of three, minimizes CI time and config sprawl for a small team |
| Python type-checking | **`mypy`** (strict mode on `app/services/rule_engine` and `app/services/compliance_engine` at minimum — the two modules where a silent type error is most consequential) | |
| JS/TS linting/formatting | **ESLint + Prettier** | Standard React/TS config |
| Frontend type-checking | **`tsc --noEmit`** in CI | Fails the build on any type error, including drift caught by §4.1's generated types |
| Container registry | GitHub Container Registry (`ghcr.io`) | Free for a student/hackathon team's public or private repo, integrates directly with GitHub Actions with no extra credentials setup |

### 10.1 Environments
| Environment | Compose file | Notes |
|---|---|---|
| Local development | `docker-compose.yml` | Hot-reload on both frontend (Vite) and backend (`uvicorn --reload`) |
| SIH demo | `docker-compose.demo.yml` | Production-built images, seeded database (demo users, seeded rule versions per `prd.md` §12.6, demo product records per `prd.md` §39), zero external network dependency per `prd.md` §38.3 |
| CI test run | `docker-compose.test.yml` (Postgres + Redis + MinIO only, ephemeral) | Backend/frontend run natively in the GitHub Actions runner against these ephemeral service containers, for faster CI than building full app images every run |

---

## 11. Testing Stack

| Layer | Tooling | Maps to `prd.md` §31 |
|---|---|---|
| Backend unit/integration | **pytest 8.x** + **pytest-asyncio** + **httpx.AsyncClient** (in-process ASGI transport, no real network hop) | Unit, Integration, API, Rule-engine test rows |
| Backend test data | **`factory_boy`** 3.3.x + a Postgres test database (via the `docker-compose.test.yml` ephemeral container) | Realistic `declarations`/`rule_versions` fixtures without hand-writing JSON by hand for every test |
| Frontend unit/component | **Vitest** (Vite-native, faster than Jest in this stack) + **React Testing Library** | Frontend tests row |
| End-to-end | **Playwright** | E2E row — chosen over Cypress for built-in multi-browser support and a faster, more reliable headless run in CI, and because it can drive the actual camera-capture flow via a fake video device in CI (`--use-fake-device-for-media-stream`) |
| Load/performance | **Locust 2.29.x** | Performance tests row — scripted against `prd.md` §9's concurrency targets (20 concurrent users, 5 concurrent analysis jobs) |
| ML/CV evaluation | Custom scripts in `ml/evaluation/` using scikit-learn's `metrics` module + a small COCO-mAP utility (`pycocotools` or a lightweight reimplementation) | Computes the metrics defined in `prd.md` §30.1 (CER/WER, mAP, F1) against the held-out validation split |
| Security | `pip-audit`/`npm audit` (§9) + a manual OWASP-ZAP baseline scan before demo | Security tests row |

---

## 12. Observability & Monitoring

| Concern | Choice | Notes |
|---|---|---|
| Application logs | `structlog` → stdout, JSON-formatted | Collected via Docker's default `json-file` log driver in dev/demo; correlatable by `request_id` per §5 |
| Audit trail | `audit_logs` table (Postgres) — **not** the same thing as application logs | Per `prd.md` §20.1/§25.1: append-only, no DB-level UPDATE/DELETE grant for the app role. This is a compliance/legal artifact, deliberately kept separate from operational logging |
| Metrics (optional, P2 per `prd.md` §34.1) | **Prometheus** + **Grafana**, via `prometheus-fastapi-instrumentator` | Not required for the SIH demo; worth adding only if the team has time after P0/P1 — `prd.md` §9 explicitly warns against over-engineering observability at this scale |
| Error tracking (optional) | **Sentry** (self-hosted or free-tier SaaS) | Same P2 caveat as above; useful during the integration/testing phase (`prd.md` §40 Phase 8) if the team wants it |

---

## 13. Version Matrix (Consolidated Pin List)

```
# Runtime
python == 3.13.*
node == 22.*        (LTS "Jod", Active LTS through 2027-04)

# Backend (requirements.txt — see §17.1 for the full file)
fastapi == 0.11x.*
uvicorn[standard] == 0.30.*
pydantic == 2.*
sqlalchemy == 2.0.*
alembic == 1.13.*
asyncpg == 0.29.*
passlib[bcrypt] == 1.7.*
python-jose[cryptography] == 3.3.*
slowapi == 0.1.*
rq == 1.16.*
redis == 5.*             # Python client, server is Redis 7.x
structlog == 24.*
pillow == 10.*
python-dateutil == 2.9.*
weasyprint == 62.*
jinja2 == 3.1.*
boto3 == 1.34.*
opencv-python == 4.10.*
ultralytics == 8.3.*
onnxruntime == 1.18.*
paddleocr == 2.8.*
paddlepaddle == 2.6.*
scikit-learn == 1.5.*
pandas == 2.2.*
joblib == 1.4.*
numpy == 1.26.*
python-dotenv == 1.0.*

# Frontend (package.json — see §17.2 for the full file)
react == 18.*
react-dom == 18.*
typescript == 5.*
vite == 5.*
tailwindcss == 3.*
@tanstack/react-query == 5.*
zustand == 4.*
react-hook-form == 7.*
zod == 3.*
recharts == 2.*
react-router-dom == 6.*
lucide-react == latest
vite-plugin-pwa == latest
openapi-typescript == latest (dev dependency)

# Infra
postgres == 17.*
redis == 7.*
nginx == 1.27.*
docker-compose spec == 3.9
```


---

## 14. Alternatives Considered & Rejected (Expanded)

This expands `prd.md` §7's comparison table with the specific runner-up for every major decision and the concrete reason it lost — so the team can revisit a decision confidently if a real constraint changes, instead of re-litigating from scratch.

| Decision | Runner-up | Why it lost |
|---|---|---|
| FastAPI over Django REST Framework | Django REST Framework | DRF's batteries (admin panel, ORM) are attractive, but its sync-first request model fights the async job-polling pattern the Processing Screen needs, and its ORM is less natural than SQLAlchemy for the JSONB-heavy rule-content schema in `prd.md` §12.2. |
| FastAPI over Node/Express | Node/Express + TypeScript | Would unify the language across frontend/backend, but every CV/OCR/ML library in §6–§7 is Python-native; an Express backend would need to shell out to a separate Python service anyway, reintroducing the network-hop cost §6.1 specifically avoids. |
| SQLAlchemy over Django ORM / Tortoise ORM | Tortoise ORM | Tortoise is a reasonable async-native alternative, but has a smaller ecosystem and less mature Alembic-equivalent migration tooling — a real risk for a schema (`prd.md` §20) that will change repeatedly during Phases 1–7 (`prd.md` §40). |
| RQ over Celery | Celery | Celery is more feature-complete (scheduled tasks, complex routing) but has meaningfully more operational surface (broker + result backend configuration, worker concurrency tuning) than a 6-person team needs for "run the CV/OCR pipeline as a background job." Revisit Celery only if the team needs cron-style periodic tasks beyond what a simple scheduled RQ job covers. |
| PaddleOCR over EasyOCR | EasyOCR | EasyOCR is easier to install (fewer native dependencies) but has materially weaker Hindi/Devanagari recognition accuracy and weaker curved-text handling than PaddleOCR's DB-based detector — both are P0 requirements here (`prd.md` §11.1), not nice-to-haves. |
| PaddleOCR over cloud OCR APIs (Google Vision / AWS Textract) | Cloud OCR APIs | Materially higher out-of-the-box accuracy, but (a) costs per call, (b) requires internet — directly breaking the offline field mode in `prd.md` §27, and (c) sends product-label images to a third party, which is an unnecessary data-handling question for a government enforcement tool to have to answer. A cloud-assist toggle remains a legitimate P3 addition (`prd.md` §35) for connected environments only. |
| YOLOv8n over Detectron2/DETR | Detectron2 or DETR | Higher achievable accuracy at scale, but both need more labeled data and (practically) GPU training time the team is unlikely to have (`prd.md` §44) — YOLOv8n's pretrained-weight starting point reaches a usable detector on `prd.md` §29's ~300–500 image dataset far faster. |
| scikit-learn baseline over a from-scratch PyTorch classifier | Fine-tuned PyTorch CNN/embedding classifier | A from-scratch deep model needs more labeled data and training iteration time than the schedule (`prd.md` §40) supports for what is, per `prd.md` §10.2, a moderate-cardinality classification problem. The CLIP-embedding upgrade path (§7) exists precisely so the team isn't locked out of higher accuracy later without a from-scratch training project. |
| PostgreSQL over MongoDB | MongoDB | `prd.md` §7 already covers this: the rules↔versions↔checks↔violations↔evidence graph is genuinely relational with real foreign-key/audit requirements; Postgres's JSONB columns already give document-store flexibility exactly where it's actually needed (`rule_versions.content`), without giving up transactional guarantees everywhere else. |
| MinIO over direct filesystem storage | Local filesystem | Filesystem storage is simpler initially, but breaks the moment the team needs more than one backend replica, and MinIO's S3 API means zero code change if the project is ever deployed to real cloud storage — the swap cost of moving off filesystem storage later is strictly higher than starting with MinIO. |
| WeasyPrint over ReportLab | ReportLab | ReportLab's imperative, canvas-style API is slower to iterate on for the fairly complex, evidence-heavy report layout in `prd.md` §24.1; WeasyPrint's HTML/CSS approach lets the same `design.md` tokens style both the web app and the PDF report from one source of design truth. Kept as the documented P1 fallback if WeasyPrint's CSS support proves insufficient for a specific layout need (`prd.md` §7). |
| Vite over Create React App / Next.js | Create React App | CRA is deprecated by its own maintainers as of recent React tooling guidance; not a real contender. Next.js is covered above (§4). |
| Tailwind over CSS Modules / styled-components | CSS Modules | CSS Modules would work and impose no runtime cost, but doesn't give the same enforced-token-scale ergonomics (`theme.extend`) that make `design.md`'s spacing/type/color tokens hard to drift from in day-to-day component code. |
| Docker Compose over Kubernetes | Kubernetes | Already covered in `prd.md` §7/§43 — reiterated here because it is the single most common over-engineering trap for a team with production-scale ambitions and hackathon-scale time. |

---

## 15. Licensing Summary

Relevant for a government-facing submission, where dependency licensing should be uncontroversial and clearly documented.

| Component | License | Commercial/government use |
|---|---|---|
| React, React Router | MIT | Unrestricted |
| Vite | MIT | Unrestricted |
| TypeScript | Apache 2.0 | Unrestricted |
| Tailwind CSS | MIT | Unrestricted |
| TanStack Query | MIT | Unrestricted |
| Zustand | MIT | Unrestricted |
| FastAPI | MIT | Unrestricted |
| Pydantic | MIT | Unrestricted |
| SQLAlchemy | MIT | Unrestricted |
| Alembic | MIT | Unrestricted |
| Redis | RSALv2 / SSPLv1 (server, since Redis 7.4) — **verify current license terms for the exact Redis version pinned before production deployment**; alternatively use a Redis-license-compatible fork (e.g., Valkey, BSD-3) if this is a concern for a government deployment | Self-hosted internal use is generally unaffected either way, but this is worth a deliberate team decision, not an assumption — flagged here rather than glossed over |
| PostgreSQL | PostgreSQL License (permissive, similar to MIT/BSD) | Unrestricted |
| MinIO | AGPLv3 (server) | **Copyleft** — fine for self-hosted internal use where the source isn't being distributed/modified-and-redistributed as a product, but the team should not fork-and-redistribute MinIO itself without complying with AGPL's terms. Using MinIO as an unmodified backing service (the design here) does not trigger AGPL's source-sharing obligation. |
| OpenCV | Apache 2.0 | Unrestricted |
| Ultralytics YOLOv8 | **AGPLv3** (or a paid Ultralytics Enterprise License for closed-source use) | **Important:** AGPLv3 requires that if this application is offered as a network service to others (which an enforcement-department deployment arguably is), the complete corresponding source code must be made available to users of that service. For a government-run internal enforcement tool this is very likely acceptable (the department can treat this as effectively internal use, or open the source), but the team should confirm this explicitly with whoever owns the project's licensing decisions before a production (non-hackathon) deployment — this is exactly the kind of thing that's cheap to check now and expensive to discover later. |
| PaddleOCR, PaddlePaddle | Apache 2.0 | Unrestricted |
| ONNX Runtime | MIT | Unrestricted |
| scikit-learn, pandas, NumPy, joblib | BSD-3-Clause | Unrestricted |
| WeasyPrint | BSD-3-Clause | Unrestricted |
| Jinja2 | BSD-3-Clause | Unrestricted |
| Pillow | MIT-CMU (HPND-style) | Unrestricted |
| Docker, Docker Compose | Apache 2.0 | Unrestricted |
| Nginx | BSD-2-Clause (open-source edition) | Unrestricted |
| Playwright | Apache 2.0 | Unrestricted |
| Locust | MIT | Unrestricted |

**Action item flagged, not resolved:** confirm the AGPLv3 implication for Ultralytics YOLOv8 (and Redis's current license line) with the team/department before any deployment beyond the SIH demo — this document surfaces the question per `prd.md`'s own instruction not to leave ambiguities silently resolved; it does not make the legal call.


---

## 16. Why the Backend Is a Monolith (and When to Split It)

`prd.md` §6.1 states this decision; restated here as a stack-level policy so it isn't accidentally re-architected mid-build. One FastAPI application, one Postgres database, one Redis instance, one RQ worker pool. The **logical** separation in `prd.md` §6's diagram (Image Processing / OCR / CV / Extraction / Classification / Rule Engine / Compliance Engine / Evidence Engine) is enforced at the **Python module** level (`app/services/<name>/`), each with a clean function-level interface — so splitting any one of them into a real microservice later is a matter of adding a network call at that module's boundary, not a rewrite. Split triggers, if they ever arise: (a) one stage's compute needs (e.g., CV/OCR) genuinely require different scaling/hardware than the rest of the app (a GPU fleet for CV, CPU-only for the API), or (b) a second consuming application needs the rule engine independent of this app's HTTP API. Neither applies at SIH scale.

---

## 17. Dependency Manifests

### 17.1 `backend/requirements.txt`
```
# Web framework
fastapi==0.115.*
uvicorn[standard]==0.30.*
pydantic==2.*
pydantic-settings==2.*

# Database
sqlalchemy==2.0.*
alembic==1.13.*
asyncpg==0.29.*

# Auth & security
passlib[bcrypt]==1.7.*
python-jose[cryptography]==3.3.*
slowapi==0.1.*
python-dotenv==1.0.*

# Job queue
rq==1.16.*
redis==5.*

# Logging
structlog==24.*

# Image / CV / OCR / ML
pillow==10.*
opencv-python==4.10.*
ultralytics==8.3.*
onnxruntime==1.18.*
paddleocr==2.8.*
paddlepaddle==2.6.*
scikit-learn==1.5.*
pandas==2.2.*
numpy==1.26.*
joblib==1.4.*
python-dateutil==2.9.*

# Reports
weasyprint==62.*
jinja2==3.1.*

# Object storage
boto3==1.34.*

# Dev / test (backend/requirements-dev.txt, separate file)
# pytest==8.*
# pytest-asyncio==0.23.*
# httpx==0.27.*
# factory_boy==3.3.*
# ruff==0.5.*
# mypy==1.10.*
# pip-audit==2.7.*
```

### 17.2 `frontend/package.json` (dependencies excerpt)
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.24.0",
    "@tanstack/react-query": "^5.51.0",
    "zustand": "^4.5.0",
    "react-hook-form": "^7.52.0",
    "zod": "^3.23.0",
    "@hookform/resolvers": "^3.9.0",
    "recharts": "^2.12.0",
    "lucide-react": "^0.400.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "vite-plugin-pwa": "^0.20.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^9.6.0",
    "prettier": "^3.3.0",
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "@playwright/test": "^1.45.0",
    "openapi-typescript": "^7.3.0"
  }
}
```

### 17.3 `docker-compose.yml` (development, abbreviated — services only)
```yaml
services:
  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --reload
    env_file: .env
    depends_on: [postgres, redis, minio]
    ports: ["8000:8000"]
    volumes: ["./backend:/app"]

  worker:
    build: ./backend
    command: rq worker --url redis://redis:6379 inspection-pipeline
    env_file: .env
    depends_on: [postgres, redis, minio]
    volumes: ["./backend:/app"]

  frontend:
    build: ./frontend
    command: npm run dev -- --host
    env_file: .env
    ports: ["5173:5173"]
    volumes: ["./frontend:/app"]

  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: ["pgdata:/var/lib/postgresql/data"]
    ports: ["5432:5432"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes: ["miniodata:/data"]
    ports: ["9000:9000", "9001:9001"]

volumes:
  pgdata:
  miniodata:
```

---

## 18. Environment Variables Reference

`.env.example` (committed to the repo, per `prd.md` §42.2 — real `.env` is git-ignored):

```
# --- Database ---
POSTGRES_DB=legal_metrology
POSTGRES_USER=app_user
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql+asyncpg://app_user:changeme@postgres:5432/legal_metrology

# --- Redis ---
REDIS_URL=redis://redis:6379/0

# --- Object storage (MinIO) ---
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=changeme
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET_IMAGES=lm-images
S3_BUCKET_EVIDENCE=lm-evidence
S3_BUCKET_REPORTS=lm-reports

# --- Auth ---
JWT_SECRET_KEY=changeme-generate-a-real-32-byte-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=14

# --- App ---
ENVIRONMENT=development
CORS_ALLOWED_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO

# --- ML/CV model paths (baked into the worker image or mounted) ---
YOLO_MODEL_PATH=/models/package_label_detector.onnx
PRODUCT_CLASSIFIER_PATH=/models/product_classifier.joblib
PADDLEOCR_LANG=en,hi

# --- Frontend (frontend/.env) ---
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

**Rule:** `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, and `MINIO_ROOT_PASSWORD` must never keep their example placeholder values past local development — the demo environment (`docker-compose.demo.yml`) generates its own secrets at setup time, never reuses the committed example file's values.

---

## 19. Local Dev Setup Quickstart

```bash
git clone <repo-url> && cd sih26034-legal-metrology
cp .env.example .env            # then edit secrets locally
docker compose up --build       # backend, worker, frontend, postgres, redis, minio
docker compose exec backend alembic upgrade head   # apply DB schema
docker compose exec backend python -m scripts.seed_rules   # load initial rule_versions (prd.md §12.6)
```
Frontend: http://localhost:5173 · Backend API docs (auto-generated by FastAPI): http://localhost:8000/docs · MinIO console: http://localhost:9001

---

## 20. Hardware & Runtime Requirements

Restated from `prd.md` §44 as a stack-specific checklist:

| Environment | Minimum spec | Why |
|---|---|---|
| Dev machine | 4-core CPU, 16GB RAM, 20GB free disk | Full Compose stack (6 containers) + PaddleOCR/YOLO model weights (~1–2GB combined) comfortably fits |
| Model training (YOLO fine-tune) | GPU recommended (a free-tier cloud notebook is an acceptable substitute), else CPU-only training is possible but slow | One-time/occasional task, not a runtime dependency — §6 confirms inference is CPU-only via ONNX Runtime |
| SIH demo machine | 4-core CPU, 16GB RAM, 20GB free disk, **no internet required** | `docker-compose.demo.yml` per §10.1; validated against `prd.md` §38.3 |
| GPU | Not required anywhere in the runtime path | Every inference-time dependency (§6, §7) has a confirmed CPU-capable path — a deliberate constraint, not an oversight |

---

## 21. Upgrade & Maintenance Policy

- **Security patches** (any dependency with a known CVE flagged by `pip-audit`/`npm audit` in CI, §10) are applied within the current sprint, not deferred to "later."
- **Minor version bumps** (e.g., FastAPI 0.115.x → 0.116.x) are batched and applied at phase boundaries (`prd.md` §40), not mid-phase, to avoid destabilizing an in-progress integration.
- **Major version bumps** (e.g., React 18 → 19, PostgreSQL 17 → 18) are explicitly out of scope during the SIH build window — evaluated only after submission, as a deliberate post-hackathon maintenance task, and only after confirming every dependency in this document has compatible releases.
- **Model artifacts** (YOLO weights, the product classifier `.joblib`) are versioned by filename (`package_label_detector.v3.onnx`) and referenced by exact filename in `.env`, never overwritten in place — this mirrors the same "never silently mutate a referenced version" principle `prd.md` §12.4 applies to legal rules, applied here to model versions.
