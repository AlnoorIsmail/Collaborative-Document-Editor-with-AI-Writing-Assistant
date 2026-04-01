# Backend PoC Architecture Notes

## Scope

This document describes the backend proof of concept as it is currently implemented in this repository.

- The project is a monorepo.
- The implemented PoC in this repository is backend-focused.
- 
- The goal of this PoC is to prove backend contracts, layering, and end-to-end API behavior rather than deliver a production-ready collaboration platform.

## Current Repository Shape

```text
.
├── app/
│   ├── AGENTS.md
│   └── backend/
├── docs/
│   ├── docs.md
│   └── references/
├── .github/
│   └── workflows/
├── .env.example
├── pyproject.toml
├── README.md
└── requirements.txt
```

The backend application root is `app/backend/`.

## Backend Structure

The backend follows the modular-monolith layering required by the project guidance.

```text
app/backend/
├── api/routes        # transport layer only
├── core              # config, auth, shared errors, db
├── integrations      # external provider seams
├── models            # persistence and internal records
├── prompts           # prompt templates
├── realtime          # realtime event definitions
├── repositories      # data access
├── schemas           # request/response contracts
├── services          # business workflows
└── tests             # route and service validation
```

Design rules currently followed in code:

- route handlers stay thin and delegate to services
- Pydantic schemas define request and response contracts
- repositories encapsulate data access
- AI prompt text lives in `app/backend/prompts/`
- realtime bootstrap is kept separate from normal document CRUD routes
- AI remains suggestion-based and never auto-applies generated content

## Runtime and Persistence

The current PoC uses:

- FastAPI for the HTTP API
- SQLAlchemy for persistence
- SQLite by default through `AI_COLLAB_DATABASE_URL=sqlite:///./collab_editor.db`
- stubbed realtime session storage for contract validation
- a stubbed AI provider and repository for deterministic tests

This means the PoC is intentionally simple to run and test locally.

The following target-state items are not part of the current implementation:

- PostgreSQL
- Redis
- a live websocket collaboration server
- a real external LLM provider

Those remain future implementation steps, not current repository behavior.

## Implemented API Surface

Base path:

```text
/v1
```

### Auth

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`

### Documents

- `POST /v1/documents`
- `GET /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}`
- `PATCH /v1/documents/{documentId}/content`

### Versions

- `GET /v1/documents/{documentId}/versions`
- `POST /v1/documents/{documentId}/versions/{versionId}/restore`

### Permissions, invitations, and share links

- `POST /v1/documents/{documentId}/permissions`
- `DELETE /v1/documents/{documentId}/permissions/{permissionId}`
- `POST /v1/documents/{documentId}/invitations`
- `POST /v1/invitations/{invitationId}/accept`
- `POST /v1/share-links`
- `POST /v1/share-links/{token}/redeem`

### Realtime bootstrap

- `POST /v1/documents/{documentId}/sessions`

### AI

- `POST /v1/documents/{documentId}/ai/interactions`
- `GET /v1/documents/{documentId}/ai/interactions`
- `GET /v1/ai/interactions/{interactionId}`
- `POST /v1/ai/suggestions/{suggestionId}/accept`
- `POST /v1/ai/suggestions/{suggestionId}/reject`
- `POST /v1/ai/suggestions/{suggestionId}/apply-edited`

## Contract and Behavior Notes

The current backend PoC enforces or demonstrates these rules:

- AI interaction requests include `base_revision`
- realtime bootstrap is handled through a dedicated session endpoint
- AI access is role-aware in the service layer
- AI outputs are returned as reviewable suggestions
- suggestion acceptance, rejection, and edited-apply outcomes are logged through the repository abstraction
- reconnect, resync, and conflict concepts are represented in contracts and event definitions

Realtime event names currently defined in code:

- `join_document`
- `edit_operation`
- `presence_update`
- `remote_operation`
- `collaborator_presence`
- `conflict_detected`
- `resync_required`

## Deferred Work

The following work is intentionally not finished in this PoC:

- full websocket transport and live collaboration state propagation
- authoritative reconnect and resync recovery engine
- persistent AI audit storage beyond the PoC stubs
- real quota tracking and enforcement persistence
- export flows
- production auth hardening
- frontend implementation details and frontend test coverage

These are left out to keep the PoC small, deterministic, and focused on backend contract validation.

## Configuration

Local settings are centralized in `app/backend/core/config.py`.

The repository includes `.env.example` with the variables used by the current backend PoC:

- `AI_COLLAB_APP_NAME`
- `AI_COLLAB_API_V1_PREFIX`
- `AI_COLLAB_ENVIRONMENT`
- `AI_COLLAB_DEBUG`
- `AI_COLLAB_DATABASE_URL`
- `AI_COLLAB_REALTIME_URL`
- `AI_COLLAB_SECRET_KEY`
- `AI_COLLAB_ACCESS_TOKEN_EXPIRE_MINUTES`
- `AI_COLLAB_ALGORITHM`
- `AI_COLLAB_ALLOWED_ORIGINS`

## Validation

The backend can be validated from the repository root with:

```bash
ruff check app
black --check app
pytest app/backend/tests -q
```

The most assignment-focused backend flow test is:

```text
app/backend/tests/test_poc_backend.py
```

That test covers authentication, document create/load/save, realtime session bootstrap, and AI interaction contracts end to end.
