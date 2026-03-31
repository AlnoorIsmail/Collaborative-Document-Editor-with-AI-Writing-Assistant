# Collaborative Document Editor Backend PoC

This repository currently delivers a backend-focused proof of concept for an AI-supported collaborative document editor. The frontend is intentionally not included in this PoC pass.

The goal of this PoC is to prove that:

- the FastAPI backend boots and exposes the expected API surface
- a client can authenticate and communicate with the backend end to end
- the request and response JSON contracts are stable in code
- the project is organized using the layered backend structure from the architecture plan

## What the PoC Demonstrates

- `POST /v1/auth/register` and `POST /v1/auth/login` for a minimal client session
- `POST /v1/documents` to create a document
- `GET /v1/documents/{documentId}` to load document content
- `PATCH /v1/documents/{documentId}/content` to save content and create a version
- `POST /v1/documents/{documentId}/sessions` for realtime session bootstrap contract validation
- AI suggestion lifecycle contract coverage through:
  - `POST /v1/documents/{documentId}/ai/interactions`
  - `GET /v1/documents/{documentId}/ai/interactions`
  - `GET /v1/ai/interactions/{interactionId}`
  - `POST /v1/ai/suggestions/{suggestionId}/accept`
  - `POST /v1/ai/suggestions/{suggestionId}/reject`
  - `POST /v1/ai/suggestions/{suggestionId}/apply-edited`

## What Is Intentionally Minimal

- no frontend UI is included in this submission
- realtime websocket transport is only represented by the session bootstrap contract, not a full live collaboration server
- AI generation is mocked through a lightweight in-memory repository/provider seam
- quota enforcement, persistent AI audit storage, and production auth hardening are not fully implemented yet
- the PoC focuses on contract validation and backend skeleton quality, not product completeness

## Repository Shape

The backend keeps the layered modular-monolith structure required by the architecture:

```text
backend/apps/backend/
├── api/routes        # transport layer only
├── core              # config, auth, shared errors, db
├── integrations      # external provider seams
├── models            # persistence and internal records
├── prompts           # prompt templates
├── repositories      # data access
├── realtime          # realtime event definitions
├── schemas           # request/response contracts
├── services          # business workflows
└── tests             # route and service validation
```

## Quick Start

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install the minimal dependencies.

```bash
pip install fastapi uvicorn sqlalchemy pydantic-settings pytest httpx
```

3. Start the backend from the `backend` directory.

```bash
cd backend
uvicorn apps.backend.main:app --reload
```

4. Open the generated docs or OpenAPI contract.

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

## Running the PoC Validation Tests

From the `backend` directory:

```bash
pytest apps/backend/tests/test_poc_backend.py -q
```

To run the full backend suite:

```bash
pytest apps/backend/tests -q
```

## Suggested Demo Flow

If you want a short manual demo without a frontend:

1. Register a user.
2. Log in and capture the bearer token.
3. Create a document.
4. Load the document back with `GET /v1/documents/{documentId}`.
5. Save updated content with `PATCH /v1/documents/{documentId}/content`.
6. Call the session bootstrap endpoint.
7. Call the AI interaction endpoint and inspect the resulting suggestion detail.

## Main Test File for the Assignment

The most assignment-relevant backend validation is in:

- `backend/apps/backend/tests/test_poc_backend.py`

That file checks that a client can authenticate, create/load/save a document, bootstrap a realtime session, and exercise the AI contract flow with the expected JSON shapes.
