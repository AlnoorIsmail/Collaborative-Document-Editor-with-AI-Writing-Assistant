# Deviations From Assignment 1 Design

## Overview

Our Assignment 1 design and our final Assignment 2 implementation are aligned on the core product direction: a React frontend, a FastAPI backend, JWT-based authentication, real-time collaboration, AI-assisted writing, version history, and role-based sharing.

The final implementation does differ from the Assignment 1 design in a few important places. Those deviations are documented below, along with the reason for each change and whether we consider it an improvement or a compromise.

## 1. Architecture Packaging

### What changed

Assignment 1 described the system as a set of conceptual components:

- frontend editor
- backend API
- real-time synchronization layer
- AI integration service
- database

The final implementation keeps those responsibilities, but packages them as a modular monolith rather than separate deployable services. In practice, the project ships as:

- `app/frontend`: React application
- `app/backend`: one FastAPI application with internal modules for auth, documents, realtime, AI, comments, sharing, and persistence

### Why it changed

This reduced operational complexity and made the system much easier to run locally with the single-command Assignment 2 setup. It also kept cross-feature changes faster because the collaboration logic, AI logic, and document services could share contracts directly inside one backend codebase.

### Improvement or compromise

This is mostly an improvement for assignment delivery and local setup, but a compromise for independent scaling. A more distributed architecture could scale subsystems separately, but would have added significant implementation and debugging overhead for this project.

## 2. Real-Time Synchronization Strategy

### What changed

Assignment 1 emphasized real-time collaboration, live presence, cursor visibility, conflict handling, and session recovery. The final implementation delivers those goals, but the sync strategy is a ProseMirror step-based WebSocket protocol with:

- authenticated WebSocket sessions
- reconnect bootstrap and state resynchronization
- remote cursor and selection awareness
- explicit conflict detection and preservation

We did not introduce a full CRDT or standalone OT engine.

### Why it changed

A step-based sync model was much more achievable within the assignment timeline while still supporting the required user-visible collaboration features. It also gave us a clearer protocol to explain during the demo and technical Q&A.

### Improvement or compromise

This is a compromise relative to a more ambitious always-mergeable collaboration engine. However, it is still a solid implementation choice for Assignment 2 because it meets the baseline, supports awareness features, and handles reconnect and stale-state cases explicitly instead of silently overwriting content.

## 3. AI Feature Packaging

### What changed

Assignment 1 listed AI capabilities such as rewrite, summarize, translate, grammar correction, and content generation. The final implementation ships:

- rewrite
- summarize
- translate
- grammar fix
- expand
- custom prompt

Instead of a separate dedicated "content generation" workflow, the final system covers that need through the custom-prompt flow and the expand action.

### Why it changed

This gave us a simpler and more consistent AI UX. Rather than building multiple overlapping generation screens, we concentrated the interaction model into one sidebar with streaming, review-before-apply, cancel, history, and undo support.

### Improvement or compromise

This is an improvement. The feature surface is still rich, but the final product is more coherent and easier to demonstrate.

## 4. Sharing Model And AI Permissions

### What changed

Assignment 1 called for invitations and shareable links. The final implementation supports both, but with stricter rules than the broad Assignment 1 description implied:

- invitations target existing users resolved by email or username
- share links require sign-in before redemption
- editors can invoke AI by default
- viewers cannot invoke AI
- commenter remains supported as an extra role beyond the baseline

### Why it changed

These rules made permission enforcement clearer and safer on the backend. Requiring authentication for share-link redemption also keeps access tied to an actual account instead of allowing anonymous link redemption.

### Improvement or compromise

This is mostly an improvement for security and baseline compliance. The only compromise is that share links are less open than a public-link model, but that tradeoff is deliberate and easier to defend in a course setting focused on secure access control.

## 5. Commenter Role Behavior

### What changed

Assignment 1 listed `commenter` as one of the supported roles. In the final implementation, commenter access is not treated as lightweight editing. Instead, commenters:

- cannot change document body content
- can use the dedicated comments workflow
- interact through a comments sidebar rather than direct text edits

### Why it changed

This made the role boundaries clearer. It avoids a confusing situation where a user appears to be "commenting" but is actually mutating the shared document.

### Improvement or compromise

This is an improvement because it makes the `commenter` role a real product behavior instead of just another editor variant with fewer buttons.

## 6. Export Scope

### What changed

Assignment 1 mentioned exporting to formats such as PDF and DOCX. The final implementation currently supports:

- HTML
- plain text
- Markdown
- JSON

It does not currently ship PDF or DOCX export.

### Why it changed

We prioritized getting the editor, collaboration, permissions, AI workflow, versioning, and tests stable before adding heavier document-conversion dependencies. The implemented formats are deterministic, lightweight, and easy to support locally.

### Improvement or compromise

This is a compromise. The implemented export feature is useful, but narrower than the broader Assignment 1 vision.

## 7. Security And Deployment Assumptions

### What changed

Assignment 1 described encryption in transit and encryption at rest. The final repository enforces:

- hashed passwords
- JWT access and refresh tokens
- authenticated WebSocket connections
- server-side authorization checks

However, the repo does not ship production HTTPS termination or database-at-rest encryption as part of the local assignment setup.

### Why it changed

Assignment 2 requires a local runnable system, not a deployed production environment. We focused on application-layer security and predictable local setup rather than introducing infrastructure that would be hard for evaluators to run on a clean machine.

### Improvement or compromise

This is a compromise. The security model is appropriate for a course project and local evaluation, but a real deployment would still need transport-layer TLS and stronger storage controls.

## 8. Persistence Choice

### What changed

Assignment 1 described a generic database component shaped by scalability and auditability concerns. The final implementation uses SQLite by default and persists:

- users
- documents
- versions
- permissions
- invitations
- share links
- comments
- refresh tokens
- AI history
- collaboration conflict records

### Why it changed

SQLite gave us a very low-friction local setup and kept the submission easy to run without external services.

### Improvement or compromise

This is both an improvement and a compromise. It is an improvement for reproducibility and evaluator experience, but a compromise for horizontal scalability.

## 9. Additional Improvements Beyond Assignment 1

### What changed

The final implementation also includes some behaviors that were not explicit in the Assignment 1 summary:

- in-app invitation inbox and notification banners
- append-only version restore instead of destructive rollback
- caller-specific AI availability surfaced in document responses
- AI interaction history with acceptance and rejection tracking

### Why it changed

These changes improved usability, auditability, and backend/frontend consistency.

### Improvement or compromise

These are improvements. They make the system easier to use and easier to explain during evaluation.

## 10. Explicitly Not Implemented Or Only Partially Implemented

For clarity, the following Assignment 1 ideas were not fully implemented in the final repository as originally envisioned:

- PDF and DOCX export are not implemented. The app currently exports HTML, plain text, Markdown, and JSON.
- A separate dedicated "content generation" AI workflow is not implemented as its own feature. That use case is covered more generally through custom prompts and the expand action.
- A full CRDT or standalone OT collaboration engine is not implemented. The final system uses authenticated ProseMirror step-based synchronization instead.
- Anonymous or public share-link redemption is not implemented. Share links require sign-in before they can grant access.
- Production-grade HTTPS termination and database-at-rest encryption are not part of the repository's local runtime setup.
- Independent horizontal scaling of collaboration, API, and AI subsystems is not implemented because the final project ships as a modular monolith backed by SQLite.

These omissions were not accidental. They reflect deliberate scope choices to keep the implemented system stable, testable, and demonstrable within the Assignment 2 constraints.

## Final Assessment

Most Assignment 1 design goals were preserved in the final system. The main deviations were practical implementation choices:

- keep the architecture modular but not distributed
- use a step-based collaboration model instead of a heavier sync engine
- narrow export formats
- tighten share-link behavior for security
- focus security work on application-layer protections in the local repo

Overall, these changes were reasonable evolutions of the design rather than silent departures. Some were clear improvements, and the compromises were made to keep the system stable, explainable, and fully runnable within the Assignment 2 constraints.
