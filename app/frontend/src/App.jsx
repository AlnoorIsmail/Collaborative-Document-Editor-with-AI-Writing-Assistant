import { useState, useEffect } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [title, setTitle] = useState("Untitled Document");
  const [docId, setDocId] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [instruction, setInstruction] = useState("");
  const [aiOutput, setAiOutput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [sparkle, setSparkle] = useState(false);

  const setStatusFor = (type, msg) => {
    setStatus(type);
    setStatusMsg(msg);
    if (type === "success") setTimeout(() => setStatus("idle"), 3000);
  };

  const createDocument = async () => {
    setStatusFor("loading", "Creating document...");
    try {
      const res = await fetch(`${API_BASE}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, content }),
      });
      const data = await res.json();
      setDocId(data.id);
      setStatusFor("success", `Document created — ID: ${data.id}`);
    } catch {
      setStatusFor("error", "Failed to create document");
    }
  };

  const loadDocument = async () => {
    if (!docId) return setStatusFor("error", "Enter a document ID first");
    setStatusFor("loading", "Loading...");
    try {
      const res = await fetch(`${API_BASE}/documents/${docId}`);
      const data = await res.json();
      setTitle(data.title);
      setContent(data.content);
      setStatusFor("success", "Document loaded");
    } catch {
      setStatusFor("error", "Failed to load document");
    }
  };

  const saveDocument = async () => {
    if (!docId) return setStatusFor("error", "Create a document first");
    setStatusFor("loading", "Saving...");
    try {
      await fetch(`${API_BASE}/documents/${docId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, content }),
      });
      setStatusFor("success", "Saved");
    } catch {
      setStatusFor("error", "Failed to save");
    }
  };

  const runAI = async () => {
    if (!instruction.trim()) return;
    setSparkle(true);
    setAiLoading(true);
    setAiOutput("");

    try {
      const res = await fetch(`${API_BASE}/ai/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, instruction }),
      });
      const data = await res.json();
      setAiOutput(data.suggestion || data.result || JSON.stringify(data));
    } catch {
      setAiOutput("AI service unavailable — this is a placeholder.");
    }

    setAiLoading(false);
  };

  const applySuggestion = () => {
    if (aiOutput) setContent(aiOutput);
  };

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  const charCount = content.length;

  useEffect(() => {
    if (!sparkle) return;
    const timer = setTimeout(() => {
      setSparkle(false);
    }, 1100);
    return () => clearTimeout(timer);
  }, [sparkle]);

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
                <span className="badge-label">ID</span>
                <span className="badge-value">{docId.slice(0, 8)}…</span>
              </>
            ) : (
              <span className="badge-empty">No document</span>
            )}
          </div>
        </div>

        <div className="nav-center">
          <input
            className="title-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
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
          <button className="btn btn-ghost" onClick={loadDocument}>Load</button>
          <button className="btn btn-primary" onClick={createDocument}>New</button>
          <button className="btn btn-success" onClick={saveDocument}>Save</button>
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
            </div>
          </div>

          <textarea
            className="editor editor-glam"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Start writing here…"
            spellCheck
          />
        </section>

        <aside className="ai-panel">
          <div className="ai-header ai-header-glam">
            <span className="ai-icon">◈</span>
            <div>
              <div className="ai-title">AI Assistant</div>
              <div className="ai-subtitle">Rewrite · Summarize · Translate</div>
            </div>
          </div>

          <div className="ai-body">
            <div className="field-group">
              <label className="field-label">Instruction</label>
              <textarea
                className="ai-input"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="e.g. Rewrite this in a more formal tone…"
                rows={3}
              />
            </div>

            <button
              className={`btn btn-ai btn-ai-glam ${aiLoading ? "btn-loading" : ""} ${sparkle ? "sparkle" : ""}`}
              onClick={runAI}
              disabled={aiLoading}
            >
              {aiLoading ? (
                <>
                  <span className="spinner" /> Thinking…
                </>
              ) : (
                <>
                  <span>◈</span> Run AI
                </>
              )}
            </button>

            {aiOutput ? (
              <div className="ai-result">
                <div className="ai-result-header">
                  <span className="field-label">Suggestion</span>
                  <button className="btn-text" onClick={() => setAiOutput("")}>Clear</button>
                </div>
                <div className="ai-result-text">{aiOutput}</div>
                <button className="btn btn-apply" onClick={applySuggestion}>
                  ✓ Apply to document
                </button>
              </div>
            ) : (
              <div className="ai-empty ai-empty-glam">
                <div className="ai-empty-icon">◈</div>
                <p>Give the assistant a prompt and let it work a little magic.</p>
              </div>
            )}
          </div>

          <div className="ai-footer">
            <div className="load-id-group">
              <label className="field-label">Load by ID</label>
              <div className="id-row">
                <input
                  className="id-input"
                  value={docId}
                  onChange={(e) => setDocId(e.target.value)}
                  placeholder="Document ID"
                />
                <button className="btn btn-ghost btn-sm" onClick={loadDocument}>Go</button>
              </div>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}