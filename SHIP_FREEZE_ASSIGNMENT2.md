# Assignment 2 Ship Freeze

## Purpose

This document freezes the current Assignment 2 release scope for the Collaborative Document Editor with AI Writing Assistant.

It is written as a step-by-step ship checklist so the team, reviewers, and grader can follow one clear release path.

This freeze locks these decisions:

- The current ship focuses on stability and usability fixes, not new major interaction patterns.
- Continuous follow-up AI chat is a separate future feature and is not part of the current ship.
- Version history remains a durable restore and audit mechanism, but the user-facing history should hide or group autosave noise by default.
- Multi-user testing must use isolated browser storage contexts. A single shared browser session is not a valid multi-user test setup.

## Step-By-Step Ship Plan

### Step 1. Lock The Current Release Scope

Ship this release with:

- export reliability fix
- version history UX fix
- version history autosave-noise cleanup at the UI and product level
- clear multi-user testing guidance
- auth and session testing guidance for separate users

Do not expand this release to include:

- threaded continuous AI chat
- replacing the existing suggestion-based AI sidebar
- changing the document identity or routing model

Release rule:

- If a change introduces a new major interaction pattern, it does not belong in this ship unless it directly fixes one of the frozen ship-now issues below.

### Step 2. Fix The Ship-Now Problems

Work through the following frozen issues in order.

#### 2.1 HTML Export Shows Literal Tags Like `<p>`

- User-visible symptom:
  Exported HTML can show literal markup instead of rendering formatted HTML.
- Current root cause:
  The backend HTML export path escapes stored rich-text HTML and wraps it in a `<pre>` block, so markup is treated as text.
- Ship recommendation:
  Export rendered rich text as actual HTML, not escaped literal markup.
- Release bucket:
  `Ship Now`

#### 2.2 Version History Modal Becomes Unusable With Many Versions

- User-visible symptom:
  The version history dialog becomes difficult or impossible to use when many entries exist.
- Current root cause:
  The history modal is not using the app’s tall, scrolling modal behavior for long content.
- Ship recommendation:
  Make the version history dialog scrollable and usable for long histories.
- Release bucket:
  `Ship Now`

#### 2.3 Version History Is Too Noisy Because Autosave Creates Many Entries

- User-visible symptom:
  Users see too many revisions, especially when autosave is active, and the history can feel like a duplicate of undo.
- Current root cause:
  Every persisted save path currently appends a durable version entry.
- Ship recommendation:
  Keep full backend history intact, but make the user-facing history hide, filter, or group autosave-heavy revisions by default.
- Freeze note:
  Version history is not the same thing as editor undo. It exists for restore, audit, and explicit document recovery.
- Release bucket:
  `Ship Now`

#### 2.4 Testing With Multiple Users Is Confusing

- User-visible symptom:
  Teams try to test collaboration with multiple users in the same browser context and get confusing auth and presence behavior.
- Current root cause:
  Auth state is stored in shared `localStorage`, so one normal browser session cannot safely represent separate independent users.
- Ship recommendation:
  Document the correct testing method using isolated browser sessions.
- Release bucket:
  `Ship Now`

#### 2.5 Logging In As Another User Changes Access In The Same Browser Context

- User-visible symptom:
  Logging in as another user in the same browser session changes the current page’s effective access and identity.
- Current root cause:
  The frontend session model is global per browser storage context.
- Ship recommendation:
  Treat this as expected with the current auth-storage model and document it clearly in testing guidance. Do not treat one shared browser session as a valid simulation of two users.
- Release bucket:
  `Ship Now`

### Step 3. Freeze The Deferred AI Chat Work

The following issue is explicitly deferred.

#### 3.1 Current AI “Ask AI” Is One-Shot, Not A True Follow-Up Chat

- User-visible symptom:
  Users can send one request at a time, but they do not get a continuous conversation thread with follow-up questions.
- Current root cause:
  The current AI UI is suggestion and request based, not a threaded conversation model.
- Ship recommendation:
  Keep the current sidebar behavior for this release and split continuous AI chat into a separate future feature.
- Release bucket:
  `Deferred`

## Future Feature Freeze: Threaded AI Chat

Threaded AI chat is explicitly frozen as a separate future feature and is not part of the current Assignment 2 ship.

### Frozen Direction

- Keep the existing AI suggestion sidebar behavior for rewrite, summarize, apply, reject, edit, and undo flows.
- Introduce threaded follow-up chat as a separate feature later.
- Do not replace the current suggestion workflow in the current ship.
- Preferred future direction is one AI sidebar with two distinct modes:
  - `Suggestions`
  - `Chat`
- Chat mode should support continuous follow-up questions in the same conversation thread.
- Chat mode should preserve conversation context across messages within the open document.
- This future feature must be scoped, tested, and shipped separately from current stability fixes.

### Messaging Freeze

- The current `Ask AI` flow is not equivalent to a true threaded chat.
- The current release should not market or describe `Ask AI` as a full conversational chat experience.

## Step 4. Run Manual QA In The Correct Order

### 4.1 Multi-User Testing

Use isolated browser storage contexts for each user:

- User A: normal browser window
- User B: incognito or private window
- Optional User C: separate browser profile or a different browser

Each user should:

- log into a different account
- open the same shared document in their own isolated session

Validate:

- sharing permissions
- realtime document updates
- presence indicator changes
- conflict behavior on overlapping edits
- viewer, editor, and owner restrictions

### 4.2 Session-Isolation Note

The following behavior is expected with the current auth model:

- If you log in as another user in the same browser storage context, the session will switch for that context.
- This is expected because auth tokens are stored in shared browser storage.
- It is not a valid way to simulate two independent users.

### 4.3 Export QA

1. Create a rich-text document with headings, bold text, lists, and paragraphs.
2. Export the document as HTML.
3. Verify the exported file renders formatted content.
4. Confirm the file does not display literal tags such as `<p>` as plain text.

### 4.4 Version History QA

1. Create enough saves to overflow the visible history list.
2. Verify the history modal scrolls correctly.
3. Verify the list remains understandable when autosave produces many revisions.
4. Verify restoring an old version still works.
5. Verify version history remains distinct from simple editor undo behavior.

## Step 5. Apply Final Ship Gates

Do not call the release ready until all of the following are true:

- all `Ship Now` issues above are fixed or explicitly documented with a release-approved compromise
- deferred AI chat work remains deferred and is not mixed into the current release
- multi-user testing was performed using isolated browser sessions
- export QA passed
- version history QA passed
- the team can explain why version history and undo are different features

## Public Interfaces And Behavior Frozen By This Document

This document does not introduce code changes. It freezes expected release behavior and future interface boundaries.

### Current Release Keeps

- document identity by `document_id`
- existing JWT access token plus refresh token auth model
- existing one-shot AI suggestion endpoints and sidebar workflow

### Explicitly Out Of Scope For This Release

- a threaded conversational AI interface
- a separate chat persistence model
- replacing the current suggestion pipeline with a chat-first experience

Future threaded AI chat is expected to require its own frontend conversation interface and likely a separate backend interaction model, but that work is explicitly outside the current release.

## Assumptions And Defaults

- File location is the repository root: `SHIP_FREEZE_ASSIGNMENT2.md`
- Audience includes team members, reviewers, and grader
- This is one markdown file, not multiple split documents
- This task documents scope and ship strategy only; it does not implement fixes
- Autosave version noise is treated first as a UX and product filtering problem, not an immediate backend history-removal decision
- Continuous AI chat is frozen as a separate future feature and should not block the current release
