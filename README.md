# Collaborative Document Editor with AI Writing Assistant

This repository contains a university software engineering project with:

- a FastAPI backend in `app/backend`
- a React + Vite frontend in `app/frontend`

The backend now includes the assigned implementation scope for:

- JWT authentication with refresh-token rotation
- protected route dependencies for bearer-token validation
- document CRUD for authenticated users
- append-only version history and restore
- pytest unit and integration coverage for auth and document flows

**Project Purpose**
The system supports collaborative document work with AI-assisted writing features. The backend in this repository focuses on secure authentication, document persistence, version tracking, sharing-related extensions already present in the repo, and clean API contracts for the frontend.

**Backend Setup**
Create and activate a Python virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

**Environment Variables**
The backend reads `.env` values through `pydantic-settings`. The main variables are:

- `SECRET_KEY`: signing secret for JWT access and refresh tokens
- `ACCESS_TOKEN_EXPIRE_MINUTES`: short-lived access token TTL
- `REFRESH_TOKEN_EXPIRE_DAYS`: refresh token TTL
- `DATABASE_URL`: SQLite connection string by default
- `JWT_ALGORITHM`: JWT signing algorithm, default `HS256`
- `AI_COLLAB_ALLOWED_ORIGINS`: JSON-list CORS origins; the default local list already includes `http://localhost:5173`

An example file is included at [.env.example](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/.env.example).

**How To Run**
Use the helper script from the repository root:

```bash
./run.sh install
./run.sh backend
```

Equivalent manual backend command:

```bash
uvicorn app.backend.main:app --reload
```

Useful local URLs:

- API docs: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

For local frontend development, Vite proxies `/v1` requests to `http://127.0.0.1:8000` in [vite.config.js](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/frontend/vite.config.js). If you point the frontend directly at the backend with `VITE_API_BASE_URL`, the backend's default CORS list already allows `http://localhost:5173`.

**How To Run Tests**
Run all backend tests:

```bash
./run.sh tests
```

Equivalent manual command:

```bash
pytest app/backend/tests -q
```

**Implemented Backend API Scope**
Authentication:

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `GET /v1/auth/me`

Documents:

- `POST /v1/documents`
- `GET /v1/documents`
- `GET /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}`
- `DELETE /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}/content`
- `GET /v1/documents/{documentId}/versions`
- `POST /v1/documents/{documentId}/versions/{versionId}/restore`

**Architecture Overview**
Auth flow:

- passwords are hashed in [security.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/core/security.py)
- login issues a short-lived access JWT and a persisted refresh JWT
- refresh tokens are stored in SQLite through [refresh_token.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/models/refresh_token.py) and rotated on refresh
- protected routes use shared dependencies from [deps.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/api/deps.py)

Document flow:

- route handlers live in [documents.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/api/routes/documents.py) and [versions.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/api/routes/versions.py)
- orchestration is handled in [document_service.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/services/document_service.py) and [version_service.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/services/version_service.py)
- persistence uses SQLAlchemy models and lightweight repositories against SQLite
- content saves append version entries, and restore creates a brand-new version instead of mutating history

**Testing Overview**
Relevant backend coverage includes:

- unit tests for password hashing and JWT logic in [test_security.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/tests/unit/test_security.py)
- auth integration tests in [test_auth.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/tests/test_auth.py)
- document CRUD integration tests in [test_documents.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/tests/test_documents.py)
- version restore tests in [test_versions.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/tests/test_versions.py)
- end-to-end contract coverage in [test_backend_contracts.py](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/app/backend/tests/test_backend_contracts.py)

**Notes**
- SQLite is used as the default assignment-friendly persistence layer.
- The repository still contains frontend, sharing, invitation, session bootstrap, and AI suggestion code that pre-existed this backend scope, and the new backend changes were integrated with that structure rather than replacing it.
- A short design note for assignment changes is included in [DEVIATIONS.md](/Users/alnoor.ismail/Collaborative-Document-Editor-with-AI-Writing-Assistant-3/DEVIATIONS.md).
