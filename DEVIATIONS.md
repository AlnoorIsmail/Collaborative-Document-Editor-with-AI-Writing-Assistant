# Deviations From Assignment 1 Design

## What Changed

- Authentication moved from access-token-only logic to JWT access tokens plus persisted refresh-token rotation.
- Document listing was expanded to show both owned documents and documents already shared through the repo's existing permission model.
- A dedicated `PATCH /v1/documents/{documentId}/content` route was retained alongside CRUD endpoints because the existing project already used optimistic content saves and version creation through that path.
- Version restore was kept append-only: restoring an old snapshot creates a new current version instead of overwriting history.
- Realtime collaboration uses authenticated WebSockets with revision-based synchronization and explicit stale/conflict handling rather than CRDT/OT.
- AI generation uses FastAPI `StreamingResponse` with SSE framing and a suggestion-first review flow instead of mutating document content inline.
- Sharing resolves registered users by either email or generated username, while invitations still persist the resolved account email as the canonical invite target.

## Why It Changed

- Refresh tokens were added to satisfy the assigned backend session scope and make `POST /v1/auth/refresh` meaningful.
- Shared-document listing fits the repo's existing permissions feature better than limiting `GET /v1/documents` to owner-only records.
- Keeping the dedicated content-save route avoided breaking the existing frontend/editor flow while still satisfying document-management requirements.
- Append-only restore preserves auditability and aligns with the repository guidance in `app/AGENTS.md`.
- Revision-based collaboration was chosen because it satisfies the assignment baseline, keeps the protocol explainable, and is much smaller to reason about than introducing a CRDT library late in the project.
- SSE streaming matched the existing request/response AI architecture better than moving all AI traffic onto WebSockets, while still satisfying the streamed-token requirement.
- Username generation was added as a lightweight compatibility layer so the app can support email-or-username sharing without requiring a bigger account-profile redesign.

## Compromise Or Improvement

- JWT refresh rotation is an improvement over the previous simpler auth flow.
- Shared-document listing is an improvement because it matches the broader repo behavior.
- Keeping the extra content-save route is a compromise in shape, but it is a deliberate one that preserves existing behavior and keeps versioning logic clean.
- SQLite remains a compromise for simplicity, but it is appropriate for the assignment and easy to run locally.
- Revision-based collaboration is a compromise relative to the richer CRDT-style Assignment 1 direction, but it is still compliant with the Assignment 2 baseline and was implemented with clearer reconnect/conflict behavior instead of silent overwrite.
- SSE AI streaming is an improvement because it gives visible progressive output and cancellation without forcing the whole AI stack onto a separate transport.
- Generated usernames are a compromise compared with a full profile-management feature, but they provide stable identifiers for sharing and keep existing accounts compatible.
