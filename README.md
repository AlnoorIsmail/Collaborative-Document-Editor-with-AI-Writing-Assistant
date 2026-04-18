# Collaborative Document Editor with AI Writing Assistant

This project implements a React + FastAPI collaborative document editor for Assignment 2. It includes JWT authentication with refresh tokens, role-based sharing, version history and restore, realtime collaboration over authenticated WebSockets, and an AI assistant with streamed responses, reviewable suggestions, undo-after-apply, and per-document interaction history.

## Stack

- Frontend: React + Vite
- Backend: FastAPI + SQLAlchemy
- Persistence: SQLite by default
- Auth: JWT access tokens + rotated refresh tokens
- Realtime: authenticated WebSockets
- AI responses: FastAPI `StreamingResponse` with SSE (`text/event-stream`)

## Implemented Scope

### Authentication and sessions

- Registration and login with securely hashed passwords
- Short-lived access tokens and refresh tokens
- Silent token refresh in the frontend so expired access tokens do not drop the user into raw `401` editing failures
- Session persistence across page refreshes

### Document management

- Document CRUD with metadata
- Responsive dashboard card grid
- Rich-text editor built on Tiptap
- Headings, bold, italic, lists, code blocks, blockquotes, undo/redo
- Autosave with status indication
- Version history with restore
- Export flows

### Access control and sharing

- Owner, editor, and viewer roles
- Server-side permission enforcement
- Share by email with role assignment
- Share links with expiration and revocation support

### Realtime collaboration

- Authenticated session bootstrap
- Authenticated WebSocket collaboration channel
- Presence list and activity updates
- Reconnect handling
- Offline draft recovery and reconciliation
- Conflict banner when remote changes arrive while local unsaved edits exist

### AI assistant

- Rewrite
- Summarize
- Custom prompt / Ask AI
- Whole-document and selected-text scopes
- Streamed token-style output in the sidebar
- Cancel in-progress generation
- Review before apply
- Accept / reject / edit / undo-after-apply flow
- Prompt rendering through a dedicated prompt builder
- Provider abstraction behind a single integration seam
- Per-document AI history UI and backend interaction audit log

## Quick Start

### 1. Create the environment file

```bash
cp .env.example .env
```

### 2. Install backend and frontend dependencies

```bash
./run.sh install
```

### 3. Start the full app with one command

```bash
./run.sh dev
```

That starts:

- FastAPI backend on `http://127.0.0.1:8000`
- Vite frontend on `http://localhost:5173`

### Optional single-process commands

Backend only:

```bash
./run.sh backend
```

Frontend only:

```bash
./run.sh frontend
```

## Environment Variables

The main variables are defined in `.env.example`.

- `SECRET_KEY`: JWT signing secret
- `ACCESS_TOKEN_EXPIRE_MINUTES`: access-token TTL
- `REFRESH_TOKEN_EXPIRE_DAYS`: refresh-token TTL
- `DATABASE_URL`: SQLite database URL by default
- `JWT_ALGORITHM`: JWT signing algorithm
- `AI_COLLAB_ALLOWED_ORIGINS`: allowed CORS origins
- `AI_COLLAB_AI_API_KEY`: optional real AI provider key
- `AI_COLLAB_AI_API_URL`: OpenAI-compatible endpoint URL
- `AI_COLLAB_AI_MODEL`: configured model name

If the AI key and URL are not configured, the backend falls back to the local stub AI provider.

## Running Tests

Backend:

```bash
./run.sh tests
```

Equivalent:

```bash
pytest app/backend/tests -q
```

Frontend:

```bash
cd app/frontend
npm test -- --run
```

## API Docs

FastAPI docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

## Auth Lifecycle

The auth model is:

1. `POST /v1/auth/login` returns an access token, refresh token, and current user.
2. The frontend stores both tokens in browser storage.
3. Protected API requests use the access token.
4. If a protected request gets `401`, the frontend automatically calls `POST /v1/auth/refresh`.
5. The refresh endpoint rotates the refresh token and returns a fresh access token.
6. If refresh fails, the frontend clears auth state and sends the user back to login.

This keeps the editing experience stable during token expiration without showing raw backend auth errors in normal use.

## Realtime Collaboration Architecture

### Session bootstrap

The editor first creates or resumes a collaboration session with:

- `POST /v1/documents/{documentId}/sessions`

That response includes:

- `session_id`
- `session_token`
- `revision`
- `realtime_url`
- `resync_required`
- `missed_revision_count`
- `active_collaborators`

### WebSocket auth

The frontend opens:

- `/v1/documents/{documentId}/sessions/{sessionId}/ws`

The backend validates:

- bearer access token
- session token from session bootstrap

No valid auth means no collaboration session.

### Message protocol

Current server/client message types include:

- `session_joined`
- `presence_snapshot`
- `content_updated`
- `conflict_detected`
- `heartbeat`
- `typing`
- `error`

### Sync strategy

The app uses revision-based synchronization rather than CRDTs. That means:

- background edits are sent with `base_revision`
- the backend broadcasts authoritative document content and revision
- if the document changed remotely while a local draft is unsaved, the UI does not silently overwrite the local draft
- instead it surfaces a conflict/reconciliation choice

### Offline and reconnect behavior

- local unsent drafts are stored client-side
- reconnect attempts happen automatically
- if realtime is unavailable, direct HTTP saves still continue
- recovered drafts are restored when the editor reopens

## AI Streaming Architecture

### Stream route

The sidebar uses:

- `POST /v1/documents/{documentId}/ai/interactions/stream`

The backend returns an SSE stream with events such as:

- `meta`
- `chunk`
- `complete`
- `cancelled`
- `error`

### Cancel route

- `POST /v1/ai/interactions/{interactionId}/cancel`

The frontend can cancel in-progress AI generation. Partial output is preserved in the sidebar when cancellation happens after some text has already streamed in.

### Suggestion workflow

AI responses are not blindly inserted into the document. The current flow is:

1. run AI on whole document or selected text
2. review streamed output in the sidebar
3. accept, reject, or edit
4. apply approved content to the document
5. optionally undo the most recent AI-applied rewrite

### Prompting and provider abstraction

- prompt rendering lives in the backend prompt builder
- context is assembled intentionally instead of dumping the entire document blindly every time
- the AI provider is abstracted behind the backend provider client, so switching providers is localized

### AI history

Every interaction records:

- feature type
- scope
- rendered prompt
- user instruction
- response
- model name
- token usage when available
- accept / reject / modified outcome

The frontend exposes a document-level AI history panel in the sidebar.

## Manual QA Guide

### Multi-user collaboration

Use isolated browser storage contexts:

- User A: normal browser window
- User B: incognito/private window
- Optional User C: separate browser profile or different browser

For each user:

1. log into a different account
2. open the same shared document
3. verify presence updates
4. verify owner/editor/viewer permissions
5. verify edits propagate across sessions
6. verify overlapping edits show the conflict flow instead of silently overwriting local work

### Session isolation note

If you log in as another user in the same browser storage context, that entire session changes identity. That is expected with the current token storage model and is not a valid simulation of two independent collaborators.

### Export QA

1. create a rich-text document with headings, paragraphs, bold text, and lists
2. export as HTML
3. open the downloaded file in a browser
4. verify the output renders formatted HTML instead of showing literal tags like `<p>`

### Version history QA

1. make several manual saves and trigger autosaves
2. open version history
3. confirm the modal scrolls
4. confirm autosaves are hidden by default
5. confirm the autosave toggle reveals them
6. confirm restore still works

Version history is restore/audit history, not the same feature as editor undo.

## Project Structure

- `app/backend`: FastAPI app, services, repositories, models, tests
- `app/frontend`: React app, editor UI, AI sidebar, tests
- `run.sh`: install, dev, backend, frontend, tests
- `.env.example`: example environment config
- `SHIP_FREEZE_ASSIGNMENT2.md`: current ship/freeze decisions
- `DEVIATIONS.md`: documented deviations from Assignment 1

## Deviations

This repository documents Assignment 1 deviations in `DEVIATIONS.md`. The most important implementation choice is that realtime collaboration uses revision-based synchronization and explicit conflict handling rather than CRDT/OT. That was a deliberate baseline-scope tradeoff, not an accidental omission.
