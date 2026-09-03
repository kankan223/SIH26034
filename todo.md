# Docket Legal Metrology Compliance System — Master Task Roadmap
**Project:** SIH26034 · **Deadline:** 20 September 2026 · **Team Size:** 6 students

---

## Phase 0: Project Scaffolding, Environment Setup & Database Migrations

**Scope:** Infrastructure, tooling, schema, local development environment
**Primary Reference:** prd.md §40 Phase 0, §43 Deployment, §20 Database Design
**Design System Reference:** design.md §12 (CSS Custom Properties)
**Tech Stack Reference:** tech-stack.md §10 DevOps, §17–18 Dependency Manifests

---

### Subphase 0.1: Docker Compose & Environment Configuration

**Objective:** Team members can run the entire application stack locally with a single command.

#### Task 0.1.1: Create docker-compose.yml (development configuration)

**Description:**
Build a Docker Compose file that orchestrates: FastAPI backend, RQ worker, React frontend (Vite dev server), PostgreSQL, Redis, MinIO, Nginx reverse proxy. Reference tech-stack.md §17.3 for the example compose file.

**Input Required:**
- tech-stack.md §17.3 (docker-compose.yml skeleton)
- tech-stack.md §2 (service versions: Python 3.13, Node 22, Postgres 17, Redis 7, MinIO latest)

**Processing:**
- [ ] Copy the skeleton from tech-stack.md §17.3 and expand it with:
  - Volume mounts for hot-reload (backend: ./backend → /app, frontend: ./frontend → /app)
  - Environment variable pass-through from .env file
  - Service health checks (pg_isready for Postgres, redis-cli ping for Redis)
  - Network configuration (all services on a shared 'docket-network')
  - Port mappings per tech-stack.md §19 (backend 8000, frontend 5173, MinIO 9000, Postgres 5432, Redis 6379)

**Output:**
- `./docker-compose.yml` (development version, ~80 lines)

**Verification Tasks:**
1. Run `docker compose up --build` from the repo root → all services start successfully
2. Run `docker compose logs backend | grep "Application startup complete"` → backend is serving
3. Run `curl http://localhost:8000/docs` → FastAPI OpenAPI page loads (returns 200)
4. Run `docker compose exec frontend npm run build` → frontend build works
5. Run `docker compose down && docker compose up` → cleanup/restart cycles work

**Regression Check:** N/A (first task in Phase 0)

**Git Instructions:**
```bash
git add docker-compose.yml
git commit -m "feat(infra): docker-compose for local development with 6 services

- Postgres 17, Redis 7, MinIO latest, Nginx 1.27
- FastAPI backend (hot-reload on code change)
- Vite dev server for React frontend
- RQ worker for async jobs
- Health checks on all services
- Network isolation (docket-network)

See: tech-stack.md §17.3 (compose example), tech-stack.md §2 (versions)
"
git push origin feature/phase-0-docker-compose
```

---

#### Task 0.1.2: Create .env.example template

**Description:**
Create the environment variable template that every developer will copy to their local .env file (which is git-ignored). Reference tech-stack.md §18 for the complete template.

**Input Required:**
- tech-stack.md §18 (.env.example provided in full)
- prd.md §25 (security constraints: JWT_SECRET_KEY must be ≥32 bytes, bcrypt cost ≥12)

**Processing:**
- [ ] Copy tech-stack.md §18's .env.example into the repo root
- [ ] Verify every variable is documented with a 1-line comment explaining its purpose
- [ ] Verify no real secrets are present (all values are placeholders like "changeme" or example values)
- [ ] Cross-check against prd.md §9 (NFR performance targets), prd.md §25 (security requirements)

**Output:**
- `./.env.example` (~45 lines with comments)

**Verification Tasks:**
1. `grep -E "^(#|[A-Z_]+\s*=)" .env.example | wc -l` → ≥40 lines (all vars + comments documented)
2. `grep -E "(password|secret|key)" .env.example | wc -l` → ≥3 (sensitive vars documented)
3. `grep "(changeme|example|fill.in)" .env.example | wc -l` → ≥5 (no real secrets leaked)
4. Copy to `.env` and run `source .env` → no syntax errors

**Regression Check:** N/A

**Git Instructions:**
```bash
git add .env.example
git commit -m "feat(infra): environment variable template

- 18 variables covering database, Redis, MinIO, auth, ML/CV models
- All secrets marked 'changeme' (never commit real values)
- Comments explain each variable's purpose per tech-stack.md §18

See: tech-stack.md §18 (env reference)
"
git push origin feature/phase-0-env-template
```

---

#### Task 0.1.3: Create .gitignore

**Description:**
Create a comprehensive .gitignore that prevents secrets, build artifacts, and OS files from being committed. Must cover Python, Node.js, Docker, and OS-specific patterns.

**Input Required:**
- tech-stack.md §19 (local dev setup paths)
- prd.md §42.2 (secrets management, .env ignored)

**Processing:**
- [ ] Include Python patterns: `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`
- [ ] Include Node patterns: `node_modules/`, `dist/`, `build/`
- [ ] Include env/secrets: `.env`, `*.env.local`
- [ ] Include OS: `.DS_Store`, `Thumbs.db`
- [ ] Include ML artifacts: `*.onnx`, `*.joblib` (large model files)
- [ ] Include IDE: `.vscode/`, `.idea/`
- [ ] Include Docker: `docker-compose.override.yml`
- [ ] Include test/coverage: `htmlcov/`, `.coverage`, `coverage/`

**Output:**
- `./.gitignore` (~60 lines)

**Verification Tasks:**
1. `git status` after creating → .gitignore appears as untracked
2. Create a test `.env` file → `git status` does not show it as untracked
3. Create a test `__pycache__` dir → `git status` does not show it

**Regression Check:** N/A

**Git Instructions:**
```bash
git add .gitignore
git commit -m "chore(infra): comprehensive .gitignore for Python, Node, Docker, ML

- Excludes .env, node_modules, __pycache__, *.onnx, *.joblib
- Prevents accidental secret commits per prd.md §42.2
"
git push origin feature/phase-0-gitignore
```

---

### Subphase 0.2: Database Schema & Alembic Migrations

**Objective:** All 15 database tables from prd.md §20 are defined as Alembic migrations, reversible and testable.

#### Task 0.2.1: Initialize backend project structure

**Description:**
Create the FastAPI backend directory structure with proper Python packaging, including the main app entry point, configuration loading, and module layout per prd.md §42.1.

**Input Required:**
- prd.md §42.1 (repository structure)
- tech-stack.md §3 (architecture-to-stack mapping)
- tech-stack.md §17.1 (requirements.txt dependencies)

**Processing:**
- [ ] Create `backend/app/__init__.py`
- [ ] Create `backend/app/main.py` with FastAPI app initialization
- [ ] Create `backend/app/core/__init__.py`
- [ ] Create `backend/app/core/config.py` with Settings class loading from environment
- [ ] Create `backend/app/api/__init__.py`
- [ ] Create `backend/app/services/__init__.py`
- [ ] Create `backend/app/models/__init__.py`
- [ ] Create `backend/app/schemas/__init__.py`
- [ ] Create `backend/requirements.txt` per tech-stack.md §17.1
- [ ] Create `backend/Dockerfile` (multi-stage: python:3.13-slim base)
- [ ] Create `backend/tests/__init__.py`

**Output:**
- `backend/` directory tree with all __init__.py files and main.py
- `backend/requirements.txt` with pinned versions
- `backend/Dockerfile`

**Verification Tasks:**
1. `python -c "from fastapi import FastAPI; print('OK')"` → FastAPI importable
2. `docker compose exec backend python -c "from app.main import app; print(app.title)"` → app loads
3. `ls backend/app/api/ backend/app/services/ backend/app/models/ backend/app/schemas/` → all directories exist

**Regression Check:** N/A

**Git Instructions:**
```bash
git add backend/
git commit -m "feat(backend): initialize FastAPI project structure

- Main app entry point with middleware setup
- Core config module loading from environment variables
- Module layout: api/, services/, models/, schemas/, core/
- Dockerfile (python:3.13-slim, multi-stage)
- Requirements with pinned versions per tech-stack.md §17.1

See: prd.md §42.1 (repo structure), tech-stack.md §3 (architecture mapping)
"
git push origin feature/phase-0-backend-structure
```

---

#### Task 0.2.2: Initialize frontend project structure

**Description:**
Create the React + Vite + TypeScript frontend with Tailwind CSS configured to use Docket design tokens. Reference tech-stack.md §4 and design.md §12.

**Input Required:**
- tech-stack.md §4 (frontend stack detail)
- tech-stack.md §17.2 (package.json dependencies)
- design.md §12 (CSS custom properties / tokens)
- design.md §2 (typefaces and type scale)

**Processing:**
- [ ] Initialize Vite React-TS project in `frontend/`
- [ ] Install dependencies per tech-stack.md §17.2 (react, react-dom, react-router-dom, @tanstack/react-query, zustand, react-hook-form, zod, recharts, lucide-react, axios)
- [ ] Install dev dependencies (typescript, vite, tailwindcss, postcss, autoprefixer, eslint, prettier, vitest, @testing-library/react, @playwright/test, openapi-typescript)
- [ ] Configure `tailwind.config.js` extending with design tokens from design.md §12
- [ ] Create `frontend/src/styles/tokens.css` with CSS custom properties from design.md §12
- [ ] Create `frontend/src/styles/globals.css` with resets and font imports
- [ ] Create `frontend/src/App.tsx` with React Router setup
- [ ] Create `frontend/src/main.tsx` entry point
- [ ] Create `frontend/Dockerfile` (multi-stage: node:22-alpine build → nginx serve)
- [ ] Create `frontend/vite.config.ts` with PWA plugin
- [ ] Create `frontend/tsconfig.json` with strict mode

**Output:**
- `frontend/` project with Vite dev server working
- `frontend/src/styles/tokens.css` containing all design.md §12 CSS variables

**Verification Tasks:**
1. `docker compose exec frontend npm run dev` → Vite dev server starts on port 5173
2. `docker compose exec frontend npm run build` → production build completes without errors
3. `docker compose exec frontend npx tsc --noEmit` → TypeScript compiles without errors
4. `cat frontend/src/styles/tokens.css | grep -- "--color-ink"` → design token present

**Regression Check:** N/A

**Git Instructions:**
```bash
git add frontend/
git commit -m "feat(frontend): initialize React + Vite + TypeScript project

- Vite 5.x with React 18, TypeScript 5.x, Tailwind CSS 3.x
- Design tokens from design.md §12 in tokens.css (colors, type, spacing)
- PWA plugin for offline capture capability
- Multi-stage Dockerfile (node:22-alpine → nginx)
- Strict TypeScript configuration

See: tech-stack.md §4 (frontend stack), design.md §12 (CSS tokens)
"
git push origin feature/phase-0-frontend-structure
```

---

#### Task 0.2.3: Initialize SQLAlchemy models and Alembic migrations

**Description:**
Set up SQLAlchemy + Alembic in the backend, then create all 15 model classes per prd.md §20 and generate the initial migration file.

**Input Required:**
- prd.md §20 (complete schema: 15 tables with fields, types, relationships)
- prd.md §20.2 (indexes to define)
- tech-stack.md §5 (SQLAlchemy 2.0.x, Alembic 1.13.x)

**Processing:**
- [ ] Create `backend/app/models/__init__.py` with SQLAlchemy declarative base
- [ ] Create model classes for all 15 tables: users, products, categories, inspections, images, ocr_results, declarations, rules, rule_versions, compliance_checks, violations, evidence, corrections, reports, audit_logs
- [ ] Each model must have:
  - Primary key (UUID or auto-increment)
  - All fields per prd.md §20 with correct types
  - Foreign key relationships to other models
  - Docstring explaining the table's purpose and prd.md section reference
- [ ] Define enums: Role (inspector/senior_officer/admin), InspectionStatus, OverallStatus, Verdict, Severity, Source
- [ ] Initialize Alembic: `alembic init backend/alembic`
- [ ] Configure `alembic.ini` to point to the correct database URL
- [ ] Generate initial migration: `alembic revision --autogenerate -m "create initial schema"`
- [ ] Verify migration file contains all 15 CREATE TABLE statements
- [ ] Test that `alembic upgrade head` applies successfully

**Output:**
- `backend/app/models/` with all 15 model classes
- `backend/alembic/versions/001_create_initial_schema.py`
- `backend/alembic.ini`

**Verification Tasks:**
1. `alembic current` → returns current schema version (initially at base or empty)
2. `alembic upgrade head` → applies schema, returns "Running upgrade" messages
3. `psql -d legal_metrology -c "\dt"` → lists all 15 tables
4. Verify each table has correct column count per prd.md §20.1
5. `alembic downgrade -1` → rolls back migration, tables disappear (reversibility check)
6. `alembic upgrade head` → reapplies migration successfully (idempotency check)

**Regression Check:** N/A

**Git Instructions:**
```bash
git add backend/app/models/ backend/alembic/ backend/alembic.ini
git commit -m "feat(db): initialize SQLAlchemy models and Alembic migrations

- All 15 tables per prd.md §20: users, products, categories, inspections,
  images, ocr_results, declarations, rules, rule_versions, compliance_checks,
  violations, evidence, corrections, reports, audit_logs
- Foreign key relationships and indexes defined
- Initial migration auto-generated via alembic revision --autogenerate
- Migration tested: upgrade/downgrade cycles work, schema is reversible

See: prd.md §20 (schema definition), tech-stack.md §5 (SQLAlchemy/Alembic versions)
"
git push origin feature/phase-0-db-schema
```

---

### Subphase 0.3: CI/CD Pipeline & Git Configuration

**Objective:** GitHub Actions pipeline runs on every push, enforcing code quality and preventing accidental secret commits.

#### Task 0.3.1: Create GitHub Actions CI workflow

**Description:**
Set up `.github/workflows/ci.yml` that runs: lint (ruff), type-check (mypy), unit tests (pytest), dependency audit (pip-audit), and an info-disclosure check.

**Input Required:**
- tech-stack.md §10 (CI/CD pipeline design)
- prd.md §42.2 (git strategy, security requirements)

**Processing:**
- [ ] Create `.github/workflows/ci.yml` with:
  - Trigger: on push to all branches, on PR
  - Python 3.13 and Node 22 setup
  - Step 1: `ruff check backend/` (Python lint)
  - Step 2: `mypy app/services/rule_engine app/services/compliance_engine` (strict type checking on critical modules)
  - Step 3: `pytest backend/tests/ -v` (run unit tests)
  - Step 4: `pip-audit` (check for known CVEs)
  - Step 5: `cd frontend && npm audit` (check frontend dependencies)
  - Step 6: `npx tsc --noEmit` (frontend type check)
  - Step 7: Info-disclosure check:
    ```bash
    if git diff --cached | grep -E "JWT_SECRET|POSTGRES_PASSWORD|MINIO_ROOT|api.key|sk_"; then
      echo "ERROR: Secrets detected in commit"
      exit 1
    fi
    ```
  - Fail the pipeline if any step fails

**Output:**
- `.github/workflows/ci.yml` (~100 lines)

**Verification Tasks:**
1. Push a test commit with a real JWT secret in a Python file → CI fails with "Secrets detected" error
2. Push a clean commit → all steps pass (or skip if no tests exist yet)
3. Verify CI status appears on GitHub PR/commit

**Regression Check:** N/A

**Git Instructions:**
```bash
git add .github/workflows/ci.yml
git commit -m "feat(ci): GitHub Actions pipeline with lint, type-check, tests, audits

- Ruff for Python linting
- Mypy strict type-checking on rule_engine and compliance_engine modules
- Pytest for unit/integration tests
- pip-audit and npm audit for dependency CVE scanning
- Info-disclosure check prevents secrets in commits

See: tech-stack.md §10 (CI/CD design), prd.md §42.2 (git strategy)
"
git push origin feature/phase-0-ci-pipeline
```

---

#### Task 0.3.2: Create seed data scripts

**Description:**
Create Python scripts that seed the database with demo users, initial product categories per prd.md §13.1, and starter rule versions per prd.md §12.6. These scripts run as part of the demo setup.

**Input Required:**
- prd.md §13.1 (product category taxonomy)
- prd.md §12.2 (rule schema)
- prd.md §41 (team roles — user accounts for demo)
- tech-stack.md §18 (environment variables for DB connection)

**Processing:**
- [ ] Create `backend/scripts/seed_categories.py` with the taxonomy from prd.md §13.1
- [ ] Create `backend/scripts/seed_users.py` with demo accounts (inspector, senior_officer, admin)
- [ ] Create `backend/scripts/seed_rules.py` with initial rule versions for core declarations (MRP format, net quantity, manufacturer details, date, consumer care)
- [ ] Create `backend/scripts/seed_data.py` as a master runner that calls all seed scripts in order
- [ ] Each seed script must be idempotent (safe to run multiple times without duplicating data)

**Output:**
- `backend/scripts/seed_*.py` scripts
- Scripts run successfully against an empty database

**Verification Tasks:**
1. `docker compose exec backend python -m scripts.seed_data` → completes without errors
2. `psql -d legal_metrology -c "SELECT count(*) FROM categories"` → returns expected category count
3. `psql -d legal_metrology -c "SELECT count(*) FROM users"` → returns 3 demo users
4. `psql -d legal_metrology -c "SELECT count(*) FROM rule_versions"` → returns seeded rule versions
5. Run seed scripts a second time → no duplicate rows created

**Regression Check:** N/A

**Git Instructions:**
```bash
git add backend/scripts/
git commit -m "feat(db): seed data scripts for demo categories, users, and rules

- Product category taxonomy per prd.md §13.1
- Demo users: inspector, senior_officer, admin per prd.md §41
- Starter rule versions per prd.md §12.6 (MRP format, net quantity, etc.)
- Idempotent scripts safe to run multiple times

See: prd.md §13.1 (taxonomy), prd.md §12.6 (rule content source)
"
git push origin feature/phase-0-seed-data
```

---

### Phase 0 Milestone: Whole Phase Verification Gate

```bash
# Phase 0 Comprehensive Test
docker compose up --build -d
sleep 10
docker compose exec -T postgres psql -U app_user -d legal_metrology -c "\dt" | wc -l  # Should show 15+ tables
docker compose exec -T backend alembic current  # Should show current migration version
curl http://localhost:8000/docs  # Should return 200
docker compose logs | grep -E "error|failed" | wc -l  # Should be 0

# If all pass:
echo "Phase 0 COMPLETE: Infra ready for development"
```

---

## Phase 1: Auth, RBAC & Core Inspection Service Infrastructure

**Scope:** Authentication system, role-based access control, inspection CRUD endpoints, database audit logging
**Primary Reference:** prd.md §21 API, prd.md §25 Security, prd.md §8.5 FR-029/FR-030 (authentication/RBAC)
**Design System Reference:** design.md §11 Voice & Microcopy (login page copy)
**Tech Stack Reference:** tech-stack.md §9 Auth libs, tech-stack.md §13 JWT version pins

---

### Subphase 1.1: Authentication Endpoints & JWT Token Flow

#### Task 1.1.1: Implement security utilities (password hashing, JWT)

**Description:**
Create the core security module with password hashing (bcrypt, cost≥12) and JWT token generation/verification per prd.md §25.2.

**Input Required:**
- prd.md §25.1 (bcrypt cost ≥12, access token ≤60min expiry)
- prd.md §25.2 (JWT structure: user_id, role, exp)
- tech-stack.md §9 (passlib, python-jose libraries)

**Processing:**
- [ ] Create `backend/app/core/security.py` with:
  - Password hashing function using passlib.context with bcrypt, cost=12
  - Password verification function
  - Access token generation (exp: +60min, claims: user_id, role)
  - Refresh token generation (exp: +14 days, claims: user_id)
  - Token verification/decode function
  - `get_password_hash()` and `verify_password()` utilities
- [ ] Load JWT_SECRET_KEY from environment (tech-stack.md §18)
- [ ] Use HS256 algorithm per tech-stack.md §18 (JWT_ALGORITHM=HS256)

**Output:**
- `backend/app/core/security.py` (~80 lines)

**Verification Tasks:**
1. Unit test: `hash_password("test")` produces a bcrypt hash starting with `$2b$`
2. Unit test: `verify_password("test", hash)` returns True
3. Unit test: `verify_password("wrong", hash)` returns False
4. Unit test: `create_access_token(user_id=1, role="inspector")` produces a decodable JWT
5. Unit test: decoded JWT contains `user_id`, `role`, `exp` claims

**Regression Check:** N/A

**Git Instructions:**
```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(auth): password hashing and JWT token utilities

- bcrypt cost factor 12 minimum per prd.md §25.1
- Access token (60min) and refresh token (14 days) per prd.md §25.2
- HS256 signing with secret from environment per tech-stack.md §18
- All functions unit-tested for correctness

See: prd.md §25.1 (security), tech-stack.md §9 (auth libs)
"
git push origin feature/phase-1-security-utils
```

---

#### Task 1.1.2: Implement POST /auth/login endpoint

**Description:**
Create the login endpoint that accepts email/password, validates against hashed passwords in the DB, and returns access + refresh tokens per prd.md §21.

**Input Required:**
- prd.md §21 (API contract: POST /auth/login request/response)
- prd.md §9 (target: API response time ≤300ms p95)
- tech-stack.md §9 (slowapi for rate limiting)

**Processing:**
- [ ] Create `backend/app/api/auth.py` with:
  - `/auth/login` route (POST)
  - Request model: Pydantic schema with `email` (str, email validation) and `password` (str)
  - Lookup user in DB by email
  - Compare password against stored hash using verify_password()
  - If invalid: return 401 with message "Invalid email or password" (no info leakage)
  - If valid: generate access token and refresh token
  - Apply @slowapi rate limiter: max 5 login attempts per IP per 15 minutes (prd.md §25.1)
  - Return response: `{access_token, refresh_token, token_type: "bearer", user: {id, email, role}}`
- [ ] Create `backend/app/api/auth.py` with `/auth/refresh` route (POST)
- [ ] Create Pydantic schemas in `backend/app/schemas/auth.py`
- [ ] Add CORS middleware configuration per tech-stack.md §9

**Output:**
- `backend/app/api/auth.py` (~120 lines)
- `backend/app/schemas/auth.py` (~40 lines)
- Unit test: `backend/tests/test_auth_login.py`

**Verification Tasks:**
1. POST to http://localhost:8000/api/v1/auth/login with valid credentials → returns 200 with access_token
2. POST with invalid password → returns 401, message is generic (no "user found" leak)
3. POST 6 times in 10 seconds from same IP → 6th returns 429 (rate limiting)
4. POST returns `{access_token, refresh_token, token_type, user}` per prd.md §21 schema
5. Measure latency: `time curl -X POST ...` → ≤300ms (prd.md §9)
6. Inspect JWT token: `jwt.decode(access_token, ...)` → has `exp`, `user_id`, `role` claims
7. POST /auth/refresh with valid refresh_token → returns new access_token

**Regression Check:** N/A (auth is new)

**Git Instructions:**
```bash
git add backend/app/api/auth.py backend/app/schemas/auth.py backend/tests/test_auth_login.py
git commit -m "feat(auth): POST /auth/login with JWT and rate limiting

- Accepts email/password, validates against bcrypt-hashed DB passwords
- Returns access_token (60min) + refresh_token (14 days) per prd.md §25.2
- Rate limit: 5 attempts per 15min per IP (slowapi) per prd.md §25.1
- Response time: <300ms p95 per prd.md §9
- No user-existence information leaked (generic 401 on invalid credentials)

See: prd.md §21 (API), prd.md §25.2 (JWT design), tech-stack.md §9 (auth libs)
"
git push origin feature/phase-1-auth-login
```

---

### Subphase 1.2: RBAC Middleware & Role-Gated Routes

#### Task 1.2.1: Implement FastAPI dependency for role-based access

**Description:**
Create a FastAPI Depends-compatible function that validates JWT, extracts the user's role, and ensures they have permission for the route they're accessing. Per prd.md §21, routes have explicit role requirements.

**Input Required:**
- prd.md §21 (role-gated routes table)
- prd.md §8.5 FR-030 (three roles: inspector, senior_officer, admin)
- prd.md §25.2 (JWT structure)

**Processing:**
- [ ] Create `backend/app/core/rbac.py` with:
  - `get_current_user()` dependency: decode JWT, return user object, or raise 401 if invalid
  - `require_role(*allowed_roles)` dependency: check user.role in allowed_roles, raise 403 if not
  - Enum for roles: `Role.INSPECTOR`, `Role.SENIOR_OFFICER`, `Role.ADMIN`
- [ ] Create `backend/app/core/constants.py` with shared enums (Role, InspectionStatus, OverallStatus, Verdict, Severity, Source)
- [ ] Apply to every route in prd.md §21:
  - `/inspections` (POST): `@require_role(Role.INSPECTOR, Role.SENIOR_OFFICER)`
  - `/rules` (POST): `@require_role(Role.ADMIN)`
  - `/dashboard` (GET): `@require_role(Role.SENIOR_OFFICER, Role.ADMIN)`
  - etc.
- [ ] Test that:
  - An inspector token accessing `/rules` (POST) returns 403
  - An admin token accessing `/rules` (POST) returns 200 (or downstream error, not auth error)

**Output:**
- `backend/app/core/rbac.py` (~60 lines)
- `backend/app/core/constants.py` (~40 lines)
- Unit test: `backend/tests/test_rbac.py`

**Verification Tasks:**
1. Call `/inspections` (POST) with inspector token → succeeds (or 400 from missing data, not 403)
2. Call `/rules` (POST) with inspector token → returns 403 "Insufficient permissions"
3. Call `/rules` (POST) with admin token → proceeds to endpoint logic
4. Call any endpoint without Authorization header → returns 401 "Missing or invalid authorization"
5. Call with expired access_token → returns 401 "Token expired"

**Regression Check:** N/A

**Git Instructions:**
```bash
git add backend/app/core/rbac.py backend/app/core/constants.py backend/tests/test_rbac.py
git commit -m "feat(rbac): role-based access control on all API routes

- get_current_user() dependency extracts JWT, validates signature, returns user
- require_role(*roles) dependency checks user.role against allowed roles per prd.md §21
- Three roles: inspector, senior_officer, admin per prd.md §8.5 FR-030
- Default-deny: routes without explicit role check are inaccessible
- Shared enums (Role, Status, Severity) in constants.py

See: prd.md §21 (role-gated routes), prd.md §25.2 (JWT structure)
"
git push origin feature/phase-1-rbac
```

---

### Subphase 1.3: Inspection CRUD & Audit Logging

#### Task 1.3.1: Implement inspection CRUD endpoints

**Description:**
Create the inspection service and API endpoints for creating, reading, updating, and listing inspections per prd.md §21.

**Input Required:**
- prd.md §21 (API: POST /inspections, GET /inspections/{id}, GET /inspections, POST /inspections/{id}/images)
- prd.md §20 (inspections table schema)

**Processing:**
- [ ] Create `backend/app/services/inspection_service.py` with CRUD operations
- [ ] Create `backend/app/api/inspections.py` with FastAPI routes
- [ ] Create `backend/app/schemas/inspection.py` with Pydantic models
- [ ] Implement image upload endpoint with MIME validation per prd.md §25.5
- [ ] Implement MinIO upload for images per tech-stack.md §8
- [ ] Apply RBAC: inspectors see own/region inspections, admins see all

**Output:**
- `backend/app/api/inspections.py` (~150 lines)
- `backend/app/services/inspection_service.py` (~100 lines)
- `backend/app/schemas/inspection.py` (~60 lines)
- Unit test: `backend/tests/test_inspections.py`

**Verification Tasks:**
1. POST /inspections with inspector token → creates inspection with status "draft"
2. GET /inspections/{id} → returns full inspection object
3. POST /inspections/{id}/images with valid JPEG → returns image_id and quality_score
4. POST /inspections/{id}/images with non-image file → returns 400
5. GET /inspections with filters → returns paginated results
6. Audit log entry created for every state change

**Regression Check:** Auth tests still pass (Phase 1.1)

**Git Instructions:**
```bash
git add backend/app/api/inspections.py backend/app/services/inspection_service.py backend/app/schemas/inspection.py backend/tests/test_inspections.py
git commit -m "feat(api): inspection CRUD endpoints with image upload

- POST /inspections creates draft inspection record
- POST /inspections/{id}/images with MIME validation per prd.md §25.5
- GET /inspections with region/status/date filters
- MinIO storage for uploaded images
- Audit log entries for every state change

See: prd.md §21 (API design), prd.md §20 (schema)
"
git push origin feature/phase-1-inspection-crud
```

---

#### Task 1.3.2: Implement audit logging service

**Description:**
Create the append-only audit logging service that records every state-changing action with actor, action, entity, before/after values per prd.md §20.1 and §31.

**Input Required:**
- prd.md §20.1 (audit_logs table: append-only, no UPDATE/DELETE grant)
- prd.md §8.5 FR-031 (audit trail requirement), prd.md §20.1 (audit_logs table definition)

**Processing:**
- [ ] Create `backend/app/services/audit_service.py` with `log_action()` function
- [ ] Integrate audit logging into all CRUD endpoints (inspections, rules, corrections)
- [ ] Configure DB grants: application role has SELECT + INSERT only on audit_logs table
- [ ] Create Alembic migration to apply DB-level grants

**Output:**
- `backend/app/services/audit_service.py` (~50 lines)
- Audit log entries created for every write operation
- DB grant migration

**Verification Tasks:**
1. Create an inspection → audit_logs has a row with actor_id, action="create", entity_type="inspection"
2. Update an inspection status → audit_logs has before_value and after_value
3. `psql -c "SELECT grant_type FROM information_schema.role_table_grants WHERE table_name='audit_logs'"` → only SELECT and INSERT
4. Attempt UPDATE on audit_logs as application role → permission denied

**Regression Check:** All previous tests still pass

**Git Instructions:**
```bash
git add backend/app/services/audit_service.py backend/alembic/versions/
git commit -m "feat(audit): append-only audit logging with DB-level enforcement

- log_action() captures actor, action, entity, before/after values
- Integrated into all CRUD endpoints
- DB grants: app role has SELECT + INSERT only on audit_logs
- Alembic migration for grant enforcement

See: prd.md §20.1 (audit_logs table), prd.md §25.1 (audit trail)
"
git push origin feature/phase-1-audit-logging
```

---

### Phase 1 Milestone: Whole Phase Verification Gate

```bash
# Phase 1 Comprehensive Test
pytest backend/tests/test_auth*.py backend/tests/test_rbac.py backend/tests/test_inspections.py -v
curl -X POST http://localhost:8000/api/v1/auth/login -d '{"email": "test@example.com", "password": "correct"}' | jq .access_token
# Verify response contains valid JWT with role claim
# Test RBAC: inspector token on /rules (POST) → 403
# Test RBAC: admin token on /rules (POST) → proceeds
# Verify audit log entries exist
```

---

## Phase 2: Image Ingestion, Quality Check & Storage Subsystem

**Scope:** Image quality gate, MinIO storage, image preprocessing pipeline
**Primary Reference:** prd.md §22 pages 3–4, FR-001/002/003, §43 object storage
**Design System Reference:** design.md §8.3 (Image Capture page wireframe)
**Tech Stack Reference:** tech-stack.md §6 CV libs, tech-stack.md §8 (MinIO storage)

---

### Subphase 2.1: Image Quality Gate

#### Task 2.1.1: Implement image quality assessment (blur, exposure, resolution)

**Description:**
Build the image quality gate that scores uploaded images for blur (Laplacian variance), exposure (histogram analysis), and minimum resolution per prd.md §10.1 and FR-003.

**Input Required:**
- prd.md §10.1 (pipeline: Image Quality Gate → Laplacian-variance blur score)
- prd.md FR-003 (quality_score 0–1, quality_issues array)
- tech-stack.md §6 (opencv-python for image processing)

**Processing:**
- [ ] Create `backend/app/services/image_processing.py` with:
  - `assess_quality(image_bytes) -> QualityResult` function
  - Laplacian variance blur detection (threshold calibrated, not arbitrary)
  - Histogram-based exposure check (over/under-exposure detection)
  - Minimum dimension check (640×480 floor per FR-001)
  - Returns: quality_score (0–1), quality_issues[] (e.g., ["blurry", "glare"])
- [ ] Integrate into image upload endpoint (POST /inspections/{id}/images)
- [ ] If quality_score below threshold: return warning in response, but still accept image (inspector decides)

**Output:**
- `backend/app/services/image_processing.py` (~80 lines)
- Unit test: `backend/tests/test_image_processing.py`

**Verification Tasks:**
1. Upload a sharp, well-lit image → quality_score > 0.8, quality_issues is empty
2. Upload a blurry image → quality_score < 0.5, quality_issues includes "blurry"
3. Upload an overexposed image → quality_issues includes "glare" or "overexposed"
4. Upload an image below 640×480 → quality_issues includes "low_resolution"
5. All quality checks complete in <500ms per image

**Regression Check:** Phase 1 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/image_processing.py backend/tests/test_image_processing.py
git commit -m "feat(cv): image quality gate with blur/exposure/resolution checks

- Laplacian variance blur detection per prd.md §10.1
- Histogram-based exposure analysis
- Minimum 640x480 resolution per FR-001
- Returns quality_score (0-1) and quality_issues array
- All checks complete in <500ms

See: prd.md §10.1 (quality gate), FR-003 (quality assessment)
"
git push origin feature/phase-2-quality-gate
```

---

#### Task 2.1.2: Implement MinIO client and image storage service

**Description:**
Create the MinIO/S3-compatible object storage client for storing raw images, evidence crops, and generated reports per tech-stack.md §8.

**Input Required:**
- tech-stack.md §8 (MinIO, S3-compatible, boto3 client)
- tech-stack.md §18 (S3_ENDPOINT_URL, S3_BUCKET_IMAGES, etc.)
- prd.md §25.5 (image re-encoding on ingest)

**Processing:**
- [ ] Create `backend/app/services/storage.py` with:
  - `upload_image(file_bytes, content_hash) -> storage_url` function
  - `upload_evidence_crop(crop_bytes, inspection_id, violation_id) -> storage_url` function
  - `upload_report(pdf_bytes, inspection_id) -> storage_url` function
  - `get_presigned_url(storage_url, expiry_seconds) -> presigned_url` function
- [ ] Implement content-hash deduplication per FR-001 (duplicate uploads detected and linked)
- [ ] Implement server-side image re-encoding to strip EXIF/embedded payloads per prd.md §25.5
- [ ] Create bucket initialization on app startup

**Output:**
- `backend/app/services/storage.py` (~100 lines)
- Unit test: `backend/tests/test_storage.py`

**Verification Tasks:**
1. Upload an image → returns a storage URL, file exists in MinIO
2. Upload the same image twice (same hash) → deduplicated, same storage_url returned
3. Get presigned URL → URL returns the image bytes, expires after configured time
4. Re-encoded image has EXIF data stripped
5. Three buckets created: lm-images, lm-evidence, lm-reports

**Regression Check:** Phase 2.1 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/storage.py backend/tests/test_storage.py
git commit -m "feat(storage): MinIO object storage client with dedup and re-encoding

- Upload images, evidence crops, and reports to MinIO
- Content-hash deduplication per FR-001
- Server-side image re-encoding strips EXIF per prd.md §25.5
- Presigned URLs for time-limited access per prd.md §25.1
- Three buckets: lm-images, lm-evidence, lm-reports

See: tech-stack.md §8 (MinIO), prd.md §25.5 (file upload security)
"
git push origin feature/phase-2-storage
```

---

### Phase 2 Milestone: Whole Phase Verification Gate

```bash
# Phase 2 Comprehensive Test
pytest backend/tests/test_image_processing.py backend/tests/test_storage.py -v
# Upload test images through the API
# Verify quality scores are returned
# Verify images are stored in MinIO with correct bucket
# Verify presigned URLs work and expire
```

---

## Phase 3: CV & OCR Pipeline

**Scope:** Package/label detection (YOLO), OCR (PaddleOCR), text normalization
**Primary Reference:** prd.md §10 (CV pipeline), §11 (OCR design), FR-004/005/006/007
**Design System Reference:** design.md §8.4 (Processing Screen wireframe)
**Tech Stack Reference:** tech-stack.md §6 (CV/OCR stack), tech-stack.md §13 (YOLO/PaddleOCR versions)

---

### Subphase 3.1: YOLO Detection Service

#### Task 3.1.1: Implement package and label detection using YOLOv8

**Description:**
Integrate YOLOv8n for package and label region detection per prd.md §10.2. For MVP, use pretrained COCO weights; fine-tuning is a later task.

**Input Required:**
- prd.md §10.2 (YOLOv8n, class: package/label, CPU inference ~150–300ms)
- prd.md FR-004 (package detection, ≥0.5 IoU)
- prd.md FR-005 (label region detection)
- tech-stack.md §6 (ultralytics, onnxruntime)

**Processing:**
- [ ] Create `backend/app/services/cv_detection.py` with:
  - `detect_package(image_bytes) -> list[BBox]` function
  - `detect_label(image_bytes, package_bbox) -> list[BBox]` function
  - Load YOLOv8n model (ONNX-exported for inference)
  - Apply confidence threshold ≥0.5 per prd.md §10.4
  - Fallback: if no package detected, run OCR on full image and flag `manual_crop_used`
- [ ] Implement bbox post-processing (non-max suppression, confidence filtering)
- [ ] Create model download/loading utility

**Output:**
- `backend/app/services/cv_detection.py` (~120 lines)
- Unit test: `backend/tests/test_cv_detection.py`

**Verification Tasks:**
1. Feed a package image → returns bbox with confidence ≥0.5
2. Feed an image with no package → returns empty list, flags manual_crop_used
3. Detection completes in <300ms on CPU (per prd.md §10.2)
4. Bbox coordinates are valid (x1 < x2, y1 < y2, within image bounds)

**Regression Check:** Phase 2 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/cv_detection.py backend/tests/test_cv_detection.py
git commit -m "feat(cv): YOLOv8n package and label detection

- Pretrained COCO weights for MVP
- Confidence threshold ≥0.5 per prd.md §10.4
- Fallback: full-image OCR when no package detected
- CPU inference ~150-300ms per prd.md §10.2

See: prd.md §10.2 (models, training, inference), FR-004/005
"
git push origin feature/phase-3-yolo-detection
```

---

### Subphase 3.2: PaddleOCR Integration

#### Task 3.2.1: Implement OCR service with PaddleOCR

**Description:**
Wrap PaddleOCR for multilingual text extraction (English + Hindi) with bounding boxes and per-line confidence per prd.md §11.

**Input Required:**
- prd.md §11.1 (PaddleOCR primary, DB-based text detection)
- prd.md §11.2 (multilingual: English + Hindi)
- prd.md §11.4 (OCR confidence system)
- tech-stack.md §6 (paddleocr 2.8.x, paddlepaddle 2.6.x)

**Processing:**
- [ ] Create `backend/app/services/ocr_service.py` with:
  - `extract_text(image_crop) -> list[OCRResult]` function
  - Initialize PaddleOCR with `en` and `hi` language models
  - Enable angle classifier (`use_angle_cls=True`) per prd.md §11.3
  - Return list of `{text, bbox, confidence, language}` per FR-006
  - Handle rotated/curved text via PaddleOCR's DB detector
- [ ] Implement text upscaling for small fonts per prd.md §11.3 (bicubic 2–4× upscale when text-line height is below threshold)
- [ ] Implement confidence filtering: <0.5 → treated as NOT_FOUND per prd.md §10.4

**Output:**
- `backend/app/services/ocr_service.py` (~100 lines)
- Unit test: `backend/tests/test_ocr_service.py`

**Verification Tasks:**
1. Feed a clear label image → returns text with bbox and confidence ≥0.75
2. Feed a Hindi label → returns Hindi text with language="hi"
3. OCR completes in <3s per image (prd.md §10.2)
4. Rotated text (15°) is correctly read after angle classification
5. Low-confidence results (<0.5) are flagged, not passed downstream

**Regression Check:** Phase 3.1 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/ocr_service.py backend/tests/test_ocr_service.py
git commit -m "feat(ocr): PaddleOCR service with multilingual support

- English + Hindi recognition models per prd.md §11.2
- DB-based text detection for rotated/curved text
- Angle classifier for auto-rotation per prd.md §11.3
- Confidence filtering: <0.5 treated as NOT_FOUND per prd.md §10.4
- Small-font upscaling preprocessing per prd.md §11.3

See: prd.md §11 (OCR design), tech-stack.md §6 (PaddleOCR versions)
"
git push origin feature/phase-3-paddleocr
```

---

### Subphase 3.3: Text Normalization & Declaration Extraction

#### Task 3.3.1: Implement text normalization and declaration extraction

**Description:**
Build the text normalization layer (fix common OCR substitutions, normalize units/currency/dates) and the declaration extraction pipeline (classify text spans into field types) per prd.md §14.

**Input Required:**
- prd.md §14.1 (declaration data model: manufacturer, net_quantity, mrp, mfg_date, etc.)
- prd.md §14.2 (extraction, normalization, validation methods)
- prd.md FR-007 (text normalization)
- prd.md FR-008 (declaration extraction)

**Processing:**
- [ ] Create `backend/app/services/extraction.py` with:
  - `normalize_text(ocr_results) -> list[NormalizedToken]` function
  - Common OCR substitution dictionary (O/0, l/1, etc.)
  - Unit normalization: g/gm/gram → `g`, ml/mL → `ml`, etc. (closed vocabulary per §14.1)
  - Currency symbol normalization to `₹`/`INR`
  - Date format parsing to ISO `YYYY-MM`
  - `extract_declarations(normalized_tokens) -> list[Declaration]` function
  - Regex + positional classifiers per field type (MRP near ₹ token, date near MFG/PKD keywords)
  - Each field type in §14.1's data model must have at least one extraction rule
  - Fields not found are explicitly recorded as `NOT_FOUND`, never omitted
- [ ] Handle multilingual: both English and Hindi candidates stored per §14.2
- [ ] Handle ambiguity: multiple candidates for same field → both recorded with confidence scores

**Output:**
- `backend/app/services/extraction.py` (~200 lines)
- Unit test: `backend/tests/test_extraction.py`

**Verification Tasks:**
1. "500gm" → normalized to value=500, unit="g"
2. "Rs. 999" → normalized to currency="INR", value=999
3. "08/2026" near "MFG" → extracted as mfg_date={month: 8, year: 2026}
4. Missing field → declared as NOT_FOUND, not omitted
5. Two MRP candidates → both returned with confidence scores
6. Every field type in §14.1 has at least one extraction rule

**Regression Check:** Phase 3.2 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/extraction.py backend/tests/test_extraction.py
git commit -m "feat(extraction): text normalization and declaration extraction

- OCR substitution dictionary (O/0, l/1, etc.)
- Unit normalization to closed vocabulary per prd.md §14.1
- Regex + positional classifiers per field type
- Missing fields recorded as NOT_FOUND, never omitted
- Multilingual support: English and Hindi candidates stored
- Ambiguity handling: multiple candidates with confidence scores

See: prd.md §14 (declaration extraction), FR-007/008
"
git push origin feature/phase-3-extraction
```

---

### Phase 3 Milestone: Whole Phase Verification Gate

```bash
# Phase 3 Comprehensive Test
pytest backend/tests/test_cv_detection.py backend/tests/test_ocr_service.py backend/tests/test_extraction.py -v
# End-to-end: feed a sample image through detection → OCR → extraction
# Verify: package detected, text extracted, declarations populated
# Verify: latency <8s p50 per prd.md §9
```

---

## Phase 4: Declaration Extraction & Product Classification

**Scope:** Product category classification, rule selection, font/layout analysis
**Primary Reference:** prd.md §13 (product classification), §15 (font size), §16 (layout), FR-009/010/019/020
**Design System Reference:** design.md §8.5 (Extracted Information page wireframe)
**Tech Stack Reference:** tech-stack.md §7 (scikit-learn classifier)

---

### Subphase 4.1: Product Classification

#### Task 4.1.1: Implement product category classifier

**Description:**
Build the product category classifier using TF-IDF + GradientBoosting per prd.md §10.2 and §13.3. MVP baseline: text-based classification from product name.

**Input Required:**
- prd.md §13.1 (category taxonomy)
- prd.md §10.2 (TF-IDF + GradientBoosting baseline)
- tech-stack.md §7 (scikit-learn, joblib)

**Processing:**
- [ ] Create `backend/app/services/classification.py` with:
  - `classify_product(product_name, extracted_text) -> ClassificationResult` function
  - TF-IDF vectorizer + GradientBoosting classifier
  - Training data: seeded product names from prd.md §13.1 categories
  - Confidence threshold ≥0.6 per prd.md §10.4
  - Below threshold → route to manual category selection (15-entry dropdown per §13.1)
- [ ] Save trained model as `.joblib` artifact per tech-stack.md §7
- [ ] Load model once at worker startup

**Output:**
- `backend/app/services/classification.py` (~80 lines)
- `ml/models/product_classifier.joblib` (trained model artifact)
- Unit test: `backend/tests/test_classification.py`

**Verification Tasks:**
1. Classify "Britannia Good Day Biscuits" → category="Food & Beverage > Packaged Food"
2. Classify "Colgate Toothpaste" → category="Personal Care & Cosmetics > Toiletries"
3. Classify ambiguous text → confidence <0.6, routes to manual selection
4. Classification completes in <50ms per prd.md §10.2

**Regression Check:** Phase 3 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/classification.py ml/models/product_classifier.joblib backend/tests/test_classification.py
git commit -m "feat(ml): product category classifier (TF-IDF + GradientBoosting)

- Baseline text classifier per prd.md §10.2
- Categories per prd.md §13.1 taxonomy
- Confidence threshold ≥0.6, below routes to manual selection
- Model saved as .joblib, loaded once at worker startup
- Inference <50ms per prd.md §10.2

See: prd.md §13 (product classification), tech-stack.md §7 (scikit-learn)
"
git push origin feature/phase-4-classification
```

---

### Subphase 4.2: Font Size & Layout Analysis

#### Task 4.2.1: Implement font size estimation (relative proxy method)

**Description:**
Build the font-size estimation module using the relative-proxy method per prd.md §15. This is the P0 approach — text-line height as a fraction of package/label height.

**Input Required:**
- prd.md §15.1–15.7 (step-by-step font size method)
- prd.md §15.7 (explicit limitations: unreliable without physical reference)
- prd.md FR-019 (measurement_confidence field, UNABLE_TO_VERIFY state)

**Processing:**
- [ ] Create `backend/app/services/font_analysis.py` with:
  - `estimate_font_size(ocr_bbox, package_bbox) -> FontSizeResult` function
  - Relative proxy: text_line_height / package_height as a fraction
  - Confidence scoring: high if clear text region, low if degraded
  - Below confidence floor → mark `UNABLE_TO_VERIFY`, never fabricate pass/fail
- [ ] Output always includes `measurement_confidence` field
- [ ] Low-confidence renders as "Unable to verify precisely" in UI/report per §15.7

**Output:**
- `backend/app/services/font_analysis.py` (~80 lines)
- Unit test: `backend/tests/test_font_analysis.py`

**Verification Tasks:**
1. Clear text region → returns relative size with confidence >0.7
2. Degraded text region → returns UNABLE_TO_VERIFY
3. Font analysis completes in <10ms per prd.md §10.2
4. No fabricated mm values — only relative fractions when no reference available

**Regression Check:** Phase 4.1 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/font_analysis.py backend/tests/test_font_analysis.py
git commit -m "feat(cv): font size estimation using relative-proxy method

- Text-line height / package height ratio per prd.md §15.2
- Confidence scoring with UNABLE_TO_VERIFY state per prd.md §15.7
- No fabricated mm values — honest uncertainty reporting
- <10ms inference per prd.md §10.2

See: prd.md §15 (font size detection), FR-019
"
git push origin feature/phase-4-font-analysis
```

---

### Phase 4 Milestone: Whole Phase Verification Gate

```bash
# Phase 4 Comprehensive Test
pytest backend/tests/test_classification.py backend/tests/test_font_analysis.py -v
# Classify sample products → verify correct categories
# Estimate font sizes → verify confidence scores are honest
# Verify no fabricated measurements
```

---

## Phase 5: Rule Engine & Compliance Checking

**Scope:** Data-driven rule engine, rule versioning, compliance evaluation
**Primary Reference:** prd.md §12 (Rule Engine), FR-010/011/012/013, §20 schema
**Design System Reference:** design.md §11 Voice (rule terms), design.md §8.10 (Rule Management page)
**Tech Stack Reference:** tech-stack.md §5 (Postgres JSONB), tech-stack.md §13 (Postgres pin)

---

### Subphase 5.1: Rule Engine Core

#### Task 5.1.1: Implement the rule engine evaluator

**Description:**
Build the generic rule evaluator that reads rule records from Postgres and executes their `applies_when`/`validation` logic against extracted declarations per prd.md §12.

**Input Required:**
- prd.md §12.1 (rules are data, not code)
- prd.md §12.2 (rule schema: applies_when, validation, severity)
- prd.md §12.3 (rule execution model)
- prd.md §12.4 (versioning and effective dates)

**Processing:**
- [ ] Create `backend/app/services/rule_engine.py` with:
  - `get_applicable_rules(category, inspection_date) -> list[RuleInstance]` function
  - Query `rules`/`rule_versions` where `effective_date <= inspection_date` and category matches
  - `evaluate_rule(rule_instance, declarations) -> RuleVerdict` function
  - Check `applies_when` conditions (product_categories, exclude_categories, package_type)
  - Run `validation` block (regex_and_presence, presence_only, etc.) against matching field
  - Return verdict: PASS, FAIL, NOT_APPLICABLE; if field NOT_FOUND → FAIL (type MISSING)
  - Every execution references exact `rule_versions.id` (not just `rule_id`)
- [ ] Implement validation types: regex_and_presence, presence_only, format_check
- [ ] Rule selection must be 100% deterministic and reproducible per FR-010

**Output:**
- `backend/app/services/rule_engine.py` (~200 lines)
- Unit test: `backend/tests/test_rule_engine.py`

**Verification Tasks:**
1. Given category="Food & Beverage" and date="2026-09-01" → returns correct rule set
2. MRP present with correct format → PASS
3. MRP present but missing "inclusive of all taxes" → FAIL
4. MRP not found → FAIL (type MISSING)
5. Rule not applicable to category → NOT_APPLICABLE
6. Rule selection is deterministic: same inputs always produce same outputs
7. Historical inspection references correct rule version after rule amendment

**Regression Check:** Phase 4 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/rule_engine.py backend/tests/test_rule_engine.py
git commit -m "feat(rule-engine): generic rule evaluator with versioning

- Rules are data, not code per prd.md §12.1
- Reads rule_versions.content (JSONB) from Postgres
- applies_when condition checking (category, package_type, exclusions)
- validation execution (regex_and_presence, presence_only, format_check)
- Every execution references exact rule_versions.id per prd.md §12.4
- 100% deterministic per FR-010

See: prd.md §12 (rule engine), prd.md §12.4 (versioning)
"
git push origin feature/phase-5-rule-engine
```

---

#### Task 5.1.2: Implement rule CRUD API endpoints

**Description:**
Create the admin-facing API for rule management: create rules, add versions, publish versions per prd.md §21 and Workflow G.

**Input Required:**
- prd.md §21 (GET /rules, POST /rules, POST /rules/{id}/versions, POST /rules/{id}/versions/{vid}/publish)
- prd.md §12.6 (rule content source: legal_reference required before publish)
- prd.md §12.4 (append-only versioning, no mutation of referenced versions)

**Processing:**
- [ ] Create `backend/app/api/rules.py` with FastAPI routes
- [ ] Create `backend/app/schemas/rule.py` with Pydantic models
- [ ] Implement rule CRUD (create, list, get detail)
- [ ] Implement version creation with schema validation per §12.2
- [ ] Implement publish with:
  - `legal_reference` must be non-empty before publish
  - Overlapping `effective_date` check → block publish
  - Audit log entry for every publish action
- [ ] RBAC: admin-only for all rule endpoints per prd.md §21

**Output:**
- `backend/app/api/rules.py` (~150 lines)
- `backend/app/schemas/rule.py` (~80 lines)
- Unit test: `backend/tests/test_rules_api.py`

**Verification Tasks:**
1. POST /rules with admin token → creates rule draft
2. POST /rules/{id}/versions with valid content → creates version
3. POST /rules/{id}/versions with missing legal_reference → returns 400
4. POST /rules/{id}/versions/{vid}/publish → publishes, creates audit log
5. POST /publish with overlapping effective_date → returns 409
6. Inspector token on POST /rules → returns 403

**Regression Check:** Phase 5.1.1 tests still pass

**Git Instructions:**
```bash
git add backend/app/api/rules.py backend/app/schemas/rule.py backend/tests/test_rules_api.py
git commit -m "feat(rule-engine): rule CRUD API with versioning and publish workflow

- POST /rules creates draft rule per prd.md §21
- POST /rules/{id}/versions creates new version with schema validation
- Publish requires non-empty legal_reference per prd.md §12.6
- Overlapping effective_date blocked per prd.md §12.4
- Audit logged on every state change
- Admin-only access per prd.md §21

See: prd.md §21 (API), prd.md §12 (rule engine)
"
git push origin feature/phase-5-rule-api
```

---

### Subphase 5.2: Compliance Engine

#### Task 5.2.1: Implement compliance decision engine

**Description:**
Build the compliance engine that aggregates per-rule verdicts into per-field and overall decisions per prd.md §17.

**Input Required:**
- prd.md §17.1 (possible outputs: COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, NEEDS_HUMAN_REVIEW, INSUFFICIENT_EVIDENCE)
- prd.md §17.2 (decision matrix)
- prd.md §10.4 (confidence thresholds)

**Processing:**
- [ ] Create `backend/app/services/compliance_engine.py` with:
  - `evaluate_compliance(declarations, rule_results) -> ComplianceResult` function
  - Decision matrix:
    - All rules PASS, all confidences ≥ threshold → COMPLIANT
    - ≥1 FAIL with high confidence, no unresolved NEEDS_REVIEW → NON_COMPLIANT
    - Some PASS, some FAIL → PARTIALLY_COMPLIANT
    - Any below confidence threshold and not human-reviewed → NEEDS_HUMAN_REVIEW
    - Insufficient fields extracted → INSUFFICIENT_EVIDENCE
  - `NEEDS_HUMAN_REVIEW` takes priority over computed PASS/FAIL per §17.2
- [ ] Store compliance_checks rows with rule_version_id per §12.4

**Output:**
- `backend/app/services/compliance_engine.py` (~120 lines)
- Unit test: `backend/tests/test_compliance_engine.py`

**Verification Tasks:**
1. All rules PASS → status=COMPLIANT
2. MRP FAIL, all high confidence → status=NON_COMPLIANT
3. Some PASS, some FAIL → status=PARTIALLY_COMPLIANT
4. Low-confidence field → status=NEEDS_HUMAN_REVIEW (takes priority)
5. Poor image quality, few fields → status=INSUFFICIENT_EVIDENCE
6. compliance_checks rows reference rule_version_id (not rule_id)

**Regression Check:** Phase 5.1 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/compliance_engine.py backend/tests/test_compliance_engine.py
git commit -m "feat(compliance): decision engine with 5-state output per prd.md §17

- COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, NEEDS_HUMAN_REVIEW,
  INSUFFICIENT_EVIDENCE per prd.md §17.1
- Decision matrix per prd.md §17.2
- NEEDS_HUMAN_REVIEW takes priority over computed verdicts
- Stores compliance_checks with rule_version_id per prd.md §12.4

See: prd.md §17 (compliance decision engine), prd.md §10.4 (thresholds)
"
git push origin feature/phase-5-compliance-engine
```

---

### Phase 5 Milestone: Whole Phase Verification Gate

```bash
# Phase 5 Comprehensive Test
pytest backend/tests/test_rule_engine.py backend/tests/test_rules_api.py backend/tests/test_compliance_engine.py -v
# Rule CRUD: create, version, publish
# Rule evaluation: given known declarations, assert expected verdicts
# Compliance engine: given rule results, assert correct overall status
# Versioning: amend a rule, verify old inspections unaffected
```

---

## Phase 6: Evidence Generation & Human Review

**Scope:** Evidence objects, human-in-the-loop review, corrections workflow
**Primary Reference:** prd.md §18 (Evidence), §19 (Human-in-Loop), FR-021/023
**Design System Reference:** design.md §7.3 (Evidence card), design.md §8.7 (Violation Evidence page)
**Tech Stack Reference:** tech-stack.md §8 (MinIO for evidence crops)

---

### Subphase 6.1: Evidence Engine

#### Task 6.1.1: Implement evidence generation and storage

**Description:**
Build the evidence engine that packages each violation with its supporting image crop, bbox, extracted/expected values, and legal reference per prd.md §18.

**Input Required:**
- prd.md §18.1 (evidence object schema)
- prd.md §18.2 (storage design: metadata in Postgres, crops in MinIO)
- prd.md FR-021 (every violations row has ≥1 linked evidence row)

**Processing:**
- [ ] Create `backend/app/services/evidence_engine.py` with:
  - `generate_evidence(violation, image, bbox) -> Evidence` function
  - Crop image at bbox coordinates using Pillow
  - Upload crop to MinIO (lm-evidence bucket)
  - Create evidence row in Postgres with: violation_id, image_id, bbox, crop_storage_url, confidence
  - Evidence is immutable once created per §18.2
- [ ] Integration: called by compliance engine after each FAIL verdict
- [ ] Block report generation if any violation lacks evidence per Workflow E

**Output:**
- `backend/app/services/evidence_engine.py` (~100 lines)
- Unit test: `backend/tests/test_evidence_engine.py`

**Verification Tasks:**
1. Given a violation + image + bbox → creates evidence row with crop URL
2. Crop is uploaded to MinIO lm-evidence bucket
3. Evidence row references correct violation_id and image_id
4. Evidence is immutable: cannot update or delete after creation
5. Every violations row has ≥1 evidence row (enforced at DB or app level)

**Regression Check:** Phase 5 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/evidence_engine.py backend/tests/test_evidence_engine.py
git commit -m "feat(evidence): evidence generation with bbox-grounded crops

- Crops image at violation bbox using Pillow
- Uploads crop to MinIO lm-evidence bucket
- Creates immutable evidence rows in Postgres
- Every violation gets ≥1 evidence row per FR-021
- Evidence objects per prd.md §18.1 schema

See: prd.md §18 (evidence system), prd.md §18.2 (storage design)
"
git push origin feature/phase-6-evidence
```

---

### Subphase 6.2: Human Review & Corrections

#### Task 6.2.1: Implement human review queue and correction workflow

**Description:**
Build the human review system: route low-confidence fields to mandatory review, allow inspectors to confirm or correct AI findings per prd.md §19 and Workflow D.

**Input Required:**
- prd.md §19.1 (review flow: confidence → threshold → review queue)
- prd.md Workflow D (correction with mandatory reason)
- prd.md §21 (POST /inspections/{id}/review)

**Processing:**
- [ ] Create `backend/app/services/review_queue.py` with:
  - `get_review_items(inspection_id) -> list[ReviewItem]` function
  - Filter declarations/checks where confidence < threshold
  - `submit_correction(correction_data) -> Correction` function
  - Store correction as new row in `corrections` table (never overwrite original)
  - Re-evaluate compliance using corrected value
  - Mark confidence as `human_confirmed`
  - Audit log entry for every correction (who, when, before/after, reason)
- [ ] Implement POST /inspections/{id}/review endpoint
- [ ] Enforce: reason field is required (non-empty) per Workflow D
- [ ] Block report submission while any field remains NEEDS_REVIEW and unconfirmed

**Output:**
- `backend/app/services/review_queue.py` (~100 lines)
- `backend/app/api/reviews.py` (~80 lines)
- Unit test: `backend/tests/test_review.py`

**Verification Tasks:**
1. GET review items for an inspection → returns only low-confidence items
2. Submit correction with reason → creates correction row, updates verdict
3. Submit correction without reason → returns 400
4. Re-evaluated compliance reflects the corrected value
5. Audit log has entry with before/after values and reason
6. Attempt to submit report with unresolved NEEDS_REVIEW → returns 409

**Regression Check:** Phase 6.1 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/review_queue.py backend/app/api/reviews.py backend/tests/test_review.py
git commit -m "feat(review): human-in-the-loop review queue and correction workflow

- Routes low-confidence fields to mandatory review per prd.md §19.1
- Corrections stored as new rows, never overwrite originals per Workflow D
- Mandatory reason field on every correction
- Re-evaluates compliance after correction
- Audit logged with before/after values and reason
- Blocks report submission with unresolved NEEDS_REVIEW per prd.md §17.2

See: prd.md §19 (human-in-the-loop), Workflow D (corrections)
"
git push origin feature/phase-6-review
```

---

### Phase 6 Milestone: Whole Phase Verification Gate

```bash
# Phase 6 Comprehensive Test
pytest backend/tests/test_evidence_engine.py backend/tests/test_review.py -v
# Violation → evidence crop generated → stored in MinIO
# Low-confidence field → appears in review queue
# Correction submitted with reason → verdict updated
# Audit log tracks all changes
```

---

## Phase 7: Reports & Dashboard

**Scope:** PDF report generation, dashboard KPIs, analytics
**Primary Reference:** prd.md §24 (Report Format), §23 (Dashboard), FR-024/027
**Design System Reference:** design.md §9 (Report print/PDF design), design.md §8.2 (Dashboard wireframe)
**Tech Stack Reference:** tech-stack.md §5 (WeasyPrint + Jinja2)

---

### Subphase 7.1: Report Generation

#### Task 7.1.1: Implement PDF report generator

**Description:**
Build the report generator that renders finalized inspections to PDF using WeasyPrint + Jinja2 per prd.md §24.

**Input Required:**
- prd.md §24.1 (report structure: 12 sections)
- prd.md §24.2 (formats: PDF primary, JSON editable export)
- prd.md §9 (target: PDF generation ≤10s)
- design.md §9 (print/PDF visual design)

**Processing:**
- [ ] Create `backend/app/services/report_generator.py` with:
  - `generate_report(inspection_id) -> ReportResult` function
  - HTML/CSS template matching prd.md §24.1 structure (12 sections)
  - WeasyPrint rendering to PDF
  - Jinja2 template population from inspection data
  - Design tokens from design.md §12 applied to PDF template
  - Upload PDF to MinIO (lm-reports bucket)
  - Create report row in `reports` table
  - JSON export as editable format per §24.2
- [ ] Report sections: Cover, Inspection Info, Product Info, Images, Declarations, Compliance Summary, Violations, Evidence Appendix, Legal References, Confidence Notes, Inspector Review, Audit Info
- [ ] Verification seal on COMPLIANT reports only per design.md §9

**Output:**
- `backend/app/services/report_generator.py` (~200 lines)
- `backend/templates/report.html` (Jinja2 template)
- Unit test: `backend/tests/test_report_generator.py`

**Verification Tasks:**
1. Generate report for a sample inspection → PDF created and uploaded to MinIO
2. PDF contains all 12 sections per prd.md §24.1
3. PDF generation completes in <10s per prd.md §9
4. COMPLIANT report includes verification seal per design.md §9
5. NON_COMPLIANT report does NOT include verification seal
6. Evidence crops are included at full size in evidence appendix
7. JSON export is machine-readable

**Regression Check:** Phase 6 tests still pass

**Git Instructions:**
```bash
git add backend/app/services/report_generator.py backend/templates/ backend/tests/test_report_generator.py
git commit -m "feat(reports): PDF report generator with WeasyPrint + Jinja2

- 12-section report structure per prd.md §24.1
- HTML/CSS template with design tokens from design.md §12
- Verification seal on COMPLIANT reports only per design.md §9
- Evidence appendix with full-size crops
- JSON export as editable format per §24.2
- PDF generation <10s per prd.md §9

See: prd.md §24 (report format), design.md §9 (print design)
"
git push origin feature/phase-7-reports
```

---

### Subphase 7.2: Dashboard & Analytics

#### Task 7.2.1: Implement dashboard KPI endpoints

**Description:**
Build the dashboard API endpoints that serve aggregated KPIs per prd.md §23.

**Input Required:**
- prd.md §23.1 (KPIs: inspections count, compliance breakdown, violation categories, trends, review queue size)
- prd.md §21 (GET /dashboard/kpis)
- prd.md §9 (dashboard responsive, precomputed/cached aggregates)

**Processing:**
- [ ] Create `backend/app/api/dashboard.py` with:
  - GET /dashboard/kpis endpoint
  - Query params: region, date_range
  - Returns: total inspections, compliant/non-compliant/needs-review counts, violation categories, top violation types, inspections by region, trend data, pending review queue size
- [ ] Implement materialized views or cached aggregate queries per §23.2
- [ ] RBAC: senior_officer+ per prd.md §21

**Output:**
- `backend/app/api/dashboard.py` (~120 lines)
- Unit test: `backend/tests/test_dashboard.py`

**Verification Tasks:**
1. GET /dashboard/kpis with admin token → returns KPI object
2. KPI object contains: total_inspections, status_breakdown, violation_categories, trends, review_queue_size
3. Filter by region → returns region-specific KPIs
4. Filter by date_range → returns period-specific KPIs
5. Dashboard query completes in <300ms per prd.md §9

**Regression Check:** Phase 7.1 tests still pass

**Git Instructions:**
```bash
git add backend/app/api/dashboard.py backend/tests/test_dashboard.py
git commit -m "feat(dashboard): KPI endpoints with cached aggregates

- GET /dashboard/kpis per prd.md §21
- Status breakdown, violation categories, trends, review queue size
- Materialized views for precomputed aggregates per §23.2
- Region and date range filters
- Response time <300ms per prd.md §9
- Admin/senior_officer access per prd.md §21

See: prd.md §23 (dashboard design), prd.md §21 (API)
"
git push origin feature/phase-7-dashboard
```

---

### Phase 7 Milestone: Whole Phase Verification Gate

```bash
# Phase 7 Comprehensive Test
pytest backend/tests/test_report_generator.py backend/tests/test_dashboard.py -v
# Generate PDF report → verify all 12 sections present
# Check PDF generation time <10s
# Dashboard KPIs return correct aggregate data
# Dashboard query time <300ms
```

---

## Phase 8: Frontend UI Implementation

**Scope:** All 15 frontend pages, core components, camera capture, API integration
**Primary Reference:** prd.md §22 (Frontend Design, 15 pages)
**Design System Reference:** design.md §0–12 (entire design system)
**Tech Stack Reference:** tech-stack.md §4 (frontend stack)

---

### Subphase 8.1: Core Design System Components

#### Task 8.1.1: Implement design token system and global styles

**Description:**
Implement the full CSS custom properties from design.md §12, configure Tailwind to use Docket tokens, and set up font imports.

**Input Required:**
- design.md §12 (CSS custom properties: colors, type, spacing, structure, motion)
- design.md §1 (color tokens and usage rules)
- design.md §2 (typefaces and type scale)

**Processing:**
- [ ] Create `frontend/src/styles/tokens.css` with all CSS variables from design.md §12
- [ ] Configure `tailwind.config.js` to extend with Docket tokens
- [ ] Set up Google Fonts / font-face declarations for Source Serif 4, IBM Plex Sans, IBM Plex Mono
- [ ] Create `frontend/src/styles/globals.css` with:
  - CSS resets
  - Focus ring styles (2px Ink Navy, instant per design.md §5)
  - `prefers-reduced-motion` media query per design.md §5
- [ ] Verify no hardcoded color hex values anywhere in the codebase

**Output:**
- `frontend/src/styles/tokens.css`
- `frontend/src/styles/globals.css`
- Updated `frontend/tailwind.config.js`

**Verification Tasks:**
1. `grep -r "#1B2A41" frontend/src/ --include="*.tsx" --include="*.ts"` → 0 results (no hardcoded colors)
2. `grep -r "var(--color-" frontend/src/styles/` → all tokens present
3. Font declarations load correctly in browser
4. `prefers-reduced-motion: reduce` disables animations 1 and 2

**Regression Check:** N/A

**Git Instructions:**
```bash
git add frontend/src/styles/ frontend/tailwind.config.js
git commit -m "feat(frontend): design token system with Tailwind integration

- CSS custom properties per design.md §12 (colors, type, spacing)
- Tailwind theme extended with Docket tokens
- Font imports: Source Serif 4, IBM Plex Sans, IBM Plex Mono
- Focus ring and reduced-motion support per design.md §5
- Zero hardcoded color hex values in component code

See: design.md §12 (CSS tokens), design.md §1-2 (colors, typography)
"
git push origin feature/phase-8-design-tokens
```

---

#### Task 8.1.2: Implement LedgerRow, MeasureRule, StatusBadge, EvidenceCard components

**Description:**
Build the four core Docket components: LedgerRow (design.md §3.2), MeasureRule (design.md §6), StatusBadge (design.md §7.1), EvidenceCard (design.md §7.3).

**Input Required:**
- design.md §3.2 (ledger row: full-width, 1px hairline, 4px left-edge status tick)
- design.md §6 (Measure Rule: vertical tick-marked rule, 6px baseline)
- design.md §7.1 (Status badge: sentence case, fill, icon)
- design.md §7.3 (Evidence card: 1px border, 0px radius, image crop with bbox overlay)
- design.md §7.5 (Confidence meter: horizontal tick-scale)

**Processing:**
- [ ] Create `frontend/src/components/LedgerRow.tsx`:
  - Full-width horizontal record with 1px hairline border
  - 4px left-edge status tick (Teal/Redline/Amber per status)
  - Props: status, children, onClick
- [ ] Create `frontend/src/components/MeasureRule.tsx`:
  - Vertical 6px-wide rule with colored ticks
  - Ticks colored by verdict (Teal/Redline/Amber)
  - 24px vertical rhythm
- [ ] Create `frontend/src/components/ComplianceStatusBadge.tsx`:
  - Sentence case text, fill background, left-aligned icon
  - Three variants: Compliant (Teal), Violation (Redline), Needs review (Amber)
- [ ] Create `frontend/src/components/EvidenceCard.tsx`:
  - Image crop with bbox overlay drawn as SVG
  - Redline bbox stroke-draw animation (320ms per design.md §5)
  - Violation ID in IBM Plex Mono
  - Detected vs. Expected values
  - Rule citation in Source Serif 4

**Output:**
- `frontend/src/components/LedgerRow.tsx`
- `frontend/src/components/MeasureRule.tsx`
- `frontend/src/components/ComplianceStatusBadge.tsx`
- `frontend/src/components/EvidenceCard.tsx`
- Component tests for each

**Verification Tasks:**
1. LedgerRow renders with correct status tick color
2. MeasureRule renders ticks with verdict colors
3. StatusBadge renders correct text and fill color for each status
4. EvidenceCard renders image with bbox overlay
5. Evidence bbox draws with 320ms stroke-draw animation
6. All components use design tokens, no hardcoded colors

**Regression Check:** Phase 8.1.1 tests still pass

**Git Instructions:**
```bash
git add frontend/src/components/
git commit -m "feat(frontend): core Docket components (LedgerRow, MeasureRule, Badge, EvidenceCard)

- LedgerRow: full-width record with 4px status tick per design.md §3.2
- MeasureRule: vertical tick-marked rule per design.md §6
- ComplianceStatusBadge: sentence-case fill badges per design.md §7.1
- EvidenceCard: image crop with bbox overlay per design.md §7.3
- Evidence bbox stroke-draw animation (320ms) per design.md §5
- All components use design tokens, no hardcoded values

See: design.md §3.2 (ledger row), §6 (Measure Rule), §7 (component library)
"
git push origin feature/phase-8-core-components
```

---

### Subphase 8.2: Authentication & Navigation Pages

#### Task 8.2.1: Implement Login page and auth state management

**Description:**
Build the Login page per design.md §8.1 and the auth state management (useAuth hook, JWT storage, route protection).

**Input Required:**
- design.md §8.1 (Login page wireframe: display-xl headline, email/password form, Sign in button)
- design.md §6 (Measure Rule runs full left edge on Login)
- prd.md §21 (POST /auth/login contract)

**Processing:**
- [ ] Create `frontend/src/pages/LoginPage.tsx`:
  - "Docket" headline in Source Serif 4 display-xl (56px)
  - "Legal Metrology Compliance" subtitle
  - Email and password fields with Plex Sans labels above inputs (never placeholder-as-label per design.md §7.6)
  - "Sign in" primary button per design.md §7.2
  - Measure Rule runs full left edge, unlabeled per design.md §8.1
  - Error state: inline error message below form
- [ ] Create `frontend/src/hooks/useAuth.ts`:
  - Store JWT in memory (not localStorage per security best practice)
  - Login/logout functions
  - Token refresh logic
- [ ] Create `frontend/src/api/client.ts`:
  - Axios instance with auth interceptor
  - Base URL from VITE_API_BASE_URL
  - Automatic 401 handling (redirect to login)

**Output:**
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/hooks/useAuth.ts`
- `frontend/src/api/client.ts`

**Verification Tasks:**
1. Login page renders with "Docket" headline and form
2. Measure Rule visible on left edge
3. Submit with valid credentials → redirects to Dashboard
4. Submit with invalid credentials → shows inline error
5. JWT stored in memory, not localStorage
6. Axios interceptor adds Authorization header to requests

**Regression Check:** Phase 8.1 tests still pass

**Git Instructions:**
```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/hooks/useAuth.ts frontend/src/api/client.ts
git commit -m "feat(frontend): Login page and auth state management

- Login page per design.md §8.1 with Measure Rule on left edge
- useAuth hook with JWT in memory (not localStorage)
- Axios client with auth interceptor and 401 handling
- Plex Sans labels above inputs per design.md §7.6

See: design.md §8.1 (Login wireframe), prd.md §21 (auth API)
"
git push origin feature/phase-8-login
```

---

### Subphase 8.3: Core Workflow Pages

#### Task 8.3.1: Implement Image Capture page with camera integration

**Description:**
Build the Image Capture page per design.md §8.3 with browser camera integration (getUserMedia) and file upload.

**Input Required:**
- design.md §8.3 (Image Capture wireframe: camera viewfinder, framing guide, capture button, thumbnails)
- prd.md FR-002 (camera capture via getUserMedia, framing guide)
- prd.md §10 (framing guide for label region)

**Processing:**
- [ ] Create `frontend/src/pages/CaptureImagePage.tsx`:
  - Camera viewfinder with framing guide overlay (dashed, Ink Navy per design.md §8.3)
  - "Capture photo" button with camera icon
  - Thumbnail strip showing captured images
  - "Add another angle" button
  - File upload drag-drop alternative
- [ ] Create `frontend/src/hooks/useCamera.ts`:
  - getUserMedia integration
  - Frame capture to canvas
  - Permission handling (camera denied → show upload-only mode)
- [ ] Handle image quality warnings inline (blurry/glare messages per design.md §11)

**Output:**
- `frontend/src/pages/CaptureImagePage.tsx`
- `frontend/src/hooks/useCamera.ts`

**Verification Tasks:**
1. Camera viewfinder renders on HTTPS
2. Framing guide overlay visible (dashed border)
3. Capture button captures frame to thumbnail
4. Upload button opens file picker
5. Quality warnings shown inline after upload
6. Minimum 34×44px touch targets per design.md §10

**Regression Check:** Phase 8.3.1 tests still pass

**Git Instructions:**
```bash
git add frontend/src/pages/CaptureImagePage.tsx frontend/src/hooks/useCamera.ts
git commit -m "feat(frontend): Image Capture page with camera integration

- Camera viewfinder with framing guide per design.md §8.3
- getUserMedia integration with permission handling
- Thumbnail strip for captured images
- Drag-drop file upload alternative
- Inline quality warnings per design.md §11

See: design.md §8.3 (capture wireframe), FR-002 (camera capture)
"
git push origin feature/phase-8-capture
```

---

#### Task 8.3.2: Implement Processing Screen, Extracted Info, and Compliance Results pages

**Description:**
Build the Processing Screen (progress stepper), Extracted Information (per-field review), and Compliance Results (verdict + violations list) pages per design.md §8.4–8.6.

**Input Required:**
- design.md §8.4 (Processing Screen: numbered pipeline stepper, the one legitimate use of sequence numbers)
- design.md §8.5 (Extracted Information: per-field card with confidence meter)
- design.md §8.6 (Compliance Results: Measure Rule with verdict-colored ticks)
- prd.md §22 (pages 5, 6, 7)

**Processing:**
- [ ] Create `frontend/src/pages/ProcessingPage.tsx`:
  - Numbered pipeline stepper (1-5) per design.md §8.4
  - Status indicators: done (checkmark), in progress (spinner), pending (empty circle)
  - Poll job status via TanStack Query refetchInterval
  - "Works offline — will finish when you're back online" message per design.md §10
- [ ] Create `frontend/src/pages/ExtractedInfoPage.tsx`:
  - Per-field ledger rows with value, confidence meter (§7.5), source crop thumbnail
  - Tap-to-correct inline (Workflow D)
  - "6 of 8 confirmed" counter
- [ ] Create `frontend/src/pages/ComplianceResultsPage.tsx`:
  - Overall status banner (color-coded per §17.1 statuses)
  - Measure Rule on left edge with verdict-colored ticks per design.md §6
  - Per-rule verdict list (ledger rows with status ticks)
  - Drill into violation → navigates to Violation Evidence page

**Output:**
- `frontend/src/pages/ProcessingPage.tsx`
- `frontend/src/pages/ExtractedInfoPage.tsx`
- `frontend/src/pages/ComplianceResultsPage.tsx`

**Verification Tasks:**
1. Processing Screen shows pipeline progress with correct states
2. Processing Screen polls job status and updates in real-time
3. Extracted Info shows each field with confidence meter
4. Compliance Results shows Measure Rule with colored ticks
5. Clicking a violation navigates to Violation Evidence page
6. Status banner matches overall verdict color

**Regression Check:** Phase 8.3.1 tests still pass

**Git Instructions:**
```bash
git add frontend/src/pages/ProcessingPage.tsx frontend/src/pages/ExtractedInfoPage.tsx frontend/src/pages/ComplianceResultsPage.tsx
git commit -m "feat(frontend): Processing, Extracted Info, and Compliance Results pages

- Processing Screen: numbered stepper per design.md §8.4 (only legitimate use of sequence numbers)
- Extracted Info: per-field rows with confidence meters per design.md §8.5
- Compliance Results: Measure Rule with verdict-colored ticks per design.md §8.6
- TanStack Query polling for job status updates
- Drill-through from violations to evidence page

See: design.md §8.4-8.6 (page wireframes), prd.md §22 (pages 5-7)
"
git push origin feature/phase-8-workflow-pages
```

---

#### Task 8.3.3: Implement Violation Evidence, Manual Review, and Report pages

**Description:**
Build the Violation Evidence page (evidence card with bbox overlay), Manual Review queue (ledger of NEEDS_REVIEW items), and Report page (PDF preview/download).

**Input Required:**
- design.md §8.7 (Violation Evidence: evidence card, rule citation, confirm/correct buttons)
- design.md §8.8 (Manual Review Queue: ledger filtered to NEEDS_REVIEW, most visually amber screen)
- design.md §8.9 (Report: print/PDF preview)
- prd.md §22 (pages 8, 9, 10)

**Processing:**
- [ ] Create `frontend/src/pages/ViolationEvidencePage.tsx`:
  - Evidence card per design.md §7.3 with bbox overlay
  - Rule citation in Source Serif 4 per design.md §8.7
  - "Confirm violation" and "Correct this finding" buttons per design.md §7.2
- [ ] Create `frontend/src/pages/ManualReviewPage.tsx`:
  - Ledger of NEEDS_REVIEW items, Amber Flag tick on every row per design.md §8.8
  - Bulk confirm and individual correct actions
- [ ] Create `frontend/src/pages/ReportPage.tsx`:
  - PDF preview (embedded viewer)
  - Download PDF and JSON export buttons
  - "Generating..." state while report is being created

**Output:**
- `frontend/src/pages/ViolationEvidencePage.tsx`
- `frontend/src/pages/ManualReviewPage.tsx`
- `frontend/src/pages/ReportPage.tsx`

**Verification Tasks:**
1. Violation Evidence shows evidence card with bbox overlay
2. Bbox draws with 320ms stroke-draw animation per design.md §5
3. Manual Review shows only NEEDS_REVIEW items in amber
4. Bulk confirm works for multiple items
5. Report page shows PDF preview and download buttons
6. Generating state shows while report is being created

**Regression Check:** Phase 8.3.2 tests still pass

**Git Instructions:**
```bash
git add frontend/src/pages/ViolationEvidencePage.tsx frontend/src/pages/ManualReviewPage.tsx frontend/src/pages/ReportPage.tsx
git commit -m "feat(frontend): Violation Evidence, Manual Review, and Report pages

- Violation Evidence: evidence card with bbox overlay per design.md §8.7
- Manual Review: amber-filtered ledger per design.md §8.8
- Report: PDF preview with download per design.md §8.9
- Evidence bbox stroke-draw animation per design.md §5

See: design.md §8.7-8.9 (page wireframes), prd.md §22 (pages 8-10)
"
git push origin feature/phase-8-evidence-review-pages
```

---

### Subphase 8.4: Admin & Analytics Pages

#### Task 8.4.1: Implement Dashboard, History, Rule Management, Admin, and Analytics pages

**Description:**
Build the remaining 6 pages: Dashboard (KPI cards + charts), History (filterable table), Rule Management (CRUD + version history), Admin (user management), Analytics (deep charts), and Product Database (search).

**Input Required:**
- design.md §8.2 (Dashboard wireframe: KPI figure blocks, bar charts, recent inspections ledger)
- prd.md §22 (pages 2, 11, 12, 13, 14, 15)
- prd.md §23 (KPIs: total inspections, compliance breakdown, violation categories, trends)
- design.md §7.4 (data tables: right-aligned numerals, tabular figures, Paper Deep striping)

**Processing:**
- [ ] Create `frontend/src/pages/DashboardPage.tsx`:
  - Four KPI figure blocks (Inspected, Violations, Review queue, Reported) per design.md §8.2
  - Bar charts (violation categories, inspections by region) using Recharts
  - Recent inspections ledger with status ticks
  - Region and date range filters
- [ ] Create `frontend/src/pages/HistoryPage.tsx`:
  - Filterable/searchable inspection table per prd.md §22
  - Status, date, region, violation type filters
  - Pagination
- [ ] Create `frontend/src/pages/RuleManagementPage.tsx`:
  - Rule list with version history per design.md §8.10
  - Create/edit/publish form
  - Legal reference required before publish
  - Version history with published_by and dates
- [ ] Create `frontend/src/pages/AdminPage.tsx`:
  - User management (CRUD)
  - Role assignment
- [ ] Create `frontend/src/pages/AnalyticsPage.tsx`:
  - Deep charts: trend lines, violation category breakdown
  - CSV export
- [ ] Create `frontend/src/pages/ProductDatabasePage.tsx`:
  - Searchable product list
  - Per-product inspection history link

**Output:**
- 6 page components in `frontend/src/pages/`
- All pages use design tokens and core components

**Verification Tasks:**
1. Dashboard shows 4 KPI figure blocks with correct data
2. Dashboard charts render with Recharts
3. History page filters and paginates correctly
4. Rule Management page shows version history per design.md §8.10
5. Admin page allows user CRUD
6. Analytics page shows trend charts
7. All pages use LedgerRow, no card grids (except KPI figure blocks per design.md §3.2)

**Regression Check:** Phase 8.3.3 tests still pass

**Git Instructions:**
```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/pages/HistoryPage.tsx frontend/src/pages/RuleManagementPage.tsx frontend/src/pages/AdminPage.tsx frontend/src/pages/AnalyticsPage.tsx frontend/src/pages/ProductDatabasePage.tsx
git commit -m "feat(frontend): Dashboard, History, Rule Management, Admin, Analytics pages

- Dashboard: KPI figure blocks + Recharts per design.md §8.2
- History: filterable inspection table per prd.md §22
- Rule Management: CRUD + version history per design.md §8.10
- Admin: user management and role assignment
- Analytics: trend charts with CSV export
- Product Database: searchable product list
- All pages use design tokens and core components

See: design.md §8.2, §8.10 (page wireframes), prd.md §22 (pages 2, 11-15)
"
git push origin feature/phase-8-admin-pages
```

---

### Subphase 8.5: Routing & App Shell

#### Task 8.5.1: Implement React Router, layout, and offline queue

**Description:**
Set up React Router with all page routes, the app shell layout (sidebar/navigation), and the offline capture queue per prd.md §27.

**Input Required:**
- prd.md §22 (all 15 pages with navigation)
- prd.md §27 (offline mode: IndexedDB queue, sync when online)
- design.md §10 (responsive: mobile-first for inspector flows, desktop-first for admin flows)

**Processing:**
- [ ] Update `frontend/src/App.tsx` with React Router:
  - Route definitions for all 15 pages
  - Protected routes (redirect to login if unauthenticated)
  - Role-based route access (admin pages only for admin role)
- [ ] Create `frontend/src/components/Layout.tsx`:
  - Sidebar navigation with page links
  - Mobile-responsive: bottom nav on mobile, sidebar on desktop
  - Measure Rule on left edge (collapses to 3px on mobile per design.md §10)
  - User info and logout in header
- [ ] Create `frontend/src/hooks/useOfflineQueue.ts`:
  - IndexedDB queue for inspections captured offline
  - Sync queue when connectivity returns
  - Amber Flag offline banner per design.md §10
- [ ] Create `frontend/src/lib/offline.ts`:
  - Service worker registration
  - IndexedDB utilities

**Output:**
- Updated `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/hooks/useOfflineQueue.ts`
- `frontend/src/lib/offline.ts`

**Verification Tasks:**
1. All 15 routes accessible via navigation
2. Unauthenticated access redirects to login
3. Admin routes return 403 or redirect for non-admin users
4. Mobile layout shows bottom nav, desktop shows sidebar
5. Measure Rule collapses to 3px on mobile
6. Offline banner appears when network is lost
7. Inspections queued in IndexedDB when offline

**Regression Check:** All Phase 8 tests still pass

**Git Instructions:**
```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/hooks/useOfflineQueue.ts frontend/src/lib/offline.ts
git commit -m "feat(frontend): routing, layout shell, and offline queue

- React Router with protected routes for all 15 pages
- Responsive layout: bottom nav mobile, sidebar desktop per design.md §10
- Measure Rule collapses to 3px on mobile per design.md §10
- IndexedDB offline queue per prd.md §27
- Amber Flag offline banner per design.md §10
- Role-based route access (admin pages restricted)

See: prd.md §22 (pages), prd.md §27 (offline mode), design.md §10 (responsive)
"
git push origin feature/phase-8-routing
```

---

### Phase 8 Milestone: Whole Phase Verification Gate

```bash
# Phase 8 Comprehensive Test
cd frontend && npm run build && npm run test
# All 15 pages render without errors
# Login → capture → process → review → report flow works end-to-end
# Measure Rule visible on key screens (Login, Dashboard, Compliance, Evidence, Report)
# No hardcoded colors: grep -r "#" frontend/src/ --include="*.tsx" | grep -v "tokens.css" | grep -v "//" → 0
# Offline banner appears when network disconnected
# Mobile layout shows bottom nav
```

---

## Phase 9: Integration, Hardening & Release

**Scope:** End-to-end pipeline integration, testing, performance tuning, demo preparation
**Primary Reference:** prd.md §31 (Testing), §38 (Demo), prd.md §9 (NFRs), tech-stack.md §10 (CI/CD)
**Design System Reference:** design.md (final review)
**Tech Stack Reference:** tech-stack.md §10 (CI/CD), §12 (monitoring), §21 (maintenance)

---

### Subphase 9.1: End-to-End Pipeline Integration

#### Task 9.1.1: Implement the full analysis pipeline orchestration

**Description:**
Wire together all CV/OCR/extraction/classification/rule/compliance/evidence services into the RQ job pipeline per prd.md §10.1 and §40 Phase 7.

**Input Required:**
- prd.md §10.1 (full pipeline: Image → Preprocessing → Quality → Detection → OCR → Extraction → Classification → Rules → Compliance → Evidence)
- prd.md §33 (failure handling: retry ×2 with backoff)
- tech-stack.md §5 (RQ job queue)

**Processing:**
- [ ] Create `backend/app/tasks/pipeline.py` with:
  - `run_analysis_pipeline(inspection_id)` RQ job function
  - Orchestrates all pipeline stages in sequence
  - Updates inspection status at each stage (draft → analyzing → review → reviewed)
  - Retry logic: automatic retry ×2 with backoff per prd.md §9
  - After exhausting retries: inspection marked `analysis_failed`, inspector notified
  - Each stage writes results to the appropriate DB table
  - Evidence generated for every violation
- [ ] Implement POST /inspections/{id}/analyze endpoint to enqueue the job
- [ ] Implement GET /inspections/{id}/status for job polling
- [ ] Integrate with frontend Processing Screen polling

**Output:**
- `backend/app/tasks/pipeline.py` (~150 lines)
- Updated `backend/app/api/inspections.py` with analyze and status endpoints
- Integration test: `backend/tests/test_pipeline.py`

**Verification Tasks:**
1. POST /inspections/{id}/analyze → returns job_id, status "queued"
2. GET /inspections/{id}/status → polls through: queued → processing → done
3. After completion: inspection has declarations, compliance_checks, violations, evidence
4. Failed image → retries 2× then marks analysis_failed
5. Full pipeline completes in <8s p50 per prd.md §9

**Regression Check:** All Phase 8 tests still pass

**Git Instructions:**
```bash
git add backend/app/tasks/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(pipeline): full analysis pipeline orchestration via RQ

- Orchestrates: quality → detection → OCR → extraction → classification → rules → compliance → evidence
- Updates inspection status at each stage per prd.md §10.1
- Retry ×2 with backoff per prd.md §9
- POST /inspections/{id}/analyze enqueues job
- GET /inspections/{id}/status for polling
- Full pipeline <8s p50 per prd.md §9

See: prd.md §10.1 (full pipeline), prd.md §33 (failure handling)
"
git push origin feature/phase-9-pipeline
```

---

### Subphase 9.2: Testing & Hardening

#### Task 9.2.1: Write comprehensive test suite per prd.md §31

**Description:**
Write unit, integration, API, and E2E tests per prd.md §31's test matrix.

**Input Required:**
- prd.md §31 (test matrix: unit, integration, API, frontend, OCR, ML, rule-engine, security, performance, E2E)
- prd.md §31.1 (test scenarios: compliant product, missing MRP, blurry image, low confidence, rule versioning, unauthorized access)
- tech-stack.md §11 (testing stack: pytest, Vitest, Playwright, Locust)

**Processing:**
- [ ] Backend tests: `pytest backend/tests/ -v`
  - Unit tests for all services (normalizers, validators, rule matching)
  - Integration tests for pipeline stages (OCR → extraction → rule engine)
  - API tests for every endpoint per prd.md §21
  - Rule engine tests: given fixed declarations + fixed rules, assert exact verdicts
  - Security tests: auth bypass, file upload fuzzing
- [ ] Frontend tests: `cd frontend && npm test`
  - Component rendering tests (LedgerRow, StatusBadge, EvidenceCard)
  - Form validation tests
- [ ] E2E tests: Playwright
  - Full Workflow A: login → capture → process → review → report
  - Offline queue test
- [ ] Performance tests: Locust
  - 20 concurrent users per prd.md §9
  - 5 concurrent analysis jobs

**Output:**
- Test files in `backend/tests/` and `frontend/tests/`
- Test coverage report

**Verification Tasks:**
1. `pytest backend/tests/ -v` → all tests pass
2. `cd frontend && npm test` → all tests pass
3. E2E flow completes without errors
4. Performance: API response ≤300ms p95, pipeline ≤8s p50
5. No test contains TODO/FIXME/placeholder

**Regression Check:** All previous phase tests still pass

**Git Instructions:**
```bash
git add backend/tests/ frontend/tests/
git commit -m "test: comprehensive test suite per prd.md §31

- Unit tests for all services
- Integration tests for pipeline stages
- API tests for every endpoint
- Frontend component tests (Vitest + React Testing Library)
- E2E tests (Playwright) for full Workflow A
- Performance tests (Locust) for 20 concurrent users
- Security tests: auth bypass, file upload fuzzing

See: prd.md §31 (testing strategy), tech-stack.md §11 (testing stack)
"
git push origin feature/phase-9-tests
```

---

#### Task 9.2.2: Performance tuning and NFR validation

**Description:**
Validate and tune all non-functional requirements per prd.md §9.

**Input Required:**
- prd.md §9 (NFRs: OCR <8s, API <300ms, report <10s, 20 concurrent users)
- prd.md §30.2 (false-negative-averse tuning)

**Processing:**
- [ ] Benchmark API response times: all non-analysis endpoints ≤300ms p95
- [ ] Benchmark pipeline latency: ≤8s p50 per image
- [ ] Benchmark report generation: ≤10s for 5-violation report
- [ ] Load test with Locust: 20 concurrent users, 5 concurrent analysis jobs
- [ ] Tune OCR confidence thresholds per prd.md §30.3
- [ ] Verify false-negative rate is near-zero for CRITICAL fields (MRP, net quantity)
- [ ] Document benchmark results

**Output:**
- Performance benchmark results
- Tuned confidence thresholds
- Updated documentation

**Verification Tasks:**
1. API p95 response time ≤300ms
2. Pipeline p50 latency ≤8s
3. Report generation ≤10s
4. 20 concurrent users handled without errors
5. False-negative rate near-zero for CRITICAL fields

**Regression Check:** All tests still pass after tuning

**Git Instructions:**
```bash
git add .phase-reports/performance-benchmarks.md
git commit -m "perf: NFR validation and performance tuning

- API p95 ≤300ms, pipeline p50 ≤8s, report ≤10s per prd.md §9
- 20 concurrent user load test passed
- Confidence thresholds tuned per prd.md §30.3
- False-negative rate near-zero for CRITICAL fields

See: prd.md §9 (NFRs), prd.md §30.2 (false-negative tuning)
"
git push origin feature/phase-9-performance
```

---

### Subphase 9.3: Demo Preparation

#### Task 9.3.1: Build demo dataset and demo compose file

**Description:**
Prepare the demo dataset (10–20 physical packages per prd.md §39) and create docker-compose.demo.yml for offline demo deployment per prd.md §43.2.

**Input Required:**
- prd.md §39 (demo dataset: 10–20 packages, team-created violations, multilingual examples)
- prd.md §39.2 (avoiding false claims of real non-compliance)
- prd.md §43.2 (docker-compose.demo.yml: production images, seeded DB, zero internet)
- prd.md §38.3 (demo works 100% offline)

**Processing:**
- [ ] Create `docker-compose.demo.yml`:
  - Same services as docker-compose.yml but with production-built images
  - Nginx serving built frontend static assets
  - Pre-seeded database (demo users, rule versions, product records)
  - Zero external network dependency
- [ ] Create `backend/scripts/seed_demo_data.py`:
  - Seed demo inspection records with known outcomes
  - Mark synthetic demo assets as `SYNTHETIC_DEMO` per prd.md §39.2
- [ ] Create `SUBMISSION_CHECKLIST.md` with all pre-submission items

**Output:**
- `docker-compose.demo.yml`
- `backend/scripts/seed_demo_data.py`
- `SUBMISSION_CHECKLIST.md`

**Verification Tasks:**
1. `docker compose -f docker-compose.demo.yml up --build` → all services start
2. Demo machine needs zero internet connectivity
3. Demo dataset loaded with correct product records
4. Demo users can log in and complete Workflow A
5. No false claims of real manufacturer non-compliance in demo data

**Regression Check:** All tests still pass

**Git Instructions:**
```bash
git add docker-compose.demo.yml backend/scripts/seed_demo_data.py SUBMISSION_CHECKLIST.md
git commit -m "feat(demo): demo compose file and dataset preparation

- docker-compose.demo.yml: production images, seeded DB, zero internet per prd.md §43.2
- Demo dataset seeded with synthetic demo assets marked SYNTHETIC_DEMO per §39.2
- Submission checklist with all pre-SIH items

See: prd.md §39 (demo dataset), prd.md §43.2 (demo deployment), prd.md §38 (demo strategy)
"
git push origin feature/phase-9-demo-prep
```

---

### Subphase 9.4: Final Code Quality & Security Audit

#### Task 9.4.1: Final code quality pass and security verification

**Description:**
Run the final code quality pass: remove all TODO/FIXME/placeholder, verify no hardcoded colors, verify audit logs are append-only, verify rule versioning works end-to-end.

**Input Required:**
- prd.md §9 (NFRs)
- design.md §12 (no hardcoded colors)
- prd.md §20.1 (audit_logs append-only)
- prd.md §12.4 (rule versioning)

**Processing:**
- [ ] `grep -r "TODO\|FIXME\|XXX\|placeholder" --include="*.py" --include="*.tsx" --include="*.ts"` → must return 0
- [ ] `grep -r "#1B2A41\|#EEF1EC\|#2E5D50\|#8C2F2F\|#A9761D\|#B08A3E" frontend/src/ --include="*.tsx" --include="*.ts"` → must return 0 (all via CSS vars)
- [ ] Verify audit_logs has no UPDATE/DELETE grants
- [ ] Verify rule versioning: create rule v1, inspect, amend to v2, inspect → v1 inspection still references v1
- [ ] Run full info-disclosure check: `grep -r "JWT_SECRET\|POSTGRES_PASSWORD\|MINIO_ROOT" --include="*.py" --include="*.tsx"` → 0 results
- [ ] Verify GitHub README includes: architecture diagram, tech stack table, setup quickstart, design system overview

**Output:**
- Clean codebase with no placeholders
- All verification checks documented
- Updated README.md

**Verification Tasks:**
1. No TODO/FIXME/XXX in production code
2. No hardcoded colors in frontend components
3. Audit logs append-only at DB level
4. Rule versioning works correctly (old inspections reference old rules)
5. No secrets in committed code
6. README has all required sections

**Regression Check:** All tests still pass

**Git Instructions:**
```bash
git add -A
git commit -m "chore: final code quality pass and security audit

- Removed all TODO/FIXME/XXX/placeholder from production code
- Verified no hardcoded colors (all via CSS custom properties)
- Audit logs append-only at DB level confirmed
- Rule versioning end-to-end verified
- Info-disclosure check passed (no secrets in code)
- README updated with architecture diagram and setup quickstart

See: prd.md §9 (NFRs), design.md §12 (tokens), prd.md §20.1 (audit logs)
"
git push origin feature/phase-9-final-audit
```

---

### Phase 9 Milestone: Whole Phase Verification Gate

```bash
# Phase 9 Comprehensive Test
pytest backend/tests/ -v
cd frontend && npm test
cd frontend && npm run build

# Full Workflow A end-to-end
# Login → Capture → Process → Extract → Review → Report
# Dashboard shows KPIs
# Rule versioning works (wow moment)
# Demo compose runs offline
# No secrets in code
# No placeholders in production code
# All NFRs met

echo "Phase 9 COMPLETE: System ready for SIH submission"
```

---

## FINAL PHASE CHECKLIST

### Pre-SIH Submission Checklist (mandatory before 20 September 2026)

- [ ] All FRs in prd.md §8 are green in end-to-end tests (test matrix prd.md §31.1)
- [ ] All NFRs in prd.md §9 met: OCR <8s p50, API <300ms p95, report gen <10s
- [ ] Live demo works 100% offline (prd.md §38.3, no internet required)
- [ ] No commits with secrets (info-disclosure check passes)
- [ ] All 10 SIH Winning Differentiators from prd.md §36 are demonstrable in a 10-minute live flow
- [ ] Demo script rehearsed twice, timing <10min (prd.md §38)
- [ ] Demo dataset prepared: 10–20 physical packages (prd.md §39)
- [ ] GitHub README includes: architecture diagram, tech stack table, setup quickstart, design system overview
- [ ] PDF report generated in <10s (prd.md §9 target)
- [ ] No "TODO", "FIXME", "XXX", "placeholder" in production code (grep -r check)
- [ ] Design tokens (color, type, spacing) used exclusively — no hardcoded colors (design.md §12)
- [ ] All pages use Ledger Rows and Measure Rule per design.md §3 and §6
- [ ] Audit logs are append-only, no DELETE granted (prd.md §20.1, verify DB grant)
- [ ] Rule versioning works: old inspections reference old rules after an amendment (test prd.md §12.4)

**Git Instructions:**
```bash
git add SUBMISSION_CHECKLIST.md
git commit -m "phase(9): pre-SIH submission verification complete

All 12 checklist items verified. System ready for Grand Finale demo.
Deadline: 20 September 2026

See: prd.md §38 (demo strategy), prd.md §9 (NFRs), tech-stack.md §21 (maintenance)
"
git tag -a sih26034-submission-v1 -m "SIH26034 submission — Legal Metrology Compliance"
git push origin main --tags
```

---

## END OF PHASE DEFINITIONS
