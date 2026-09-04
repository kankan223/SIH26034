# Docket — Legal Metrology Compliance System

**SIH26034** · Smart India Hackathon 2026 · Submission Deadline: 20 September 2026

An automated compliance checker for packaged goods under the Legal Metrology (Packaged Commodities) Rules. Enforcement officers photograph a package, and the system detects the label, reads text (English + Hindi), extracts mandatory declarations, evaluates them against versioned rules, and produces an evidence-backed compliance report.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DOCKET SYSTEM                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │  Frontend │───▶│  Backend │───▶│  Worker  │───▶│ Database │ │
│  │ React+TS │    │  FastAPI │    │ RQ/Celery│    │ Postgres │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│       │               │               │               │        │
│       │               │               ▼               │        │
│       │               │         ┌──────────┐          │        │
│       │               │         │ MinIO    │          │        │
│       │               │         │ (S3)     │          │        │
│       │               │         └──────────┘          │        │
│       │               │               │               │        │
│       │               ▼               ▼               │        │
│       │         ┌──────────────────────────┐          │        │
│       │         │      CV/OCR Pipeline     │          │        │
│       │         │  YOLO → PaddleOCR → Rule │          │        │
│       │         └──────────────────────────┘          │        │
│       │                                               │        │
│       └───────────────── UI ◀─────────────────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Technology | Port | Purpose |
|---|---|---|---|
| **Backend** | FastAPI (Python 3.14) | 8000 | REST API, auth, RBAC, audit |
| **Frontend** | React + Vite + TypeScript | 5173 | Inspector UI |
| **Worker** | RQ + Redis | — | Async pipeline execution |
| **Database** | PostgreSQL 17 | 5432 | 15 relational tables |
| **Cache** | Redis 7 | 6379 | Session cache, job queue |
| **Object Storage** | MinIO (S3-compatible) | 9000 | Images, evidence, reports |

---

## Implemented Features (Phase 0–5.2)

### Phase 0: Infrastructure ✅
- Docker Compose with 6 services (backend, worker, frontend, postgres, redis, minio)
- 15 SQLAlchemy models per prd.md §20 with Alembic migrations
- GitHub Actions CI pipeline (lint, type-check, tests, audit)
- Seed data scripts (categories, users, rules)

### Phase 1: Auth, RBAC & Inspections ✅
- **POST /auth/login** — JWT authentication with bcrypt (cost=12)
- **POST /auth/refresh** — Token refresh (14-day expiry)
- **RBAC middleware** — `get_current_user()` + `require_role(*roles)` dependencies
- Three roles: `inspector`, `senior_officer`, `admin`
- **Inspection CRUD** — Create, read, list with RBAC enforcement
- **Image upload** — MIME validation, quality scoring, audit logging
- **Audit middleware** — Intercepts all mutating operations
- **GET /audit-logs** — Admin-only audit trail with filtering

### Phase 2: Image Quality & Storage ✅
- **Image quality gate** — Laplacian variance blur detection, histogram exposure analysis, 640×480 resolution floor
- **MinIO storage client** — Upload images, evidence crops, reports
- **Content-hash deduplication** — Duplicate uploads linked to existing URL
- **EXIF stripping** — Server-side re-encoding removes metadata
- **Presigned URLs** — Time-limited access to stored objects

### Phase 3: CV & OCR Pipeline ✅
- **YOLOv8n detection** — Package and label region detection with NMS
- **Contour-based fallback** — Development/testing when YOLO unavailable
- **PaddleOCR service** — English + Hindi text extraction
- **Angle classification** — Rotated/curved text handling
- **Small-font upscaling** — Bicubic 3x when text height < 12px
- **Confidence filtering** — Results <0.5 flagged as NOT_FOUND

### Phase 3.3: Text Normalization & Extraction ✅
- **OCR substitution fixes** — O/0, l/1, etc.
- **Unit normalization** — g/gm/gram → g, ml/mL → ml
- **Currency normalization** — ₹/Rs. → INR
- **Date parsing** — MM/YYYY → YYYY-MM
- **Declaration extraction** — All 14 field types per prd.md §14.1
- **NOT_FOUND handling** — Missing fields explicitly recorded, never omitted

### Phase 4: Classification & Font Analysis ✅
- **Product category classifier** — TF-IDF + GradientBoosting, 10 categories
- **Confidence threshold** — ≥0.6; below routes to manual selection
- **Font size estimation** — Relative-proxy method (text height / package height)
- **UNABLE_TO_VERIFY** — Honest uncertainty reporting, no fabricated mm values

### Phase 5.1: Rule Engine ✅
- **Deterministic rule evaluator** — Rules are data, not code
- **3 validation types** — regex_and_presence, presence_only, format_check
- **Versioned rule execution** — Every verdict references exact rule_versions.id
- **Category/Package matching** — applies_when conditions enforced
- **Missing → FAIL** — Mandatory fields missing → type MISSING, never silent pass
- **100% deterministic** — Same inputs always produce same outputs per FR-010

### Phase 5.2: Rule CRUD API & Compliance Engine ✅
- **Rule CRUD API** — POST/GET /rules, POST /rules/{id}/versions, POST publish
- **Rule versioning** — Append-only; legal_reference required before publish
- **Overlapping date check** — Blocks publish when effective_date conflicts
- **Audit logging** — Every publish action logged
- **Compliance decision engine** — 5-state output: COMPLIANT, NON_COMPLIANT,
  PARTIALLY_COMPLIANT, NEEDS_HUMAN_REVIEW, INSUFFICIENT_EVIDENCE
- **Severity assignment** — CRITICAL (missing mandatory), MAJOR (format dates),
  MINOR (other violations)
- **Per-field compliance** — Each field tracked with rule_version_id reference

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/login` | None | Authenticate user |
| POST | `/api/v1/auth/refresh` | Refresh token | Refresh access token |
| POST | `/api/v1/inspections` | inspector+ | Create inspection |
| GET | `/api/v1/inspections` | inspector+ | List inspections (RBAC-filtered) |
| GET | `/api/v1/inspections/{id}` | inspector+ | Get inspection detail |
| POST | `/api/v1/inspections/{id}/images` | inspector+ | Upload image |
| GET | `/api/v1/audit-logs` | admin | List audit logs |
| GET | `/api/v1/audit-logs/{id}` | admin | Get audit log entry |
| POST | `/api/v1/rules` | admin | Create rule (Phase 5.2) |
| GET | `/api/v1/rules` | admin | List rules |
| POST | `/api/v1/rules/{id}/versions` | admin | Add rule version |
| POST | `/api/v1/rules/{id}/versions/{vid}/publish` | admin | Publish rule version |
| GET | `/health` | None | Health check |

---

## Setup & Development

### Prerequisites
- Docker & Docker Compose
- Python 3.14+
- Node.js 22+

### Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd SIH26034

# 2. Copy environment template
cp .env.example .env

# 3. Start all services
docker compose up --build

# 4. Verify
curl http://localhost:8000/health
```

### Running Tests

```bash
# Backend tests (443 tests)
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest tests/ -v

# Frontend (when implemented)
cd frontend
npm install
npm test
```

### Backend Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, middleware, routers
│   ├── core/
│   │   ├── config.py              # Settings from environment
│   │   ├── security.py            # bcrypt + JWT utilities
│   │   ├── rbac.py                # Role-based access control
│   │   └── constants.py           # Shared enums (Role, Status, etc.)
│   ├── api/
│   │   ├── auth.py                # POST /auth/login, /auth/refresh
│   │   ├── inspections.py         # Inspection CRUD + image upload
│   │   └── audit.py              # GET /audit-logs (admin-only)
│   ├── services/
│   │   ├── image_processing.py    # Quality gate (blur, exposure, resolution)
│   │   ├── cv_detection.py        # YOLOv8n package/label detection
│   │   ├── ocr_service.py         # PaddleOCR text extraction
│   │   ├── storage.py             # MinIO object storage
│   │   ├── audit_service.py       # Append-only audit logging
│   │   ├── inspection_service.py  # Inspection CRUD operations
│   │   ├── extraction.py          # OCR fixes, normalization, field extraction
│   │   ├── classification.py     # TF-IDF + GB classifier (10 categories)
│   │   ├── font_analysis.py       # Relative-proxy font size estimation
│   │   ├── rule_engine.py         # Deterministic rule evaluator (Phase 5.1)
│   │   ├── compliance_engine.py   # 5-state compliance decision engine (Phase 5.2)
│   │   ├── api/
│   │   │   ├── rules.py           # Rule CRUD + versioning + publish (Phase 5.2)
│   │   │   └── ...                # auth.py, inspections.py, audit.py
│   ├── models/                    # 15 SQLAlchemy models
│   ├── schemas/                   # Pydantic request/response models
│   │   ├── rule.py                # Rule CRUD request/response schemas (Phase 5.2)
│   └── middleware/
│       └── audit.py               # Audit middleware for mutating ops
├── alembic/                       # Database migrations
├── scripts/                       # Seed data scripts
├── tests/                         # 443 unit tests
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Dev/test dependencies
└── Dockerfile                     # Python 3.14-slim
```

---

## Test Suite Summary

| Test File | Tests | Coverage |
|---|---|---|
| `test_security.py` | 9 | Password hashing, JWT creation/verification |
| `test_rbac.py` | 25 | Role enforcement, 401/403/200 scenarios |
| `test_audit.py` | 42 | Schema, middleware, API RBAC, filtering |
| `test_image_processing.py` | 26 | Blur, exposure, resolution, performance |
| `test_cv_detection.py` | 40 | Package/label detection, NMS, fallback |
| `test_ocr_service.py` | 35 | Text extraction, language, upscaling |
| `test_storage.py` | 32 | Upload, dedup, EXIF, presigned URLs |
| `test_classification.py` | 33 | Product category classification |
| `test_font_analysis.py` | 29 | Font size estimation, confidence scoring |
| `test_rule_engine.py` | 58 | Rule evaluation, versioning, all validation types |
| `test_rules_api.py` | 58 | Rule CRUD schemas, compliance engine, decision matrix |
| **Total** | **443** | **All passing** |

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Backend | FastAPI | 0.115.x |
| ORM | SQLAlchemy | 2.0.x |
| Migrations | Alembic | 1.13.x |
| Auth | bcrypt + python-jose | 4.x / 3.3.x |
| Rate Limiting | slowapi | 0.1.x |
| CV Detection | OpenCV + YOLOv8n | 4.10.x / 8.3.x |
| OCR | PaddleOCR | 2.8.x |
| Storage | boto3 (MinIO) | 1.34.x |
| Frontend | React + Vite + TypeScript | 18.x / 5.x / 5.x |
| Database | PostgreSQL | 17 |
| Cache | Redis | 7 |
| Object Storage | MinIO | latest |

---

## Project Roadmap

| Phase | Status | Tests | Description |
|---|---|---|---|
| Phase 0 | ✅ Complete | — | Scaffolding, DB schema, CI/CD |
| Phase 1 | ✅ Complete | 76 | Auth, RBAC, Inspection CRUD, Audit |
| Phase 2 | ✅ Complete | 58 | Image quality gate, MinIO storage |
| Phase 3 | ✅ Complete | 75 | YOLO detection, PaddleOCR |
| Phase 3.3 | ✅ Complete | 56 | Text normalization & declaration extraction |
| Phase 4 | ✅ Complete | 62 | Classification + font analysis |
| Phase 5.1 | ✅ Complete | 58 | Rule engine evaluator |
| Phase 5.2 | ✅ Complete | 58 | Rule CRUD API + Compliance Decision Engine |
| Phase 5.3 | ⏳ Pending | — | Compliance checking service integration |
| Phase 6 | ⏳ Pending | — | Evidence & human review |
| Phase 7 | ⏳ Pending | — | Reports & dashboard |
| Phase 8 | ⏳ Pending | — | Frontend UI |
| Phase 9 | ⏳ Pending | — | Hardening & release |

---

## Environment Variables

See `.env.example` for the complete list. Key variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://app_user:changeme@postgres:5432/legal_metrology

# Auth (≥32 bytes)
JWT_SECRET_KEY=changeme-minimum-32-bytes-long

# Object Storage
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET_IMAGES=lm-images
S3_BUCKET_EVIDENCE=lm-evidence
S3_BUCKET_REPORTS=lm-reports

# OCR
PADDLEOCR_LANG=en,hi
```

---

## License

Internal project for Smart India Hackathon 2026.

---

**SIH26034** · Ministry of Consumer Affairs, Food & Public Distribution · Department of Consumer Affairs
