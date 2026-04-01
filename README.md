# Collaborative Document Editor Backend PoC

This repository contains a collaborative document editor project with both frontend and backend workstreams.

The goal of this PoC is to prove that (backend):

- the FastAPI backend boots and exposes the expected API surface
- a client can authenticate and communicate with the backend end to end
- the request and response JSON contracts are stable in code
- the project is organized using the layered backend structure from the architecture plan

## Frontend Scope



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

## Backend Decisions

These are the main backend decisions made for the PoC:

- `FastAPI` was kept as the backend framework to match the architecture requirement.
- The backend was organized as a layered modular monolith under `app/backend/`.
- Route handlers stay thin and mainly handle transport and dependency wiring.
- Business behavior is pushed into `services/`.
- Data access is kept in `repositories/`.
- Request and response formats are defined with explicit Pydantic schemas in `schemas/`.
- Realtime traffic is represented separately through the session bootstrap contract instead of mixing it into document CRUD routes.
- AI remains suggestion-based, with separate interaction and suggestion endpoints rather than automatic document mutation.
- The PoC uses lightweight stubbed repositories for realtime session bootstrapping and AI generation so the contracts can be validated without introducing a production-ready websocket server or live LLM dependency.
- The backend package was moved under `app/backend` so the repository structure matches the decision to treat `app` as the application root folder.

## What Was Left Out and Why

Some backend work was intentionally left incomplete because this is a proof of concept rather than a full implementation:

- A true websocket collaboration server was not implemented yet. For the PoC, the important part was proving the session bootstrap contract and keeping realtime concerns separate from REST APIs.
- AI calls are mocked instead of hitting a real provider. This keeps the PoC deterministic, testable, and free from external service dependencies.
- Full quota enforcement and persistent AI audit logging were not completed yet because they are production concerns beyond the minimum PoC requirement.
- Reconnect, resync, and conflict handling are represented at the contract level, but not yet built out as a complete live synchronization engine.
- Authentication is sufficient for PoC validation, but not yet hardened as a production auth system.

## What Is Intentionally Minimal

- the focus is backend contract validation, not product completeness
- realtime websocket transport is only represented by the session bootstrap contract, not a full live collaboration server
- AI generation is mocked through a lightweight in-memory repository/provider seam
- some backend concerns are left as future work so the PoC stays small, testable, and aligned with the assignment scope

## Repository Shape

The backend keeps the layered modular-monolith structure required by the architecture:

```text
app/backend/
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
pip install -r requirements.txt
```

3. Optionally copy the example environment file.

```bash
cp .env.example .env
```

4. Start the backend from the repository root.

```bash
uvicorn app.backend.main:app --reload
```

5. Open the generated docs or OpenAPI contract.

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

## Running the PoC Validation Tests

From the repository root:

```bash
pytest app/backend/tests/test_poc_backend.py -q
```

To run the full backend suite:

```bash
pytest app/backend/tests -q
```

You can also run the same checks used by CI:

```bash
ruff check app
black --check app
pytest app/backend/tests -q
```

## Main Test File for the Assignment

The most assignment-relevant backend validation is in:

- `app/backend/tests/test_poc_backend.py`

That file checks that a client can authenticate, create/load/save a document, bootstrap a realtime session, and exercise the AI contract flow with the expected JSON shapes.
