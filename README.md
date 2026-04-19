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
- ProseMirror step-based sync with versioned resync
- Presence list and activity updates
- Remote cursor and selection awareness
- Reconnect handling
- Offline draft recovery and reconciliation
- Overlap-aware conflict detection and resolution

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
- `collab_version`
- `realtime_url`
- `resync_required`
- `missed_revision_count`
- `active_collaborators`

### WebSocket auth

The frontend opens:

- `/v1/documents/{documentId}/sessions/{sessionId}/ws`

The backend validates:

- bearer access token
- signed realtime session token from session bootstrap
- matching `document_id`, `user_id`, and `session_id` claims inside that realtime token

The websocket handshake no longer depends on an in-memory bootstrap-session lookup. The signed realtime token is stateless, short-lived, and specific to the user plus document session. No valid auth means no collaboration session.

### Server-side sync setup

- `POST /v1/documents/{documentId}/sessions` bootstraps the live editor session
- the backend returns a signed realtime `session_token`
- the frontend opens the websocket at `/v1/documents/{documentId}/sessions/{sessionId}/ws`
- the in-memory realtime hub tracks only currently connected sockets, presence, typing, and cursor awareness
- document content sync is handled through versioned ProseMirror step batches plus resync/full-reset fallbacks
- `active_collaborators` in bootstrap comes from the hub's live connected presence, not stale bootstrap records

### Message protocol

Current server/client message types include:

- `session_joined`
- `presence_snapshot`
- `awareness_snapshot`
- `content_updated`
- `conflict_detected`
- `heartbeat`
- `typing`
- `selection_update`
- `step_update`
- `steps_applied`
- `steps_resync`
- `error`

### Sync strategy

The app uses ProseMirror step-based synchronization with versioned server reconciliation rather than a full CRDT. That means:

- normal live edits are sent as ordered step batches with range/context metadata
- the backend advances `collab_version` and rebroadcasts accepted step batches
- if a client falls behind, it receives `steps_resync`
- if the gap is too large or the state is stale, the server can force a full snapshot reset
- overlapping edits are preserved and surfaced through the conflict-resolution workflow instead of silently overwriting confirmed content

### Offline and reconnect behavior

- local unsent drafts are stored client-side
- reconnect attempts always perform a fresh session bootstrap before opening a new websocket
- if realtime is unavailable, direct HTTP saves still continue
- recovered drafts are restored when the editor reopens
- remote presence and cursor awareness are cleared while offline/reconnecting and redrawn only after a fresh realtime handshake succeeds

### How to verify live realtime

1. open the same shared document in two isolated browser sessions and different user accounts
2. open DevTools and confirm the websocket request upgrades with `101 Switching Protocols`
3. confirm frames/events such as `session_joined`, `presence_snapshot`, and step traffic are visible
4. verify active users appear in both sessions
5. verify remote cursor/selection updates appear only while the realtime connection is connected
6. disconnect one session and confirm the editor falls back to local saves plus reconnect behavior instead of pretending presence is still live

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
5. verify the websocket upgrades successfully in DevTools
6. verify edits propagate across sessions
7. verify remote cursors and text selections are visible while both users are connected
8. verify overlapping edits show the conflict flow instead of silently overwriting local work

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

This repository documents Assignment 1 deviations in `DEVIATIONS.md`. The most important collaboration choice is that the editor now uses ProseMirror step-based synchronization with explicit conflict preservation and resolution rather than a full CRDT such as Yjs. That is closer to OT-style collaboration than the earlier revision-only baseline, while still remaining simpler than a full CRDT stack.
