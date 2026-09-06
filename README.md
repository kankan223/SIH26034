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

## Implemented Features (Phase 0–7)

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

### Phase 5.3: Pipeline Integration & Evidence Engine ✅
- **9-stage analysis pipeline** — image → quality → detection → OCR → extraction → classification → rules → compliance → evidence
- **Evidence engine** — Bounding-box crops stored to MinIO (`lm-evidence`), immutable evidence rows
- **PDF report generator** — 12-section report with verification seal on COMPLIANT only

### Phase 6: Evidence & Human Review ✅
- **Review queue** — Routes NEEDS_HUMAN_REVIEW / INSUFFICIENT_EVIDENCE items by region & severity
- **Correction workflow** — Mandatory reason (≥5 chars), stored as new rows (originals never overwritten)
- **Audit trail** — Every review decision and correction logged with before/after values
- **Report submission gate** — Blocks submission while any field is unresolved NEEDS_REVIEW

### Phase 7: Reports & Dashboard ✅
- **PDF reports** — Evidence crops embedded with bounding box coordinates, 12 sections per prd.md §24.1
- **DOCX export** — Editable 12-section Word export alongside PDF per prd.md §24.2
- **Report scheduling** — In-memory queue for asynchronous batch generation
- **Verification seal** — COMPLIANT exports only, per design.md §9
- **Dashboard KPIs** — GET /dashboard/kpis, /trends, /categories with RBAC + audit logging

### Phase 8: Frontend UI Implementation ✅
- **Core design system components** — LedgerRow (left-edge status tick, compact spacing per §3.2), MeasureRule (confidence meter baseline motif per §6), ComplianceStatusBadge (status-colored band), EvidenceCard (specimen card with bbox stroke-draw animation per §7.3)
- **API client & hooks** — Axios client with JWT request interceptor + 401 redirect; React Query hooks `useAuth`, `useInspection`; in-memory JWT only (never localStorage per §8.2.1 verification #5)
- **Auth & navigation** — LoginPage (design.md §8.1), app shell Layout (desktop sidebar + mobile bottom nav, Measure Rule collapses to 3px on mobile per §10), DashboardPage wired to `/dashboard/kpis` + `/trends` + `/categories`, RequireAuth routing
- **Core workflow pages** — ProcessingScreenPage (pipeline stepper, §8.4), ExtractedInfoPage (per-field confidence cards, §8.5), ComplianceResultsPage (verdict ticks, EvidenceCard with bbox animation, §8.6/§7.3), InspectionDetailPage
- **Admin & analytics pages** — ManualReviewPage (review queue + correction form), ReportPage (compliance preview), RuleManagementPage (rule list, version history, create/edit UI), ViolationEvidencePage
- **Offline capture queue** — `useOfflineQueue` hook (IndexedDB-backed queue for POST/PUT/PATCH, auto-retry every 30s, max 3 retries); `OfflineBanner` component (Amber Flag strip per design.md §10); `lib/offline.ts` utilities; PWA service worker via `vite-plugin-pwa` caching app shell for offline access per prd.md §27
- **Frontend tests** — 58 Vitest tests passing (12 files), 0 TypeScript errors, 0 hardcoded colors

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
| GET | `/api/v1/dashboard/kpis` | inspector+ | Dashboard KPIs (Phase 7.2) |
| GET | `/api/v1/dashboard/trends` | admin | Monthly trends (Phase 7.2) |
| GET | `/api/v1/dashboard/categories` | admin | Category breakdown (Phase 7.2) |
| GET | `/api/v1/reviews/queue` | senior_officer+ | Review queue (Phase 6.2) |
| POST | `/api/v1/reviews/{id}/confirm` | any auth | Confirm review item (Phase 6.2) |
| POST | `/api/v1/reviews/{id}/override` | senior_officer+ | Override/correct review (Phase 6.2) |
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
# Backend tests (540 tests)
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest tests/ -v

# Frontend (Phase 8)
cd frontend
npm install
npm test
```

### Frontend Structure

```
frontend/
├── src/
│   ├── App.tsx                          # React Router + OfflineBanner
│   ├── main.tsx                         # Entry point (QueryClient, BrowserRouter)
│   ├── api/
│   │   └── client.ts                    # Axios client + JWT interceptor
│   ├── components/
│   │   ├── Layout.tsx                   # App shell: desktop sidebar + mobile bottom nav
│   │   ├── OfflineBanner.tsx            # Amber Flag offline strip (design.md §10)
│   │   ├── InspectionLayout.tsx         # Inspection context shell with stepper
│   │   ├── LedgerRow.tsx                # Compact ledger row with left-edge status tick (§3.2)
│   │   ├── MeasureRule.tsx              # Confidence meter baseline motif (§6)
│   │   ├── ComplianceStatusBadge.tsx    # Status-colored band (§7)
│   │   └── EvidenceCard.tsx             # Specimen card with bbox stroke-draw (§7.3)
│   ├── hooks/
│   │   ├── useAuth.ts                    # useLogin, useLogout, useAuthToken (in-memory)
│   │   ├── useInspection.ts             # useInspection, useDashboard hooks
│   │   ├── useReview.ts                  # useReviewQueue, useConfirmReview, useOverrideReviewWithMessage
│   │   ├── useRules.ts                   # useRules, useRuleDetail, useCreateRule, useAddRuleVersion
│   │   └── useOfflineQueue.ts           # IndexedDB queue + auto-retry (prd.md §27)
│   ├── lib/
│   │   └── offline.ts                    # isOnline(), getOfflineMessage(), supportsOfflineStorage()
│   ├── pages/
│   │   ├── LoginPage.tsx                # Login (design.md §8.1)
│   │   ├── DashboardPage.tsx            # KPI summary + compliance chart
│   │   ├── ProcessingScreenPage.tsx     # Pipeline stepper (§8.4)
│   │   ├── ExtractedInfoPage.tsx        # Per-field confidence cards (§8.5)
│   │   ├── ComplianceResultsPage.tsx    # Verdict ticks + EvidenceCard (§8.6)
│   │   ├── InspectionDetailPage.tsx     # Inspection detail
│   │   ├── ViolationEvidencePage.tsx    # Evidence with bbox annotations
│   │   ├── ManualReviewPage.tsx         # Review queue + correction form
│   │   ├── ReportPage.tsx               # Compliance preview shell
│   │   ├── RuleManagementPage.tsx       # Rule list, version history, create/edit UI
│   │   └── __tests__/                   # 58 Vitest tests (12 files)
│   ├── styles/
│   │   ├── tokens.css                    # CSS custom properties (design.md §12)
│   │   └── globals.css                   # Resets + font imports
│   └── test/
│       └── setup.ts                     # Vitest setup
├── vite.config.ts                      # Vite + vite-plugin-pwa
├── tsconfig.json                        # Strict mode TypeScript
└── package.json                        # Dependencies
```

---

## Test Suite Summary

### Backend (540 tests)

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
| `test_pipeline.py` | 44 | 9-stage pipeline, evidence engine, PDF report |
| `test_review.py` | 26 | Review queue, corrections, confirmations |
| `test_dashboard.py` | 17 | Dashboard KPIs, trends, categories, RBAC |
| `test_report_generator.py` | 10 | PDF sections, DOCX export, scheduling |
| **Total** | **540** | **All passing** |

### Frontend (58 Vitest tests)

| Test File | Tests | Coverage |
|---|---|---|
| `components/__tests__/LedgerRow.test.tsx` | 6 | Status tick, compact spacing, props |
| `components/__tests__/MeasureRule.test.tsx` | 4 | Confidence meter ticks, baseline motif |
| `components/__tests__/ComplianceStatusBadge.test.tsx` | 4 | Status colors, variants |
| `components/__tests__/EvidenceCard.test.tsx` | 4 | Specimen card, bbox stroke-draw animation |
| `components/__tests__/Layout.test.tsx` | 2 | Desktop sidebar, mobile bottom nav render |
| `pages/__tests__/DashboardPage.test.tsx` | 3 | KPI rendering with mock data |
| `pages/__tests__/LoginPage.test.tsx` | 6 | Login form, submit, error states |
| `pages/__tests__/ManualReviewPage.test.tsx` | 8 | Queue rendering, correction form, submit |
| `pages/__tests__/ReportPage.test.tsx` | 5 | Report header, status banner, declarations |
| `pages/__tests__/RuleManagementPage.test.tsx` | 7 | Rule list, detail panel, create/edit UI |
| `pages/__tests__/ViolationEvidencePage.test.tsx` | 7 | Evidence list, bbox annotations |
| **Total** | **58** | **All passing** |

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
| State | TanStack React Query + Zustand | — |
| Offline | IndexedDB + vite-plugin-pwa (Workbox) | — |
| Database | PostgreSQL | 17 |
| Cache | Redis | 7 |
| Object Storage | MinIO | latest |

---

## Project Roadmap

| Phase | Status | Backend Tests | Frontend Tests | Description |
|---|---|---|---|---|
| Phase 0 | ✅ Complete | — | — | Scaffolding, DB schema (15 tables), CI/CD |
| Phase 1 | ✅ Complete | 76 | — | Auth, RBAC, Inspection CRUD, Audit logging |
| Phase 2 | ✅ Complete | 58 | — | Image quality gate, MinIO storage |
| Phase 3 | ✅ Complete | 75 | — | YOLO detection, PaddleOCR text extraction |
| Phase 3.3 | ✅ Complete | 56 | — | Text normalization & declaration extraction |
| Phase 4 | ✅ Complete | 62 | — | Product classification + font analysis |
| Phase 5.1 | ✅ Complete | 58 | — | Deterministic rule engine evaluator |
| Phase 5.2 | ✅ Complete | 58 | — | Rule CRUD API + Compliance Decision Engine |
| Phase 5.3 | ✅ Complete | 44 | — | Pipeline integration, evidence engine, PDF reports |
| Phase 6 | ✅ Complete | 26 | — | Evidence engine + human review queue + corrections |
| Phase 7 | ✅ Complete | 27 | — | PDF/DOCX reports + dashboard & analytics APIs |
| Phase 8 | ✅ Complete | 540 | 58 Vitest | Full frontend: design system, auth UI, workflow pages, admin pages, offline queue |
| Phase 9 | ⏳ Pending | — | — | DB hardening, demo deployment, submission |

**Phase 8 deliverables (540 backend + 58 frontend tests passing):**
- Core Docket components: LedgerRow, MeasureRule, ComplianceStatusBadge, EvidenceCard (18 tests)
- API client (Axios + JWT interceptor) and React Query hooks (useAuth, useInspection) (Phase 8.1)
- LoginPage, app shell Layout, DashboardPage wired to KPI APIs (Phase 8.2)
- Core workflow pages: InspectionDetailPage, ProcessingScreenPage, ExtractedInfoPage, ComplianceResultsPage (Phase 8.3)
- Admin pages: ManualReviewPage, ReportPage, RuleManagementPage, ViolationEvidencePage (Phase 8.4)
- Offline capture queue: useOfflineQueue (IndexedDB), OfflineBanner (Amber Flag), lib/offline, PWA SW (Phase 8.5)
- 0 TypeScript errors, 0 hardcoded colors, all 58 Vitest tests passing

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
