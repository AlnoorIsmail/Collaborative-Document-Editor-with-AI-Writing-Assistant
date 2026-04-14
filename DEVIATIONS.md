# Deviations From Assignment 1 Design

## What Changed

- Authentication moved from access-token-only logic to JWT access tokens plus persisted refresh-token rotation.
- Document listing was expanded to show both owned documents and documents already shared through the repo's existing permission model.
- A dedicated `PATCH /v1/documents/{documentId}/content` route was retained alongside CRUD endpoints because the existing project already used optimistic content saves and version creation through that path.
- Version restore was kept append-only: restoring an old snapshot creates a new current version instead of overwriting history.

## Why It Changed

- Refresh tokens were added to satisfy the assigned backend session scope and make `POST /v1/auth/refresh` meaningful.
- Shared-document listing fits the repo's existing permissions feature better than limiting `GET /v1/documents` to owner-only records.
- Keeping the dedicated content-save route avoided breaking the existing frontend/editor flow while still satisfying document-management requirements.
- Append-only restore preserves auditability and aligns with the repository guidance in `app/AGENTS.md`.

## Compromise Or Improvement

- JWT refresh rotation is an improvement over the previous simpler auth flow.
- Shared-document listing is an improvement because it matches the broader repo behavior.
- Keeping the extra content-save route is a compromise in shape, but it is a deliberate one that preserves existing behavior and keeps versioning logic clean.
- SQLite remains a compromise for simplicity, but it is appropriate for the assignment and easy to run locally.
