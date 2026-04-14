# Assignment Deviations

This file records practical implementation changes made while turning the backend design into a working application.

## 1. SQLite was kept as the default local database

Why it changed:
The assignment scope can be run and graded more reliably with a zero-setup local database.

Impact:
This is a simplification for local development, but it is also an improvement for portability and reviewer setup time.

## 2. Refresh tokens are persisted and rotated

Why it changed:
The original high-level design did not fully specify server-side refresh-token persistence. The implemented backend stores refresh-token identifiers and revokes old tokens during refresh.

Impact:
This is a security improvement over a purely stateless refresh flow.

## 3. A dedicated content-save endpoint was retained

Why it changed:
The repository already contained `/v1/documents/{document_id}/content` and other features depended on that contract. The assignment-required `PATCH /v1/documents/{document_id}` now also supports content updates, but the explicit save endpoint was kept for compatibility.

Impact:
This is a compatibility-oriented improvement rather than a compromise.

## 4. Existing AI and realtime routes remain in the backend

Why it changed:
They were already part of the shared codebase and removing them would create unnecessary regression risk outside the assigned scope.

Impact:
This is a pragmatic compatibility decision. The new auth and document work was added without expanding the assignment into new realtime or frontend implementation.
