# AGENTS.md

## Purpose

This file defines how coding agents and contributors should work in this repository.
The project is an **AI-supported collaborative document editor** built as a **monorepo** with a **feature-based frontend** and a **layered FastAPI backend**.

Primary architectural priorities:
1. real-time collaboration responsiveness and consistency
2. suggestion-based AI, never silent AI edits
3. graceful degradation under failure
4. centralized auth and permission enforcement
5. append-only versioning and auditability

Do not introduce changes that violate those priorities.

---

## Repository Shape

```text
ai-collab-editor/
├── app/
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

### Frontend
Use feature-based organization.

Expected areas:
- `features/editor`
- `features/collaboration`
- `features/ai-assistant`
- `features/documents`
- `features/permissions`
- `services` for API/WebSocket clients
- `state` for shared frontend state

### Backend
Use layered FastAPI organization.

Expected areas:
- `api/routes`
- `core`
- `domain`
- `services`
- `repositories`
- `models`
- `schemas`
- `realtime`
- `prompts`
- `integrations`

### Shared code
Use `packages/` only for framework-independent code.

Allowed:
- shared DTOs/types
- validation schemas
- constants
- pure utilities

Not allowed in shared packages:
- React imports
- FastAPI imports
- ORM models
- provider SDK code
- request context logic

---

## Non-Negotiable Design Rules

### 1. AI is suggestion-based
- AI must return suggestions.
- AI must not directly overwrite document content.
- Users must be able to accept, reject, or edit before apply.
- Persist suggestion outcome when applicable.

### 2. Realtime stays separate from standard REST flows
- Live edits, presence, and cursor state belong to the realtime path.
- Document CRUD, auth, versioning, permissions, and AI lifecycle belong to REST APIs.
- Do not route high-frequency collaboration traffic through normal CRUD endpoints.

### 3. Auth and permissions stay centralized
- Do not scatter permission checks across random files.
- Put shared auth logic in reusable backend dependencies/services.
- Always enforce role checks server-side.
- Frontend visibility logic is not a substitute for backend authorization.

### 4. Versioning is append-only
- Restore operations create a new version entry.
- Do not delete or overwrite history to simulate restore.
- Preserve auditability.

### 5. Prompt logic stays isolated
- Prompt templates belong under `app/backend/prompts/`.
- Avoid inline prompt strings in route handlers.
- Prefer template-based prompt construction.

### 6. Shared contracts drive consistency
- If an API request/response changes, update shared schemas/types and docs in the same change.
- Keep frontend and backend aligned through shared contracts.

---

## Change Routing Guide

### If the change is about editor interaction
Touch primarily:
- `app/frontend/features/editor`
- `app/frontend/state`
- `app/frontend/services`

Avoid:
- embedding provider logic in the UI
- coupling UI components directly to database assumptions

### If the change is about collaboration or live sync
Touch primarily:
- `app/frontend/features/collaboration`
- `app/frontend/services`
- `app/backend/realtime`
- session bootstrap in `api/routes`

Avoid:
- mixing realtime transport with document CRUD handlers
- storing ephemeral cursor state in long-term persistence without clear need

### If the change is about documents or versions
Touch primarily:
- `app/backend/api/routes/documents*`
- `app/backend/services`
- `app/backend/repositories`
- `app/backend/models`
- `app/backend/schemas`

Avoid:
- bypassing repositories from route handlers
- version restore that mutates old entries

### If the change is about AI
Touch primarily:
- `app/backend/api/routes/ai*`
- `app/backend/services`
- `app/backend/prompts`
- `app/backend/integrations`
- `app/backend/schemas`
- frontend suggestion UI under `features/ai-assistant`

Avoid:
- direct AI provider calls from frontend
- direct provider calls from route handlers when orchestration belongs in services
- automatic application of AI output

### If the change is about roles, sharing, invitations, or access
Touch primarily:
- `app/backend/api/routes/auth*`
- `app/backend/api/routes/permissions*`
- `app/backend/services`
- `app/backend/repositories`
- `app/backend/schemas`

Avoid:
- frontend-only permission enforcement
- ad hoc role strings duplicated across files

---

## Coding Standards

### General
- Make the smallest change that fits the architecture.
- Prefer explicit names over clever ones.
- Keep modules cohesive.
- Keep functions focused.
- Avoid hidden side effects.

### Backend
- Routes handle transport and validation only.
- Services handle orchestration and business logic.
- Repositories handle persistence access.
- Integrations wrap external providers.
- Schemas define request/response contracts.

Do not:
- put SQL/ORM-heavy code inside routes
- put provider-specific API handling all over the codebase
- duplicate permission logic in multiple layers without a shared source

### Frontend
- Group code by feature first.
- Keep UI state close to UI features.
- Put networking in `services`, not in leaf components.
- Keep reusable components generic.

Do not:
- call APIs directly from random deeply nested presentational components
- mix collaboration transport code into purely visual components

### Shared packages
- Keep them pure and portable.
- Prefer serializable types and deterministic helpers.

---

## API and Contract Rules

Base path:

```text
/v1
```

Protected endpoints require bearer auth unless explicitly documented otherwise.

Expected endpoint families:
- `/auth/*`
- `/documents/*`
- `/documents/{id}/versions/*`
- `/documents/{id}/permissions/*`
- `/documents/{id}/invitations/*`
- `/share-links/*`
- `/documents/{id}/sessions`
- `/documents/{id}/ai/interactions`
- `/ai/interactions/{id}`
- `/ai/suggestions/{id}/*`

Use status codes consistently:
- `200` success
- `201` created
- `204` no body delete/revoke
- `400` malformed input
- `401` unauthenticated
- `403` unauthorized
- `404` missing resource
- `409` state conflict
- `422` validation error
- `429` quota or rate limit
- `503` temporary provider/service failure

For AI-related failures, distinguish between:
- pending/processing
- permission denied
- quota exceeded
- stale revision/selection
- provider timeout/failure

Do not collapse all of those into a generic error.

---

## Realtime Rules

Session bootstrap should come from a normal API endpoint, then the client joins the realtime channel.

Typical message categories:
- join document
- edit operation
- presence update
- remote operation
- collaborator presence
- conflict detected
- resync required

Rules:
- include revision awareness where needed
- support reconnect and resync
- do not silently discard conflicting or stale states without signaling

---

## AI Rules

### Context handling
- Use the smallest relevant scope.
- Default to selection plus limited surrounding context.
- Do not send full document context unless genuinely necessary.

### Safety and UX
- Suggestions must be reviewable.
- Mark stale AI results when the selected region changed during generation.
- Keep accepted edits undoable through normal editor behavior.

### Provider integration
- Put external provider code under `integrations`.
- Keep retry, timeout, and mapping behavior encapsulated.
- Make provider swapping possible without touching UI code.

### Prompting
- Use prompt templates.
- Keep prompt edits local to `prompts/` where possible.
- Avoid duplicating template intent across multiple files.

---

## Data and Persistence Rules

Main persistent concepts:
- users
- teams
- documents
- document versions
- permissions
- invitations
- share links
- AI interactions
- AI suggestions

Rules:
- current document state is optimized for reads
- version history is immutable/append-only
- AI logs preserve prompt/context/output references as needed
- permissions are explicit and role-driven

---

## Testing Expectations

### Backend
Add or update tests when changing:
- route contracts
- permission logic
- versioning behavior
- AI orchestration
- integration error mapping

### Frontend
Add or update tests when changing:
- editor state behavior
- suggestion review/apply UX
- collaboration indicators
- API client contract assumptions

### AI tests
- mock provider calls
- do not require real LLM calls in normal test runs

### Contract-sensitive changes
If request/response fields change, update:
- backend schema
- shared types
- frontend usage
- docs
- tests

---

## Documentation Expectations

When changing architecture-significant behavior, update the relevant docs under `docs/` and, if needed:
- `README.md`
- API examples
- diagrams or mermaid sources
- this `AGENTS.md`

Examples of architecture-significant changes:
- new role behavior
- new realtime event shapes
- changed AI lifecycle
- changed versioning semantics
- changed shared package boundaries

---

## PR Expectations

Every PR should aim to be:
- scoped
- reviewable
- contract-consistent
- test-backed where appropriate

For non-trivial changes, include:
- what changed
- why it changed
- affected modules
- any contract changes
- any follow-up work

Avoid mixing unrelated refactors with feature changes unless the refactor is required for the feature.

---

## What Agents Should Optimize For

Prefer:
- architectural consistency
- clear contracts
- central permission logic
- safe collaborative behavior
- reviewable AI flows
- maintainable module boundaries

Do not optimize for:
- shortcut implementations that bypass contracts
- rapid UI-only fixes that leave backend rules inconsistent
- automatic AI edits
- premature microservice-style fragmentation

When uncertain, choose the option that preserves:
1. correctness
2. auditability
3. contract clarity
4. modularity
