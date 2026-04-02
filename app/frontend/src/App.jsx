import { useEffect, useState } from "react";
import "./App.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "/v1"
).replace(/\/$/, "");

const SESSION_STORAGE_KEY = "collabowrite.session";
const DEFAULT_TITLE = "Untitled Document";
const DEFAULT_CONTENT_FORMAT = "plain_text";
const EMPTY_SNAPSHOT = {
  title: DEFAULT_TITLE,
  content: "",
  aiEnabled: true,
};

function loadStoredSession() {
  if (typeof window === "undefined") {
    return { token: "", user: null };
  }

  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) {
      return { token: "", user: null };
    }

    const parsed = JSON.parse(raw);
    return {
      token: parsed?.token || "",
      user: parsed?.user || null,
    };
  } catch {
    return { token: "", user: null };
  }
}

function persistStoredSession(session) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

function clearStoredSession() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function apiRequest(path, { method = "GET", body, token } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const raw = await response.text();
  let data = null;

  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = raw;
    }
  }

  if (!response.ok) {
    const message =
      data && typeof data === "object" && "message" in data
        ? data.message
        : `Request failed with status ${response.status}.`;

    const error = new Error(message);
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

function getErrorMessage(error, fallback) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}

export default function App() {
  const [token, setToken] = useState(() => loadStoredSession().token);
  const [currentUser, setCurrentUser] = useState(() => loadStoredSession().user);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({
    email: "",
    displayName: "",
    password: "",
  });
  const [authLoading, setAuthLoading] = useState(false);

  const [title, setTitle] = useState(DEFAULT_TITLE);
  const [docId, setDocId] = useState("");
  const [loadDocId, setLoadDocId] = useState("");
  const [content, setContent] = useState("");
  const [revision, setRevision] = useState(0);
  const [contentFormat, setContentFormat] = useState(DEFAULT_CONTENT_FORMAT);
  const [role, setRole] = useState("");
  const [aiEnabled, setAiEnabled] = useState(true);
  const [latestVersionId, setLatestVersionId] = useState(null);
  const [savedSnapshot, setSavedSnapshot] = useState(EMPTY_SNAPSHOT);
  const [liveSession, setLiveSession] = useState(null);

  const [status, setStatus] = useState("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [instruction, setInstruction] = useState("");
  const [aiOutput, setAiOutput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiFeature, setAiFeature] = useState("summarize");
  const [sparkle, setSparkle] = useState(false);
  const [interactionId, setInteractionId] = useState("");
  const [suggestionId, setSuggestionId] = useState("");

  const isAuthenticated = Boolean(token);
  const hasUnsavedChanges =
    title !== savedSnapshot.title ||
    content !== savedSnapshot.content ||
    aiEnabled !== savedSnapshot.aiEnabled;

  const setStatusFor = (type, msg) => {
    setStatus(type);
    setStatusMsg(msg);

    if (type === "success") {
      window.setTimeout(() => setStatus("idle"), 3000);
    }
  };

  const clearAiState = () => {
    setAiOutput("");
    setSuggestionId("");
    setInteractionId("");
  };

  const applyDocumentState = (document) => {
    const nextDocId = String(document.document_id);
    const nextContent = document.current_content || "";
    const nextAiEnabled = Boolean(document.ai_enabled);
    const nextRevision = document.revision ?? 0;

    setDocId(nextDocId);
    setLoadDocId(nextDocId);
    setTitle(document.title);
    setContent(nextContent);
    setRevision(nextRevision);
    setContentFormat(document.content_format || DEFAULT_CONTENT_FORMAT);
    setRole(document.role || "");
    setAiEnabled(nextAiEnabled);
    setLatestVersionId(
      document.latest_version?.version_id ?? document.latest_version_id ?? null,
    );
    setSavedSnapshot({
      title: document.title,
      content: nextContent,
      aiEnabled: nextAiEnabled,
    });
  };

  const bootstrapSession = async (documentId, lastKnownRevision) => {
    if (!token) {
      return null;
    }

    try {
      const session = await apiRequest(`/documents/${documentId}/sessions`, {
        method: "POST",
        token,
        body: {
          last_known_revision: lastKnownRevision,
        },
      });

      setLiveSession({
        sessionId: session.session_id,
        realtimeUrl: session.realtime_url,
        revision: session.revision,
      });

      return session;
    } catch {
      setLiveSession(null);
      return null;
    }
  };

  const fetchDocument = async (documentIdentifier, { showStatus = true } = {}) => {
    if (!token) {
      throw new Error("Sign in before loading a document.");
    }

    if (showStatus) {
      setStatusFor("loading", "Loading document...");
    }

    const document = await apiRequest(`/documents/${documentIdentifier}`, {
      token,
    });

    applyDocumentState(document);
    clearAiState();
    await bootstrapSession(document.document_id, document.revision ?? 0);

    if (showStatus) {
      setStatusFor("success", "Document loaded");
    }

    return document;
  };

  const createDocument = async () => {
    if (!token) {
      return setStatusFor("error", "Sign in before creating a document.");
    }

    const nextTitle = title.trim() || DEFAULT_TITLE;
    setTitle(nextTitle);
    setStatusFor("loading", "Creating document...");

    try {
      const document = await apiRequest("/documents", {
        method: "POST",
        token,
        body: {
          title: nextTitle,
          initial_content: content,
          content_format: contentFormat,
          ai_enabled: aiEnabled,
        },
      });

      applyDocumentState(document);
      clearAiState();
      await bootstrapSession(document.document_id, document.revision ?? 0);
      setStatusFor("success", `Document created. ID: ${document.document_id}`);
    } catch (error) {
      setStatusFor("error", getErrorMessage(error, "Failed to create document."));
    }
  };

  const saveDocument = async ({ quiet = false } = {}) => {
    if (!token) {
      const error = new Error("Sign in before saving your document.");
      if (!quiet) {
        setStatusFor("error", error.message);
      }
      throw error;
    }

    const nextTitle = title.trim() || DEFAULT_TITLE;
    if (nextTitle !== title) {
      setTitle(nextTitle);
    }

    try {
      if (!docId) {
        if (!quiet) {
          setStatusFor("loading", "Creating document...");
        }

        const document = await apiRequest("/documents", {
          method: "POST",
          token,
          body: {
            title: nextTitle,
            initial_content: content,
            content_format: contentFormat,
            ai_enabled: aiEnabled,
          },
        });

        applyDocumentState(document);
        clearAiState();
        await bootstrapSession(document.document_id, document.revision ?? 0);

        if (!quiet) {
          setStatusFor("success", `Document created. ID: ${document.document_id}`);
        }

        return document;
      }

      const metadataChanged =
        nextTitle !== savedSnapshot.title || aiEnabled !== savedSnapshot.aiEnabled;
      const contentChanged = content !== savedSnapshot.content;

      if (!metadataChanged && !contentChanged) {
        if (!quiet) {
          setStatusFor("success", "No changes to save.");
        }
        return {
          document_id: Number(docId),
          revision,
        };
      }

      if (!quiet) {
        setStatusFor("loading", "Saving...");
      }

      if (metadataChanged) {
        await apiRequest(`/documents/${docId}`, {
          method: "PATCH",
          token,
          body: {
            title: nextTitle,
            ai_enabled: aiEnabled,
          },
        });
      }

      if (contentChanged) {
        const saved = await apiRequest(`/documents/${docId}/content`, {
          method: "PATCH",
          token,
          body: {
            content,
            base_revision: revision,
          },
        });

        setRevision(saved.revision);
        setLatestVersionId(saved.latest_version_id);
      }

      const refreshed = await apiRequest(`/documents/${docId}`, {
        token,
      });

      applyDocumentState(refreshed);
      await bootstrapSession(refreshed.document_id, refreshed.revision ?? 0);

      if (!quiet) {
        setStatusFor("success", "Saved");
      }

      return refreshed;
    } catch (error) {
      if (!quiet) {
        setStatusFor("error", getErrorMessage(error, "Failed to save document."));
      }
      throw error;
    }
  };

  const loadDocument = async () => {
    if (!token) {
      return setStatusFor("error", "Sign in before loading a document.");
    }

    if (!loadDocId.trim()) {
      return setStatusFor("error", "Enter a document ID first.");
    }

    try {
      await fetchDocument(loadDocId.trim());
    } catch (error) {
      setStatusFor("error", getErrorMessage(error, "Failed to load document."));
    }
  };

  const pollInteraction = async (nextInteractionId) => {
    for (let attempt = 0; attempt < 8; attempt += 1) {
      const detail = await apiRequest(`/ai/interactions/${nextInteractionId}`, {
        token,
      });

      if (detail.status === "completed" && detail.suggestion) {
        return detail;
      }

      if (detail.status === "failed") {
        throw new Error("The AI interaction failed.");
      }

      await wait(700);
    }

    throw new Error("The AI is still processing. Try again in a moment.");
  };

  const runAI = async () => {
    if (!token) {
      return setStatusFor("error", "Sign in before using the AI assistant.");
    }

    if (!content.trim()) {
      return setStatusFor("error", "Write something before asking the AI to help.");
    }

    setSparkle(true);
    setAiLoading(true);
    setAiOutput("");
    setSuggestionId("");

    try {
      const document = await saveDocument({ quiet: true });
      const resolvedDocumentId = document.document_id ?? docId;
      const resolvedRevision = document.revision ?? revision;

      const created = await apiRequest(
        `/documents/${resolvedDocumentId}/ai/interactions`,
        {
          method: "POST",
          token,
          body: {
            feature_type: aiFeature,
            scope_type: "document",
            selected_text_snapshot: content,
            surrounding_context: `Title: ${title}\n\n${content.slice(0, 4000)}`,
            user_instruction: instruction.trim() || undefined,
            base_revision: resolvedRevision,
            parameters: {},
          },
        },
      );

      setInteractionId(created.interaction_id);

      const detail = await pollInteraction(created.interaction_id);
      setInteractionId(detail.interaction_id);
      setSuggestionId(detail.suggestion?.suggestion_id || "");
      setAiOutput(detail.suggestion?.generated_output || "");

      if (detail.suggestion?.stale) {
        setStatusFor("error", "The AI suggestion became stale. Save and try again.");
      } else {
        setStatusFor(
          "success",
          aiFeature === "summarize" ? "Summary ready" : "AI suggestion ready",
        );
      }
    } catch (error) {
      clearAiState();
      setStatusFor("error", getErrorMessage(error, "AI request failed."));
    } finally {
      setAiLoading(false);
    }
  };

  const applySuggestion = async () => {
    if (!token) {
      return setStatusFor("error", "Sign in before applying AI output.");
    }

    if (aiFeature === "summarize") {
      return setStatusFor(
        "error",
        "Summaries are review-only. Switch to rewrite mode to apply AI output.",
      );
    }

    if (!docId || !suggestionId || !aiOutput) {
      return setStatusFor("error", "Run the AI assistant first.");
    }

    if (hasUnsavedChanges) {
      return setStatusFor(
        "error",
        "Save or discard your local edits before applying the AI suggestion.",
      );
    }

    setAiLoading(true);

    try {
      const applied = await apiRequest(`/ai/suggestions/${suggestionId}/accept`, {
        method: "POST",
        token,
        body: {
          apply_to_range: {
            start: 0,
            end: content.length,
          },
        },
      });

      setRevision(applied.new_revision);

      const refreshed = await apiRequest(`/documents/${docId}`, {
        token,
      });

      applyDocumentState(refreshed);
      await bootstrapSession(refreshed.document_id, refreshed.revision ?? applied.new_revision);
      clearAiState();
      setInstruction("");
      setStatusFor("success", "Suggestion applied to the document");
    } catch (error) {
      setStatusFor(
        "error",
        getErrorMessage(error, "Failed to apply the AI suggestion."),
      );
    } finally {
      setAiLoading(false);
    }
  };

  const handleAuthInputChange = (event) => {
    const { name, value } = event.target;
    setAuthForm((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const handleAuthSubmit = async (event) => {
    event.preventDefault();

    if (!authForm.email.trim() || !authForm.password) {
      return setStatusFor("error", "Email and password are required.");
    }

    if (authMode === "register" && !authForm.displayName.trim()) {
      return setStatusFor("error", "Display name is required when creating an account.");
    }

    setAuthLoading(true);

    try {
      const normalizedEmail = authForm.email.trim().toLowerCase();

      if (authMode === "register") {
        await apiRequest("/auth/register", {
          method: "POST",
          body: {
            email: normalizedEmail,
            display_name: authForm.displayName.trim(),
            password: authForm.password,
          },
        });
      }

      const login = await apiRequest("/auth/login", {
        method: "POST",
        body: {
          email: normalizedEmail,
          password: authForm.password,
        },
      });

      const nextUser = login.user;
      setToken(login.access_token);
      setCurrentUser(nextUser);
      persistStoredSession({
        token: login.access_token,
        user: nextUser,
      });
      setAuthForm((current) => ({
        ...current,
        email: normalizedEmail,
        password: "",
      }));
      setStatusFor(
        "success",
        authMode === "register"
          ? "Account created and signed in"
          : `Signed in as ${nextUser.display_name}`,
      );
    } catch (error) {
      setStatusFor("error", getErrorMessage(error, "Authentication failed."));
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    clearStoredSession();
    setToken("");
    setCurrentUser(null);
    setLiveSession(null);
    clearAiState();
    setStatusFor("success", "Signed out");
  };

  const handleSaveClick = async () => {
    try {
      await saveDocument();
    } catch {
      // saveDocument already sets the user-facing error state
    }
  };

  useEffect(() => {
    if (!token) {
      return undefined;
    }

    let isActive = true;

    const syncCurrentUser = async () => {
      try {
        const me = await apiRequest("/auth/me", { token });

        if (!isActive) {
          return;
        }

        setCurrentUser(me);
        persistStoredSession({
          token,
          user: me,
        });
      } catch {
        if (!isActive) {
          return;
        }

        clearStoredSession();
        setToken("");
        setCurrentUser(null);
        setLiveSession(null);
        setStatusFor("error", "Your session expired. Sign in again.");
      }
    };

    syncCurrentUser();

    return () => {
      isActive = false;
    };
  }, [token]);

  useEffect(() => {
    if (!sparkle) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setSparkle(false);
    }, 1100);

    return () => window.clearTimeout(timer);
  }, [sparkle]);

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  const charCount = content.length;
  const displayUserName =
    currentUser?.display_name || currentUser?.email || "Authenticated User";
  const isSummaryMode = aiFeature === "summarize";
  const aiActionLabel = isSummaryMode ? "Generate summary" : "Run rewrite";
  const aiInstructionLabel = isSummaryMode ? "Summary Focus" : "Instruction";
  const aiInstructionPlaceholder = isSummaryMode
    ? "Optional: focus on action items, decisions, risks, or key takeaways..."
    : "Rewrite this draft in a clearer, more formal style...";
  const aiResultLabel = isSummaryMode ? "Summary" : "Suggestion";

  return (
    <div className="app">
      <nav className="navbar">
        <div className="nav-left">
          <div className="logo">
            <span className="logo-icon">✦</span>
            <span className="logo-text">Collabowrite</span>
          </div>

          <div className="doc-id-badge">
            {docId ? (
              <>
                <span className="badge-label">DOC</span>
                <span className="badge-value">{docId}</span>
              </>
            ) : (
              <span className="badge-empty">Draft only</span>
            )}
          </div>

          {liveSession ? (
            <div className="doc-id-badge live-badge">
              <span className="badge-label">LIVE</span>
              <span className="badge-value">{liveSession.sessionId}</span>
            </div>
          ) : null}
        </div>

        <div className="nav-center">
          <input
            className="title-input"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Document title"
          />
        </div>

        <div className="nav-right">
          <div className={`status-pill status-${status}`}>
            {status === "loading" && <span className="spinner" />}
            {status === "success" && <span>✓</span>}
            {status === "error" && <span>✕</span>}
            <span>{statusMsg || "Ready"}</span>
          </div>

          <button className="btn btn-ghost" onClick={loadDocument} disabled={!isAuthenticated}>
            Load
          </button>
          <button className="btn btn-primary" onClick={createDocument} disabled={!isAuthenticated}>
            New
          </button>
          <button className="btn btn-success" onClick={handleSaveClick}>
            Save
          </button>
        </div>
      </nav>

      <main className="main">
        <section className="editor-section">
          <div className="editor-toolbar">
            <span className="toolbar-label">Document</span>

            <div className="doc-stats">
              <span>{wordCount} words</span>
              <span className="dot">·</span>
              <span>{charCount} chars</span>
              <span className="dot">·</span>
              <span>rev {revision}</span>
              <span className="dot">·</span>
              <span>{role || "local draft"}</span>
            </div>
          </div>

          <textarea
            className="editor editor-glam"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Start writing here..."
            spellCheck
          />
        </section>

        <aside className="ai-panel">
          <div className="ai-header ai-header-glam">
            <span className="ai-icon">◈</span>
            <div>
              <div className="ai-title">Backend-connected AI workspace</div>
              <div className="ai-subtitle">
                Auth · Documents · Versions · Summaries · Suggestions
              </div>
            </div>
          </div>

          <div className="ai-body">
            <section className="account-card">
              <div className="account-card-header">
                <span className="field-label">Account</span>
                {isAuthenticated ? (
                  <button className="btn-text" onClick={handleLogout}>
                    Sign out
                  </button>
                ) : null}
              </div>

              {isAuthenticated ? (
                <div className="user-summary">
                  <div className="user-avatar">{displayUserName.slice(0, 1).toUpperCase()}</div>
                  <div className="user-meta">
                    <strong>{displayUserName}</strong>
                    <span>{currentUser?.email}</span>
                    <span className="account-note">
                      Connected to <code>{API_BASE}</code>
                    </span>
                  </div>
                </div>
              ) : (
                <form className="auth-form" onSubmit={handleAuthSubmit}>
                  <div className="auth-switch">
                    <button
                      type="button"
                      className={`mode-chip ${authMode === "login" ? "active" : ""}`}
                      onClick={() => setAuthMode("login")}
                    >
                      Log In
                    </button>
                    <button
                      type="button"
                      className={`mode-chip ${authMode === "register" ? "active" : ""}`}
                      onClick={() => setAuthMode("register")}
                    >
                      Register
                    </button>
                  </div>

                  <input
                    className="ai-input"
                    name="email"
                    type="email"
                    value={authForm.email}
                    onChange={handleAuthInputChange}
                    placeholder="Email"
                    autoComplete="email"
                  />

                  {authMode === "register" ? (
                    <input
                      className="ai-input"
                      name="displayName"
                      value={authForm.displayName}
                      onChange={handleAuthInputChange}
                      placeholder="Display name"
                      autoComplete="name"
                    />
                  ) : null}

                  <input
                    className="ai-input"
                    name="password"
                    type="password"
                    value={authForm.password}
                    onChange={handleAuthInputChange}
                    placeholder="Password"
                    autoComplete={
                      authMode === "register" ? "new-password" : "current-password"
                    }
                  />

                  <button className="btn btn-primary auth-submit" type="submit" disabled={authLoading}>
                    {authLoading ? (
                      <>
                        <span className="spinner" /> Working...
                      </>
                    ) : authMode === "register" ? (
                      "Create account"
                    ) : (
                      "Sign in"
                    )}
                  </button>
                </form>
              )}
            </section>

            <section className="account-card">
              <div className="account-card-header">
                <span className="field-label">Document Settings</span>
              </div>

              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={aiEnabled}
                  onChange={(event) => setAiEnabled(event.target.checked)}
                />
                <span>Allow AI for this document</span>
              </label>

              <div className="helper-text">
                {docId
                  ? `Latest version: ${latestVersionId ?? "none yet"}`
                  : "This draft will be created on the backend when you save or create a new document."}
              </div>

              {liveSession ? (
                <div className="helper-text">
                  Session {liveSession.sessionId} ready at <code>{liveSession.realtimeUrl}</code>
                </div>
              ) : null}
            </section>

            <div className="field-group">
              <label className="field-label">AI Task</label>
              <select
                className="ai-input"
                value={aiFeature}
                onChange={(event) => {
                  setAiFeature(event.target.value);
                  clearAiState();
                }}
                disabled={!isAuthenticated || !aiEnabled || aiLoading}
              >
                <option value="summarize">Summarize document</option>
                <option value="rewrite">Rewrite document</option>
              </select>
            </div>

            <div className="field-group">
              <label className="field-label">{aiInstructionLabel}</label>
              <textarea
                className="ai-input"
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder={aiInstructionPlaceholder}
                rows={3}
                disabled={!isAuthenticated || !aiEnabled}
              />
            </div>

            <button
              className={`btn btn-ai btn-ai-glam ${aiLoading ? "btn-loading" : ""} ${sparkle ? "sparkle" : ""}`}
              onClick={runAI}
              disabled={aiLoading || !isAuthenticated || !aiEnabled}
            >
              {aiLoading ? (
                <>
                  <span className="spinner" /> Thinking...
                </>
              ) : (
                <>
                  <span>◈</span> {aiActionLabel}
                </>
              )}
            </button>

            {interactionId ? (
              <div className="helper-text">
                Interaction ID: <code>{interactionId}</code>
              </div>
            ) : null}

            {aiOutput ? (
              <div className="ai-result">
                <div className="ai-result-header">
                  <span className="field-label">{aiResultLabel}</span>
                  <button className="btn-text" onClick={clearAiState}>
                    Clear
                  </button>
                </div>
                <div className="ai-result-text">{aiOutput}</div>
                {isSummaryMode ? (
                  <div className="helper-text">
                    Summaries stay review-only in the frontend so the original document is not
                    overwritten.
                  </div>
                ) : (
                  <button
                    className="btn btn-apply"
                    onClick={applySuggestion}
                    disabled={aiLoading}
                  >
                    ✓ Apply to backend document
                  </button>
                )}
              </div>
            ) : (
              <div className="ai-empty ai-empty-glam">
                <div className="ai-empty-icon">◈</div>
                <p>
                  Sign in, save your draft, and generate a backend summary or rewrite suggestion
                  from the current document.
                </p>
              </div>
            )}
          </div>

          <div className="ai-footer">
            <div className="load-id-group">
              <label className="field-label">Load by ID</label>
              <div className="id-row">
                <input
                  className="id-input"
                  value={loadDocId}
                  onChange={(event) => setLoadDocId(event.target.value)}
                  placeholder="Document ID"
                />
                <button className="btn btn-ghost btn-sm" onClick={loadDocument} disabled={!isAuthenticated}>
                  Go
                </button>
              </div>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
