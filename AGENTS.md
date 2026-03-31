# AGENTS.md

## Project
AI-supported collaborative document editor backend in a monorepo.

## Goal
Implement the backend for:
- realtime collaboration/session handling
- websocket/realtime connection logic
- presence and cursor updates
- reconnect/resync flow
- AI integration
- prompt templates
- quota handling
- AI interaction and suggestion logging

## Architecture constraints
- Backend stack: FastAPI
- Architecture style: modular monolith, not microservices
- Keep layers separate:
  - api/routes = transport only
  - schemas = request/response contracts
  - services = business workflows
  - repositories = data access
  - models = persistence models
  - realtime = websocket/session logic
  - prompts = prompt templates
  - integrations = external providers
  - core = config, auth, shared errors
- Do not put business logic directly inside route handlers.
- Do not hardcode prompts inside route handlers or services.
- AI must be suggestion-based. Never auto-apply AI output to document content.
- Realtime traffic must stay separate from normal REST CRUD traffic.
- Follow the existing API contract and references in the reference directory.

## API contract requirements
Implement or preserve these contracts:
- POST /v1/documents/{documentId}/sessions
- POST /v1/documents/{documentId}/ai/interactions
- GET /v1/ai/interactions/{interactionId}
- GET /v1/documents/{documentId}/ai/interactions
- POST /v1/ai/suggestions/{suggestionId}/accept
- POST /v1/ai/suggestions/{suggestionId}/reject
- POST /v1/ai/suggestions/{suggestionId}/apply-edited

Realtime event types:
- join_document
- edit_operation
- presence_update
- remote_operation
- collaborator_presence
- conflict_detected
- resync_required

## Data and behavior rules
- AI requests must store base_revision.
- Suggestions may become stale if the target range changed since request creation.
- Quota checks must happen before LLM calls.
- Role-based AI access must be enforced.
- Reconnect/resync must restore authoritative state when the client falls behind.
- Log AI interactions and suggestion outcomes.
- Use append-only history semantics where applicable.

## Coding rules
- Prefer explicit Pydantic schemas.
- Prefer typed service interfaces.
- Add tests for every new route/service.
- Mock external AI providers in tests.
- Keep functions small and deterministic where possible.
- Do not introduce frontend code unless explicitly requested.

## Deliverable format for code changes
When making a change:
1. summarize the contract being implemented
2. list files created/edited
3. implement code
4. add/update tests
5. note any TODOs or assumptions