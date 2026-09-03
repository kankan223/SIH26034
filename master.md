# Docket Legal Metrology Compliance System — Master Reference & Navigation

**Project:** Legal Metrology (Packaged Commodities) Compliance Checking System
**SIH ID:** SIH26034
**Sponsoring Ministry:** Ministry of Consumer Affairs, Food & Public Distribution, Dept. of Consumer Affairs
**Submission Deadline:** 20 September 2026
**Team Size:** 6 students (1 backend, 1 ML/AI, 1 CV/OCR, 1 frontend, 1 DB/security/DevOps, 1 research/testing/presentation — prd.md §41)

---

## 1. Project Overview & Quick Summary

The Docket system is an automated compliance checker for packaged goods. An enforcement officer photographs a package or uploads a product listing, and the system:

1. Detects the label region (YOLO)
2. Reads text from the label (PaddleOCR, Hindi+English)
3. Extracts mandatory declarations (manufacturer, MRP, net quantity, date, etc.)
4. Determines the product category
5. Looks up applicable Legal Metrology rules for that category+date
6. Evaluates each rule against the extracted declarations
7. Produces an evidence-backed compliance report with bounding boxes for every violation
8. Stores inspection history in a queryable database
9. Provides dashboards for officers to view trends and prioritize inspections

**Why this system?** Manual inspection is slow and inconsistent across inspectors; this provides a standardized, auditable, evidence-based first-pass triage and documentation.

**Critical architectural principle:** The rule engine is **data-driven, not hard-coded**. When the Ministry amends a rule (as happened 3 times in 2025–2026 per prd.md §2.4), an admin edits a database record; the system does not need a redeploy.

---

## 2. Repository Structure & File Locations

```
sih26034-legal-metrology/
├── README.md                       # Project overview, setup quickstart, tech stack summary
├── ARCHITECTURE.md                 # System architecture diagram (ASCII or Mermaid), data flow
├── master.md                       # This file (primary entry point)
├── todo.md                         # Master task roadmap (all phases 0–9, per prd.md §40)
├── current_progress.md             # Live logbook (updated after each task completion)
├── .env.example                    # Template for environment variables (never commit real .env)
├── .gitignore                      # Ignores .env, node_modules, __pycache__, .DS_Store, etc.
├── docker-compose.yml              # Local dev: 6 services (backend, worker, frontend, postgres, redis, minio)
├── docker-compose.demo.yml         # SIH demo: production images, no internet required
├── docker-compose.test.yml         # CI: ephemeral services for test runs
│
├── backend/                        # FastAPI backend application
│   ├── app/
│   │   ├── main.py                # FastAPI app initialization, middleware setup
│   │   ├── api/
│   │   │   ├── auth.py            # POST /auth/login, /auth/refresh (prd.md §21)
│   │   │   ├── inspections.py     # CRUD + analysis orchestration (prd.md §21)
│   │   │   ├── rules.py           # Rule CRUD + versioning (prd.md §21, §12)
│   │   │   ├── dashboard.py       # KPI endpoints (prd.md §21, §23)
│   │   │   └── reviews.py         # Human review and corrections (prd.md §21, §19)
│   │   ├── services/
│   │   │   ├── image_processing.py    # Quality gate, perspective correction (prd.md §10.1)
│   │   │   ├── ocr_service.py         # PaddleOCR wrapper (prd.md §11)
│   │   │   ├── cv_detection.py        # YOLOv8 package/label detection (prd.md §10)
│   │   │   ├── extraction.py          # Declaration extraction, normalization (prd.md §14)
│   │   │   ├── classification.py      # Product category classifier (prd.md §13)
│   │   │   ├── font_analysis.py       # Font size estimation (prd.md §15)
│   │   │   ├── rule_engine.py         # Rule evaluation logic (prd.md §12)
│   │   │   ├── compliance_engine.py   # Per-field & overall verdicts (prd.md §17)
│   │   │   ├── evidence_engine.py     # Evidence object generation (prd.md §18)
│   │   │   ├── report_generator.py    # PDF/DOCX/JSON report rendering (prd.md §24)
│   │   │   ├── review_queue.py        # Manual review routing (prd.md §19)
│   │   │   ├── storage.py             # MinIO object storage client (tech-stack.md §8)
│   │   │   └── audit_service.py       # Append-only audit logging (prd.md §20.1)
│   │   ├── models/
│   │   │   └── __init__.py            # SQLAlchemy models for all 15 tables (prd.md §20)
│   │   ├── schemas/
│   │   │   ├── auth.py                # Pydantic auth request/response schemas
│   │   │   ├── inspection.py          # Pydantic inspection schemas
│   │   │   └── rule.py               # Pydantic rule schemas
│   │   ├── core/
│   │   │   ├── security.py            # Password hashing (bcrypt), JWT utilities
│   │   │   ├── rbac.py                # Role-based access control dependencies
│   │   │   ├── config.py              # Config from environment variables
│   │   │   └── constants.py           # Enums (Role, Status, Severity, etc.)
│   │   └── tasks/
│   │       └── pipeline.py            # RQ job task: full CV/OCR/extraction pipeline
│   ├── alembic/                       # Alembic migration files (one per schema change)
│   ├── scripts/
│   │   ├── seed_categories.py         # Seed product categories per prd.md §13.1
│   │   ├── seed_users.py              # Seed demo user accounts
│   │   ├── seed_rules.py              # Seed initial rule versions per prd.md §12.6
│   │   └── seed_data.py              # Master seed runner
│   ├── templates/
│   │   └── report.html                # Jinja2 PDF report template
│   ├── tests/
│   │   ├── test_security.py           # Security utility tests
│   │   ├── test_auth_login.py         # Auth endpoint tests
│   │   ├── test_rbac.py               # RBAC enforcement tests
│   │   ├── test_inspections.py        # Inspection CRUD tests
│   │   ├── test_image_processing.py   # Image quality gate tests
│   │   ├── test_storage.py            # MinIO storage tests
│   │   ├── test_cv_detection.py       # YOLO detection tests
│   │   ├── test_ocr_service.py        # OCR accuracy tests
│   │   ├── test_extraction.py         # Declaration extraction tests
│   │   ├── test_classification.py     # Product classification tests
│   │   ├── test_font_analysis.py      # Font size estimation tests
│   │   ├── test_rule_engine.py        # Rule evaluation tests
│   │   ├── test_rules_api.py          # Rule CRUD API tests
│   │   ├── test_compliance_engine.py  # Compliance decision tests
│   │   ├── test_evidence_engine.py    # Evidence generation tests
│   │   ├── test_review.py             # Human review tests
│   │   ├── test_report_generator.py   # Report generation tests
│   │   ├── test_dashboard.py          # Dashboard KPI tests
│   │   └── test_pipeline.py           # Full pipeline integration tests
│   ├── requirements.txt               # Python dependencies (tech-stack.md §17.1)
│   ├── requirements-dev.txt           # Development dependencies (pytest, mypy, ruff, etc.)
│   └── Dockerfile                     # Multi-stage: python:3.13-slim base
│
├── frontend/                       # React + Vite + TypeScript SPA
│   ├── src/
│   │   ├── main.tsx                # React entry point
│   │   ├── App.tsx                 # Root layout + router setup
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx       # Login screen (design.md §8.1)
│   │   │   ├── DashboardPage.tsx   # Dashboard with KPIs (design.md §8.2)
│   │   │   ├── NewInspectionPage.tsx # New inspection form (design.md §8.3)
│   │   │   ├── CaptureImagePage.tsx # Camera/upload (design.md §8.3)
│   │   │   ├── ProcessingPage.tsx  # Job progress (design.md §8.4)
│   │   │   ├── ExtractedInfoPage.tsx # Field review (design.md §8.5)
│   │   │   ├── ComplianceResultsPage.tsx # Verdict + violations (design.md §8.6)
│   │   │   ├── ViolationEvidencePage.tsx # Detailed evidence (design.md §8.7)
│   │   │   ├── ManualReviewPage.tsx # Human review queue (design.md §8.8)
│   │   │   ├── ReportPage.tsx      # Final report view (design.md §8.9)
│   │   │   ├── HistoryPage.tsx     # Search past inspections (design.md §8.10)
│   │   │   ├── ProductDatabasePage.tsx # Product search (design.md §8.11)
│   │   │   ├── RuleManagementPage.tsx # Admin rule CRUD (design.md §8.10)
│   │   │   ├── AdminPage.tsx       # User management (design.md §8.12)
│   │   │   └── AnalyticsPage.tsx   # Deep analytics (design.md §8.13)
│   │   ├── components/
│   │   │   ├── LedgerRow.tsx       # Core structure component (design.md §3.2)
│   │   │   ├── EvidenceCard.tsx    # Evidence specimen card (design.md §7.3)
│   │   │   ├── MeasureRule.tsx     # Confidence meter (design.md §6)
│   │   │   ├── ComplianceStatusBadge.tsx # Status mark (design.md §7.1)
│   │   │   └── Layout.tsx          # App shell with sidebar/bottom nav
│   │   ├── hooks/
│   │   │   ├── useAuth.ts          # JWT auth state
│   │   │   ├── useCamera.ts        # Camera capture logic
│   │   │   ├── useOfflineQueue.ts  # IndexedDB offline queueing
│   │   │   └── useInspection.ts    # React Query hook for inspection data
│   │   ├── api/
│   │   │   └── client.ts           # Axios client with auth interceptor
│   │   ├── styles/
│   │   │   ├── tokens.css          # Design tokens (colors, type, spacing) from design.md §12
│   │   │   └── globals.css         # Global resets, font imports, focus ring
│   │   └── lib/
│   │       ├── confidence-meter.ts # Confidence scoring logic for UI display
│   │       └── offline.ts          # Service worker + IndexedDB utilities
│   ├── public/
│   │   └── manifest.json           # PWA manifest for offline installability
│   ├── package.json                # Dependencies (tech-stack.md §17.2)
│   ├── vite.config.ts              # Vite bundler config, PWA plugin
│   ├── tsconfig.json               # TypeScript compiler options (strict mode)
│   ├── tailwind.config.js          # Tailwind CSS config extending design tokens
│   ├── postcss.config.js           # PostCSS plugins (Autoprefixer, Tailwind)
│   └── Dockerfile                  # Multi-stage: node:22-alpine build → nginx serve
│
├── ml/
│   ├── training/
│   │   ├── yolo_training.py        # YOLO fine-tuning script
│   │   ├── product_classifier_training.py # scikit-learn classifier training
│   │   └── dataset_prep.py         # prd.md §29 annotation format → training data
│   ├── evaluation/
│   │   ├── eval_metrics.py         # prd.md §30: CER, WER, mAP, F1, confusion matrices
│   │   └── performance_profiler.py # Latency benchmarks per prd.md §9
│   ├── models/
│   │   ├── package_label_detector.onnx   # YOLO model exported to ONNX
│   │   └── product_classifier.joblib     # Trained scikit-learn pipeline
│   └── README.md                   # Model training guide, data prep instructions
│
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI pipeline (lint, type-check, test, audit)
│
├── docs/
│   ├── prd.md                      # Product Requirements Document (44 sections, 1380 lines)
│   ├── design.md                   # Design system (14 sections, 450 lines)
│   ├── tech-stack.md               # Tech choices & versions (21 sections, 569 lines)
│   └── ARCHITECTURE.md             # System architecture, data flow diagrams
│
├── .phase-reports/                 # End-of-phase verification artifacts
│   ├── phase-0-results.txt
│   └── ...
│
└── SUBMISSION_CHECKLIST.md         # Pre-SIH submission verification items
```

---

## 3. Reference Reading Guide

**"I need to understand X. Where do I read?"**

### System Requirements & Design

- **What is the project trying to solve?**
  Read `prd.md` §1 (Executive Summary), §2 (Official Problem Statement Analysis)

- **What are the user personas and their workflows?**
  Read `prd.md` §3–5 (Stakeholders, Personas, Workflows A–G)

- **What does the system architecture look like?**
  Read `prd.md` §6 (Complete System Architecture + ASCII diagram), tech-stack.md §3 (Architecture-to-Stack Mapping)

- **What are the database tables and relationships?**
  Read `prd.md` §20 (Database Design, ER diagram §20.3), map to `backend/app/models/`

### API & Backend Implementation

- **What are all the API endpoints? What do they accept/return?**
  Read `prd.md` §21 (API Design, complete table with method/path/auth/request/response/errors)

- **How do I implement authentication and RBAC?**
  Read `prd.md` §25 (Security Architecture, specifically §25.2 JWT design), tech-stack.md §9 (Auth libraries)
  Implementation: `backend/app/core/rbac.py`, `backend/app/api/auth.py`, `backend/app/core/security.py`

- **What are the functional requirements for feature X?**
  Read `prd.md` §8 (Functional Requirements, FR-001 through FR-032, each with description/input/processing/output/acceptance criteria)

- **How does the rule engine work?**
  Read `prd.md` §12 (Legal Metrology Rule Engine, rule schema, versioning, execution)
  Implementation: `backend/app/services/rule_engine.py`

- **How do I handle compliance verdicts?**
  Read `prd.md` §17 (Compliance Decision Engine, decision matrix)
  Implementation: `backend/app/services/compliance_engine.py`

- **How do I seed initial data (categories, users, rules)?**
  Read `backend/scripts/seed_*.py` files; category taxonomy from prd.md §13.1, rule schema from prd.md §12.2

### Frontend & Design

- **Where do I find the design tokens (colors, type, spacing)?**
  Read `design.md` §1–2 (Color Tokens, Typography)
  CSS Variables: `frontend/src/styles/tokens.css` (auto-generated from design.md §12)

- **What is a "Ledger Row" and how do I build it?**
  Read `design.md` §3.2 (Ledger Row structure, spacing, left-edge status tick)
  Component: `frontend/src/components/LedgerRow.tsx`
  CSS: `frontend/src/styles/globals.css` (Ledger Row rule styling)

- **What is the "Measure Rule" and where does it appear?**
  Read `design.md` §6 (Measure Rule motif, 6px baseline, tick scale, appears on specific pages)
  Component: `frontend/src/components/MeasureRule.tsx`
  Appears on: Login, Dashboard, Compliance Results, Violation Evidence, Report cover

- **What are the 15 frontend pages? What should each look like?**
  Read `design.md` §8 (Page Layouts, ASCII wireframes for all 15 pages)
  Map to files: `frontend/src/pages/*Page.tsx` (each page per prd.md §22)

- **How do I style a component to match the design system?**
  Read `design.md` §12 (Implementation Notes, CSS Custom Properties)
  Example: Use `var(--color-ink)` instead of hardcoding `#1B2A41`; use `var(--font-sans)` instead of hardcoding `IBM Plex Sans`

- **What are the four core Docket components?**
  Read `design.md` §7 (Component Library): §7.1 Status Badge, §7.3 Evidence Card, §7.5 Confidence Meter
  Read `design.md` §3.2 (Ledger Row), §6 (Measure Rule)

### Computer Vision & OCR

- **How does the full CV/OCR pipeline work?**
  Read `prd.md` §10 (AI/ML/CV Pipeline, step-by-step from image through compliance)
  Implementation: `backend/app/tasks/pipeline.py` orchestrates all stages

- **What OCR engine should I use? Why?**
  Read `prd.md` §11 (OCR Design, comparison table, decision rationale)
  Choice: PaddleOCR with English + Hindi models (tech-stack.md §6)
  Implementation: `backend/app/services/ocr_service.py`

- **How do I detect package/label regions?**
  Read `prd.md` §10.2 (Models, Training, Inference — YOLO for detection)
  Implementation: `backend/app/services/cv_detection.py`
  Model artifact: `ml/models/package_label_detector.onnx`

- **How do I estimate font size from an image?**
  Read `prd.md §15` (Font Size and Readability Detection — step-by-step method, stated limitations, confidence scoring)
  Implementation: `backend/app/services/font_analysis.py`

- **How do I extract declarations from OCR text?**
  Read `prd.md` §14 (Declaration Extraction, data model, extraction methods)
  Implementation: `backend/app/services/extraction.py`

### Technology Stack

- **What are the exact versions I should install?**
  Read `tech-stack.md` §2 (Stack at a Glance, table with version lines)
  Consolidated: `tech-stack.md` §13 (Version Matrix, copy-paste into requirements.txt/package.json)

- **Why was technology X chosen over its alternatives?**
  Read `tech-stack.md` §14 (Alternatives Considered & Rejected, specific runner-up + reason for each decision)

- **What Docker setup do I need?**
  Read `tech-stack.md` §10 (DevOps, CI/CD & Deployment)
  Config: `tech-stack.md` §17.3 (docker-compose.yml example, copy-paste)

- **What environment variables do I need?**
  Read `tech-stack.md` §18 (Environment Variables Reference, complete .env.example with explanations)

- **How do I set up the project locally?**
  Read `tech-stack.md` §19 (Local Dev Setup Quickstart)

### Project Planning & Execution

- **What are the phases and what gets built in each?**
  Read `todo.md` (Master Task Roadmap, Phases 0–9 with subphases and granular tasks)

- **What is the current status? What was done recently?**
  Read `current_progress.md` (Real-Time Progress & Changelog)

- **How do I know what to work on next?**
  Read `todo.md` (find your phase/subphase, pick the next uncompleted task)
  Update `current_progress.md` after every task completion

- **When do I need to run security audits or performance tests?**
  Read `todo.md` (every Phase ends with a "Whole Phase Verification Gate" + "Security & Compliance Gate")

### Legal & Regulatory

- **What are the Legal Metrology (Packaged Commodities) Rules, 2011? What declarations are mandatory?**
  Read `prd.md` §2.4 (Legal/regulatory currency check, 2025–2026 amendments)
  Read `prd.md` §12.6 (Rule content source, note: rules are data, seeded from DoCA e-book)

- **How do I ensure rule definitions are legally accurate and not hallucinated by an LLM?**
  Read `prd.md` §12.6 (Rule content source — a human enters rule text via Rule Management UI, backed by `legal_reference` field)
  Implementation pattern: `backend/app/services/rule_engine.py` reads `rule_versions.content` from DB, never computes verdicts via LLM

### Data & Training

- **Where do I find datasets for training YOLO/OCR/classifier?**
  Read `prd.md` §28 (Dataset Strategy, public datasets list with licenses, custom collection plan)

- **How do I annotate data for YOLO/OCR?**
  Read `prd.md` §29 (Data Annotation Strategy, formats, tools like LabelImg/CVAT)

- **How do I evaluate model accuracy?**
  Read `prd.md` §30 (Model Evaluation, metrics per component, importance of false-negative minimization)

### Testing & Security

- **What kinds of tests do I need to write?**
  Read `prd.md` §31 (Testing Strategy, test matrix with unit/integration/API/frontend/ML/rule-engine/security/performance/E2E rows)

- **What security threats should I be defending against?**
  Read `prd.md` §25 (Security Architecture, threat model table)
  Implement: `backend/app/core/security.py`, `backend/app/core/rbac.py`

### Demo & SIH Submission

- **How should I demo the system at SIH Grand Finale?**
  Read `prd.md` §38 (Demo Strategy, 5–10 minute scripted flow, "wow moment" is live rule-versioning)

- **What dataset should I prepare?**
  Read `prd.md` §39 (Demo Dataset, 10–20 physical packages, must not falsely claim real manufacturer non-compliance)

- **What makes this system win against competing SIH teams?**
  Read `prd.md` §36 (SIH Winning Differentiators, 10 points, e.g., versioned rule engine, bbox-grounded evidence, confidence-aware decisions)

---

## 4. Mandatory State Protocol

**EVERY developer or AI agent working on this repository MUST:**

1. **READ FIRST** (before starting work):
   - `master.md` (this file) — 10 min
   - `todo.md` (relevant phase/subphase) — 10 min
   - `current_progress.md` (see what's already done) — 5 min
   - The specific prd.md / design.md / tech-stack.md sections referenced in your task — as needed

2. **WORK** on the assigned task per todo.md

3. **UPDATE IMMEDIATELY AFTER** completing any task:
   - Update `todo.md`: mark task as COMPLETE, update verification results
   - Update `current_progress.md`: add a changelog entry with timestamp, files modified, verification status, any blockers
   - Commit all changes with the required format (see §5 below)
   - Push to the feature branch or directly to develop (per git strategy in prd.md §42.2)

4. **NEVER COMMIT**:
   - Real `.env` values (passwords, API keys, JWT secrets)
   - `node_modules/`, `__pycache__/`, `.DS_Store`, or build artifacts
   - AI agent signatures, `Co-authored-by:` footers, or LLM attribution in commit messages
   - Placeholder code (`TODO`, `FIXME`, `XXX` in production files)
   - Hardcoded color hex values (use CSS custom properties per design.md §12)

---

## 5. Git Workflow & Commit Format

Every commit follows Conventional Commits. Template:

```
<type>(<scope>): <short description — lowercase, <50 chars>

<detailed explanation if needed — 72 chars per line>

<reference to prd.md/design.md/tech-stack.md sections>

See: prd.md §X (section name), design.md §Y (section name), tech-stack.md §Z (section name)
```

**Example:**
```
feat(auth): POST /auth/login with JWT and rate limiting

- Accepts email/password, validates against bcrypt-hashed DB passwords
- Returns access_token (60min) + refresh_token (14 days) per prd.md §25.2
- Rate limit: 5 attempts per 15min per IP (slowapi) per prd.md §25.1
- Response time: <300ms p95 per prd.md §9
- No user-existence information leaked (generic 401 on invalid credentials)

See: prd.md §21 (API), prd.md §25.2 (JWT design), tech-stack.md §9 (auth libs)
```

**Types:** `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `chore`

**Scopes:** `auth`, `db`, `ocr`, `cv`, `api`, `frontend`, `rule-engine`, `infra`, `pipeline`, `evidence`, `review`, `reports`, `dashboard`, `demo`

---

## 6. Security & Verification Schedule

| Event | When | What |
|---|---|---|
| Info-disclosure check | Before every commit | `grep -r "JWT_SECRET\|POSTGRES_PASSWORD\|MINIO_ROOT\|api.key\|sk_" --include="*.py" --include="*.tsx"` → must return 0 |
| Phase regression tests | End of each phase (todo.md "Whole Phase Verification Gate") | Run all unit/integration/E2E tests for current phase + all prior phases |
| Phase security audit | End of each phase (todo.md "Security & Compliance Gate") | Verify auth, RBAC, input validation, CORS, rate limiting per prd.md §25.1 |
| Dependency audit | Every CI run (via GitHub Actions, tech-stack.md §10) | `pip-audit`, `npm audit` → must return 0 vulns |
| Code review | Every PR | At least one reviewer from a different sub-team (not the author) |
| Pre-demo security | Before SIH Grand Finale | Full vulnerability scan (OWASP ZAP, manual review) |

---

## 7. File Locations Quick Links

**Don't know where something is? Use this tree:**

```
Project state & planning:
  └─ master.md                ← You are here
  ├─ todo.md                  ← What to build, phase by phase
  ├─ current_progress.md      ← What was built, when, by whom

Source docs (never edit these in the code repo — they're in docs/):
  ├─ prd.md                   ← Requirements (44 sections, 1380 lines)
  ├─ design.md                ← Design system (14 sections, 450 lines)
  └─ tech-stack.md            ← Tech choices & versions (21 sections, 569 lines)

Backend implementation:
  └─ backend/
      ├─ app/api/             ← API routes per prd.md §21
      ├─ app/services/        ← Core services (CV, OCR, rule engine, etc.)
      ├─ app/models/          ← SQLAlchemy models per prd.md §20
      ├─ app/core/            ← Security, RBAC, config
      ├─ app/tasks/           ← RQ pipeline orchestration
      ├─ alembic/             ← Alembic DB migrations
      ├─ scripts/             ← Seed data scripts
      ├─ templates/           ← Jinja2 report templates
      └─ tests/               ← Unit, integration, E2E tests

Frontend implementation:
  └─ frontend/
      ├─ src/pages/           ← 15 pages per prd.md §22 & design.md §8
      ├─ src/components/      ← Reusable components (LedgerRow, MeasureRule, etc.)
      ├─ src/styles/          ← tokens.css (design tokens per design.md §12)
      ├─ src/hooks/           ← React hooks (useAuth, useCamera, useOfflineQueue)
      ├─ src/api/             ← Axios client + typed API hooks
      └─ tests/               ← Component & hook tests

ML/Data:
  └─ ml/
      ├─ training/            ← YOLO, classifier training scripts
      ├─ evaluation/          ← Metrics, performance profiling per prd.md §30
      └─ models/              ← Exported YOLO .onnx, classifier .joblib

Configuration:
  ├─ docker-compose.yml       ← Local dev (tech-stack.md §17.3)
  ├─ docker-compose.demo.yml  ← SIH demo, offline (prd.md §38.3)
  ├─ .env.example             ← Environment template (tech-stack.md §18)
  └─ .github/workflows/ci.yml ← GitHub Actions (tech-stack.md §10)
```

---

## 8. Collaboration & Team Handoff

**If you're handing off to another team member:**

1. Update `current_progress.md` with your final status and any notes
2. Push all work to a feature branch or develop
3. File an issue in GitHub with:
   - Title: `[Phase X.Y] Task X.Y.Z: Task Name — Ready for Next Dev`
   - Description: link to the GitHub commit, list any blockers/technical debt
   - Assign to the next person on the rotation
4. Send a Slack/email with the link to the issue

**If you're picking up work from someone else:**

1. Read the GitHub issue (blockers, context)
2. Read `current_progress.md` (what stage are we at, what was just done)
3. Read `todo.md` for the exact task spec
4. Read the related prd.md/design.md/tech-stack.md sections
5. Start work

---

## 9. Emergency: Things Are Broken

**If a service won't start:**
- Check Docker logs: `docker compose logs <service-name>`
- Check `.env` file: are all required variables present?
- Re-read tech-stack.md §2 (service versions) — are you pinned to the right version?
- Search `current_progress.md` for similar blockers (how were they resolved before?)

**If tests fail:**
- Run the specific failing test in isolation: `pytest backend/tests/test_X.py::test_Y -vvs`
- Check prd.md §31 (testing strategy) for the expected behavior
- Look at recent `current_progress.md` entries — was this component just changed?

**If a design token isn't available:**
- Check `frontend/src/styles/tokens.css` (was it generated from design.md §12?)
- Search for the token name in `design.md` (§1–2)
- If missing, manually add it per design.md §12's CSS custom properties format

**If a rule is failing when it shouldn't:**
- Check `backend/app/models/` — is the rule version correctly linked to the inspection?
- Check prd.md §12.4 (rule versioning & effective dates) — does the rule version's `effective_date` match the inspection's timestamp?
- Verify the rule's `legal_reference` is not empty (prd.md §12.6 requirement)

**If the pipeline fails midway:**
- Check RQ worker logs: `docker compose logs worker`
- Verify all services are healthy: `docker compose ps`
- Check if the specific pipeline stage (OCR, detection, extraction) has a known issue in `current_progress.md`
- The pipeline retries ×2 with backoff per prd.md §33; after exhausting retries, the inspection is marked `analysis_failed`

---

## 10. SIH Submission Checklist (2 weeks before 20 September 2026)

- [ ] Read prd.md §36 (SIH Winning Differentiators) — all 10 are implemented and demoed
- [ ] Read prd.md §38 (Demo Strategy) — 5–10 min scripted flow, rehearsed 2× without breaking
- [ ] Read prd.md §39 (Demo Dataset) — 10–20 physical packages prepared, zero false claims
- [ ] GitHub repo README: includes architecture diagram, tech stack, setup quickstart, design system link
- [ ] No commits with secrets: info-disclosure check passes (`grep -r "JWT_SECRET\|POSTGRES_PASSWORD" ...` returns 0)
- [ ] Live demo works 100% offline: no internet required (prd.md §38.3)
- [ ] All FRs in prd.md §8 are checked in end-to-end tests
- [ ] All NFRs in prd.md §9 are met: OCR <8s, API <300ms, reports <10s
- [ ] No production code has TODO/FIXME/XXX (code review checklist from §5 above)
- [ ] Design system enforced: no hardcoded colors, all components use tokens per design.md §12
- [ ] Audit logs are append-only, DB grants verified (prd.md §20.1)
- [ ] Rule versioning demonstrated: change a rule mid-demo, old inspections unaffected
- [ ] Create a `.git/hooks/pre-commit` that runs info-disclosure + code checks locally before allowing commits

**Submit by:** 20 September 2026 (prd.md §0)

---

## ANTI-HALLUCINATION & GROUNDING RULES

1. **Every task in todo.md must cite prd.md section(s).** No ungrounded tasks.
2. **Every component in frontend must cite design.md section(s).** No colors or typography not in design tokens.
3. **Every dependency version must cite tech-stack.md.** No "I'll use the latest" — pin it.
4. **Every database table must cite prd.md §20 schema.** No tables invented mid-project.
5. **Every API endpoint must cite prd.md §21 API Design table.** No endpoints without documented auth/request/response.
6. **Rule engine is deterministic and DB-driven (prd.md §12), never LLM-based.** Violations are evaluated by rule records, not by prompting an AI.
7. **No speculative code.** Every function is complete and tested. No `// TODO`, `pass`, or mock responses in production branches.

---

## Document Version History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-09-01 | Team SIH26034 | Initial master reference document |
