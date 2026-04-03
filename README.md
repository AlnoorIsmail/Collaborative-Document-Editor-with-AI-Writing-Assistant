# Collaborative Document Editor with AI Writing Assistant

This repository contains a collaborative document editor with:

- a FastAPI backend under `app/backend`
- a React + Vite frontend under `app/frontend`

The current implementation is still PoC-sized, but it already supports an end-to-end flow for authentication, document creation/loading/saving, version history, sharing/invitations, session bootstrap, and suggestion-based AI actions.

## Current Scope

### Backend

The backend exposes:

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`
- `POST /v1/documents`
- `GET /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}/content`
- version listing and restore endpoints
- permissions, invitations, and share-link endpoints
- realtime session bootstrap through `POST /v1/documents/{documentId}/sessions`
- AI interaction and suggestion endpoints under `/v1/documents/{documentId}/ai/*` and `/v1/ai/*`

Key backend decisions:

- FastAPI was kept as the API framework.
- The code is organized as a layered modular monolith.
- Route handlers stay thin; services hold orchestration logic; repositories handle persistence.
- AI is suggestion-based only. It does not silently overwrite document content.
- Realtime is represented as a session bootstrap contract, not a full websocket sync engine yet.

### Frontend

The frontend provides a single-page client that can:

- register and sign in
- create a new document
- load an existing document by ID
- edit and save document content
- show revision and latest-version information
- bootstrap a realtime session and display the returned session metadata
- call the backend AI endpoints for summarize and rewrite flows
- accept an AI rewrite suggestion back into the document

The frontend talks to the backend using:

- `VITE_API_BASE_URL`
- default value: `/v1`
- in local Vite development, `/v1` is proxied to `http://127.0.0.1:8000`

## Requirements

### Runtime requirements

- Python 3.11+ recommended
- Node.js 24+ recommended
- npm 11+ recommended

Validated locally in this repository:

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

Formatting/lint targets are configured in `pyproject.toml`. Black and Ruff currently target Python 3.11 syntax/style.

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
├── requirements.txt
├── pyproject.toml
├── .env.example
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

Optionally copy the example environment file:

```bash
cp .env.example .env
```

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

## Running the project

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

By default, Vite serves the frontend at:

- `http://127.0.0.1:5173`

## Verification

The repository was rechecked locally with:

### Backend tests

```bash
pytest app/backend/tests -q
```

Result:

- `51 passed`

### Frontend lint

```bash
cd app/frontend
npm run lint
```

### Frontend production build

```bash
cd app/frontend
npm run build
```


## Intentionally minimal / future work

This is still a proof-of-concept implementation. A few things are intentionally not production-complete yet:

- reconnect/resync and conflict-resolution behavior are not a complete collaboration engine yet
- auth is suitable for PoC validation but not fully hardened for production deployment
- broader CI and release automation are still minimal
- Fully functional AI chat, that is personalized and customizable
- Real-time collaboration was left at the session-bootstrap level. The app can create/join a collaboration session, but full live synchronization, presence, cursors, and conflict-free multi-user editing over websockets were intentionally deferred.
- The AI assistant was implemented as a suggestion-based workflow, but production-grade AI concerns were left minimal. The system supports summarize/rewrite flows, and can use a fallback local provider, but streaming responses, advanced retries, cost controls, persistent AI audit logs, and full provider hardening were not completed.
- The frontend was intentionally kept as a single end-to-end client focused on proving backend connectivity and user flows, rather than a fully modular collaboration UI with separate live-editing, presence, and sharing interfaces.
- Authentication and authorization were implemented enough for protected routes and document access control, but not hardened to production standards such as stronger session management, secret rotation, and broader security controls.
- Sharing, invitations, versioning, and document editing are functional, but the project does not yet include production deployment concerns such as CI/CD pipelines, observability, monitoring, and large-scale load handling.

## Main backend validation file

The most assignment-relevant backend contract coverage lives in:

- `app/backend/tests/test_poc_backend.py`

That test exercises authentication, document create/load/save, realtime session bootstrap, and the AI contract flow end to end.
