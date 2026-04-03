# Collaborative Document Editor with AI Writing Assistant

This repository contains a proof-of-concept collaborative document editor with:

- a FastAPI backend in `app/backend`
- a React + Vite frontend in `app/frontend`

The current repo supports an end-to-end flow for authentication, document creation/loading/saving, version history, permissions and sharing APIs, realtime session bootstrap, and suggestion-based AI actions.

## Current Scope

### Backend

The backend currently exposes:

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`
- `POST /v1/documents`
- `GET /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}/content`
- `POST /v1/documents/{documentId}/export`
- `GET /v1/documents/{documentId}/versions`
- `POST /v1/documents/{documentId}/versions/{versionId}/restore`
- `POST /v1/documents/{documentId}/permissions`
- `DELETE /v1/documents/{documentId}/permissions/{permissionId}`
- `POST /v1/documents/{documentId}/invitations`
- `POST /v1/invitations/{invitationId}/accept`
- `POST /v1/share-links`
- `POST /v1/share-links/{token}/redeem`
- `POST /v1/documents/{documentId}/sessions`
- AI interaction and suggestion endpoints under `/v1/documents/{documentId}/ai/*` and `/v1/ai/*`

Key backend decisions:

- FastAPI remains the API framework.
- The code is organized as a layered modular monolith.
- Route handlers stay thin, services orchestrate behavior, and repositories handle persistence.
- AI is suggestion-based only and does not silently overwrite document content.
- Realtime is represented as a session bootstrap contract, not a full websocket sync engine yet.
- If `AI_COLLAB_AI_API_KEY` and `AI_COLLAB_AI_API_URL` are not set, the backend falls back to a local stub AI provider.

### Frontend

The frontend is a single-page client that can:

- register and sign in
- create a new document
- load an existing document by ID
- edit and save document content
- show revision and latest-version information
- bootstrap a realtime session and display the returned session metadata
- call the backend AI endpoints for summarize and rewrite flows
- accept an AI rewrite suggestion back into the document

The frontend talks to the backend using `VITE_API_BASE_URL`, which defaults to `/v1`. In local Vite development, `/v1` is proxied to `http://127.0.0.1:8000`.

Sharing, invitations, permissions management, and export are implemented at the API layer, but are not yet surfaced as dedicated UI workflows in the current frontend.

## Requirements

- Python 3.11+ recommended
- A recent Node.js and npm release compatible with Vite 8 and React 19

Validated in this workspace on April 3, 2026:

- Python `3.12.7`
- Node `v24.13.0`
- npm `11.6.2`

### Backend Python dependencies

The backend dependencies are listed in `requirements.txt`:

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic-settings`
- `pytest`
- `httpx`
- `black`
- `ruff`

Formatting and linting targets are configured in `pyproject.toml`. Black and Ruff target Python 3.11 syntax/style.

### Frontend dependencies

The frontend dependencies are defined in `app/frontend/package.json`. The main stack is:

- `react`
- `react-dom`
- `vite`
- `eslint`
- `@vitejs/plugin-react`

## Repository Layout

```text
.
├── README.md
├── .env.example
├── requirements.txt
├── pyproject.toml
└── app
    ├── backend
    │   ├── api
    │   ├── core
    │   ├── integrations
    │   ├── models
    │   ├── prompts
    │   ├── repositories
    │   ├── realtime
    │   ├── schemas
    │   ├── services
    │   └── tests
    └── frontend
        ├── public
        ├── src
        ├── package.json
        └── vite.config.js
```

## Setup

### 1. Backend setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Copy the example backend environment file:

```bash
cp .env.example .env
```

If you leave `AI_COLLAB_AI_API_KEY` and `AI_COLLAB_AI_API_URL` empty, the backend will use the built-in stub AI provider.

### 2. Frontend setup

Install frontend dependencies:

```bash
cd app/frontend
npm install
```

If you want the frontend to target a backend on a different origin, create an `.env` file inside `app/frontend` and set:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/v1
```

## Running the Project

### Start the backend

From the repository root:

```bash
uvicorn app.backend.main:app --reload
```

Backend URLs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

### Start the frontend

From `app/frontend`:

```bash
npm run dev
```

By default, Vite serves the frontend at `http://127.0.0.1:5173`.

## Verification

Rechecked in this workspace on April 3, 2026 with:

From the repository root:

```bash
pytest app/backend/tests -q
```

From `app/frontend`:

```bash
npm run lint
npm run build
```

Result:

- backend tests: `54 passed`
- frontend lint: passed
- frontend production build: passed

## Intentionally Minimal / Future Work

This is still a proof-of-concept implementation. A few areas are intentionally not production-complete yet:

- reconnect, resync, presence, and conflict-free live collaboration are not implemented as a full collaboration engine yet
- authentication and secret management are suitable for PoC validation, but not hardened for production deployment
- sharing, invitations, and permissions exist in the API, but the frontend does not yet provide dedicated management screens for them
- the AI assistant is intentionally minimal: no streaming responses, advanced retries, cost controls, or persistent audit logs yet
- observability, CI/CD, release automation, and large-scale deployment concerns are still minimal

## Main Backend Validation File

The most assignment-relevant backend contract coverage lives in `app/backend/tests/test_poc_backend.py`.

That test exercises authentication, document create/load/save, realtime session bootstrap, and the AI contract flow end to end.
