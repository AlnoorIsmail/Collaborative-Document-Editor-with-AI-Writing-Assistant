# AI-Supported Collaborative Document Editor

## Project Overview

This repository contains the implementation plan and codebase for an **AI-supported collaborative document editor**. The system is designed as a simplified Google Docs–style platform with integrated AI writing assistance. Users can create and manage documents, collaborate in real time, and invoke AI features such as rewriting, summarization, translation, and restructuring.

The project is shaped by six ranked architectural drivers:

1. real-time collaboration responsiveness and consistency
2. AI integration as a core but reviewable feature
3. availability and graceful degradation
4. authentication, authorization, and privacy
5. versioning, auditability, and document lifecycle
6. scalability and growth

These drivers directly determine the system boundaries, repository structure, and implementation priorities.

---

## Core Product Scope

### Collaboration
- Multiple authorized users can edit the same document at the same time.
- Active collaborators, cursor position, and selections are visible to others.
- Conflicts on overlapping regions are detected and surfaced.
- Reconnection should restore the latest known document state and session indicators.

### AI assistance
- AI output is **suggestion-based**, never silently applied.
- Users can request rewrite, summarize, translate, expand, shorten, reorganize, and general writing help.
- Users can accept, reject, or edit suggestions before applying them.
- AI interactions should be logged for auditability.

### Document management
- Create, open, save, version, restore, share, and export documents.
- Restore operations create a **new version entry** instead of overwriting history.
- Sharing supports direct user access, invitations, and link sharing.

### Access control
- Supported document roles: **Owner**, **Editor**, **Commenter**, **Viewer**.
- AI access is role-aware and may also be controlled by workspace or document settings.

---

## Architecture Summary

### Architecture style
- **Monorepo** for coordinated frontend/backend work.
- **Modular monolith** backend with clear internal boundaries.
- **Mixed communication model**:
  - REST APIs for stable resource-oriented actions
  - persistent real-time channel for edits, presence, and collaboration events

### Main containers
- **Frontend app**: editor UI, collaboration indicators, AI suggestion review, sharing UI
- **Backend API**: request/response operations, auth, documents, permissions, versioning
- **Real-time service**: edit propagation, presence, session sync, reconnect support
- **AI integration service**: prompt building, quota handling, model calling, suggestion formatting, logging
- **PostgreSQL**: persistent storage
- **Redis**: ephemeral real-time state and AI queue/support state

### Design principles
- Keep the editor decoupled from backend persistence details.
- Keep AI prompt logic separate from route handlers and business orchestration.
- Keep auth and permission checks centralized.
- Keep shared code framework-independent.
- Prefer append-only history for safety and traceability.

---

## Repository Structure

```text
ai-collab-editor/
├── apps/
│   ├── frontend/
│   └── backend/
├── packages/
├── docs/
├── scripts/
├── .github/
├── .env.example
├── README.md
└── docker-compose.yml
```

### `apps/frontend`
Feature-oriented frontend structure.

```text
apps/frontend/
├── app/
├── pages/
├── features/
│   ├── editor/
│   ├── collaboration/
│   ├── ai-assistant/
│   ├── documents/
│   └── permissions/
├── components/
├── hooks/
├── services/
├── state/
├── types/
├── utils/
└── tests/
```

### `apps/backend`
Layered FastAPI backend.

```text
apps/backend/
├── api/routes/
├── core/
├── domain/
├── services/
├── repositories/
├── models/
├── schemas/
├── realtime/
├── prompts/
├── integrations/
└── tests/
```

### `packages`
Shared, framework-independent code only.

```text
packages/
├── shared-types/
├── shared-validation/
├── shared-constants/
└── shared-utils/
```

Rules for shared packages:
- no React imports
- no FastAPI imports
- no DB clients
- no provider SDK coupling
- keep them portable and pure

---

## Module Decomposition

### 1. Rich-text editor and frontend state
Responsible for:
- local editing state
- selection state
- suggestion preview and application
- collaborator indicators
- local pending changes
- reconnect draft recovery

Depends on:
- API layer
- real-time synchronization layer
- auth/permission state

### 2. Real-time synchronization layer
Responsible for:
- joining/leaving sessions
- sending local operations
- receiving remote operations
- presence updates
- reconnect and resync
- conflict notifications

Depends on:
- editor events
- session bootstrap from backend
- permission validation
- authoritative storage for recovery

### 3. AI assistant service
Responsible for:
- AI request intake
- scope/context selection
- prompt template resolution
- provider calls
- suggestion formatting
- interaction logging
- quota checks
- role-aware AI enforcement

### 4. Document storage and versioning
Responsible for:
- current document state
- append-only version history
- restore as new version
- metadata persistence
- export hooks

### 5. Authentication and authorization
Responsible for:
- identity checks
- role evaluation
- permission validation
- invitation acceptance
- share-link validation
- AI access authorization

### 6. API layer
Responsible for:
- transport contracts
- schema validation
- auth enforcement
- service orchestration
- error responses
- realtime bootstrap endpoints

---

## Data Model Summary

### Main entities
- `USER`
- `TEAM`
- `DOCUMENT`
- `DOCUMENT_VERSION`
- `DOCUMENT_PERMISSION`
- `DOCUMENT_INVITATION`
- `SHARE_LINK`
- `AI_INTERACTION`
- `AI_SUGGESTION`

### Storage model
Documents use a hybrid storage strategy:
- `DOCUMENT` stores the current fast-read state
- `DOCUMENT_VERSION` stores immutable historical snapshots

Benefits:
- efficient current reads during editing
- safe restore behavior
- full audit trail

### Sharing model
Three sharing mechanisms are supported:
- direct user permissions
- team-based access
- token-based share links

### AI history model
- `AI_INTERACTION` stores prompt/context/scope metadata
- `AI_SUGGESTION` stores generated output and final outcome

---

## API Summary

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
- `POST /v1/documents/{documentId}/export`

### Versions
- `GET /v1/documents/{documentId}/versions`
- `GET /v1/documents/{documentId}/versions/{versionId}`
- `POST /v1/documents/{documentId}/versions/{versionId}/restore`

### Permissions, invitations, share links
- `POST /v1/documents/{documentId}/permissions`
- `DELETE /v1/documents/{documentId}/permissions/{permissionId}`
- `POST /v1/documents/{documentId}/invitations`
- `POST /v1/invitations/{invitationId}/accept`
- `POST /v1/share-links`
- `POST /v1/share-links/{token}/redeem`

### Real-time bootstrap
- `POST /v1/documents/{documentId}/sessions`

### AI
- `POST /v1/documents/{documentId}/ai/interactions`
- `GET /v1/documents/{documentId}/ai/interactions`
- `GET /v1/ai/interactions/{interactionId}`
- `POST /v1/ai/suggestions/{suggestionId}/accept`
- `POST /v1/ai/suggestions/{suggestionId}/reject`
- `POST /v1/ai/suggestions/{suggestionId}/apply-edited`

### Response conventions
- `200 OK`
- `201 Created`
- `204 No Content`
- `400 Bad Request`
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`
- `409 Conflict`
- `422 Unprocessable Entity`
- `429 Too Many Requests`
- `503 Service Unavailable`

---

## Real-Time Contract Summary

The real-time layer is separate from normal REST traffic because live editing, presence, and cursor updates have different latency and failure characteristics.

Typical flow:
1. Client calls `POST /v1/documents/{documentId}/sessions`
2. Backend returns a realtime session token and connection info
3. Client connects to the realtime channel
4. Client sends edit and presence messages
5. Server broadcasts remote operations and presence updates
6. Server can issue conflict or resync events

Representative events:
- `join_document`
- `edit_operation`
- `presence_update`
- `remote_operation`
- `collaborator_presence`
- `conflict_detected`
- `resync_required`

---

## AI Design Rules

### Scope
Use the smallest context that can still satisfy the task:
- default to selected text plus limited surrounding context
- only use broader section or document context when required
- avoid sending unnecessary document content to third-party providers

### UX
- AI returns reviewable suggestions
- no automatic document mutation
- suggestion may be edited before apply
- accepted AI edits remain undoable

### Collaboration behavior
- do not hard-lock the selected region during generation
- attach AI requests to a base revision
- mark stale suggestions if the region changed while AI was running
- allow regeneration against the latest text

### Prompting
- use template-based prompts in `apps/backend/prompts/`
- avoid scattering prompt strings in routes or UI code
- keep prompt updates isolated from business logic changes

### Cost and reliability
- support smaller models for lighter tasks and stronger models for heavier tasks
- enforce quotas before provider calls
- degrade gracefully when AI is unavailable
- document editor remains usable if AI is down

---

## Testing Strategy

### Frontend
- unit tests for feature modules
- integration tests for editor/API/WebSocket client behavior

### Backend
- unit tests for services and repositories
- integration tests for API endpoints
- contract tests for request/response schemas
- mocked provider tests for AI flows

### End-to-end
- basic PoC path: frontend loads, calls backend, displays valid response
- optional flows: auth, realtime sync, mock AI suggestion

### AI testing rule
Do not hit real LLM APIs in routine tests. Use mocks/fakes for repeatability, speed, and cost control.

---

## Configuration and Secrets

- local development uses `.env` (never commit it)
- repository includes `.env.example` only
- staging/production secrets live in deployment or CI/CD secret stores
- configuration should be read through a centralized config layer, not scattered across files

Examples of config:
- database URL
- Redis URL
- JWT secret
- LLM API key
- export/storage credentials
- allowed frontend origins

---

## CI/CD and Quality Gates

Expected baseline checks:
- lint frontend and backend
- run backend tests
- run frontend tests
- validate formatting
- block merge on failing checks

Recommended repository automation:
- GitHub Actions for lint/test
- protected main branch
- PR-based workflow
- environment-specific secrets

---

## Team and Ownership Guidance

Suggested ownership split for a two-person backend effort:

### Person A
- auth and permission layer
- document CRUD and versioning
- share links and invitations
- database/repository layer

### Person B
- realtime session bootstrap and collaboration backend
- AI interaction endpoints and suggestion lifecycle
- integration layer, prompt templates, AI logging
- error handling for stale revisions, quota, provider failure

### Shared responsibilities
- shared contracts in `packages/`
- API consistency
- Docker/dev environment
- CI, linting, branch protection
- cross-cutting bug fixes

Feature rule:
If a feature changes shared contracts, update both code and docs together in the same PR.

---

## Immediate PoC Goal

The minimum proof of concept should demonstrate:
- a working frontend page
- a meaningful frontend-to-backend API call
- response data matching the documented contract
- a repository structure that reflects the architecture
- a README that lets someone run it with minimal setup

A simple acceptable PoC path:
1. frontend loads an editor page
2. user clicks create or load document
3. frontend calls backend
4. backend returns documented JSON
5. frontend renders the result

---

## What This Repository Is Optimizing For

- safe collaboration before fancy features
- reviewable AI instead of automatic AI edits
- clean internal boundaries instead of early microservices
- explicit contracts between frontend and backend
- auditability and maintainability over shortcuts

