import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DEFAULT_DOCUMENT_TITLE } from '../documentDisplay';

const STATUS_LABEL = {
  saved: 'Saved',
  saving: 'Saving…',
  unsaved: 'Unsaved changes',
};

const STATUS_CLASS = {
  saved: 'status-saved',
  saving: 'status-saving',
  unsaved: 'status-unsaved',
};

export default function Navbar({
  title,
  onTitleChange,
  saveStatus,
  onSaveNow,
  onOpenHistory,
  onOpenExport,
  onShare,
  isOwner,
  isReadOnly,
  canRestoreHistory,
  onBack,
  user,
  isAiOpen,
  onToggleAi,
  presenceSummary = null,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  // Keep draft in sync when title prop changes externally
  useEffect(() => {
    if (!editing) setDraft(title);
  }, [title, editing]);

  function startEditing() {
    if (isReadOnly) return;
    setDraft(title);
    setEditing(true);
    // Focus happens after state update via the effect below
  }

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  function commitTitle() {
    const trimmed = draft.trim();
    setEditing(false);
    if (trimmed !== title) {
      onTitleChange(trimmed);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') commitTitle();
    if (e.key === 'Escape') {
      setEditing(false);
      setDraft(title);
    }
  }

  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  }

  return (
    <nav className="navbar">
      <div className="navbar-left">
        <button className="btn btn-ghost navbar-back" onClick={onBack} title="All documents">
          &#8592;
        </button>
        <div className="navbar-title-row">
          {editing ? (
            <input
              ref={inputRef}
              className="navbar-title-input"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onBlur={commitTitle}
              onKeyDown={handleKeyDown}
            />
          ) : (
            <span
              className={`navbar-title ${!isReadOnly ? 'navbar-title-editable' : ''}`}
              onClick={startEditing}
              title={isReadOnly ? undefined : 'Click to rename'}
            >
              {title || DEFAULT_DOCUMENT_TITLE}
            </span>
          )}

          {presenceSummary ? (
            <div className="navbar-presence-summary">
              {presenceSummary}
            </div>
          ) : null}
        </div>
      </div>

      <div className="navbar-center">
        <span className={`save-status ${STATUS_CLASS[saveStatus]}`}>
          {STATUS_LABEL[saveStatus]}
        </span>
        {saveStatus === 'unsaved' && (
          <button className="btn btn-ghost save-now-btn" onClick={onSaveNow}>
            Save now
          </button>
        )}
      </div>

      <div className="navbar-right">
        <button className="btn btn-secondary" onClick={onToggleAi}>
          {isAiOpen ? 'Hide AI' : 'Show AI'}
        </button>
        <button className="btn btn-secondary" onClick={onOpenHistory}>
          {canRestoreHistory ? 'History' : 'Versions'}
        </button>
        <button className="btn btn-secondary" onClick={onOpenExport}>
          Export
        </button>
        {isOwner && (
          <button className="btn btn-secondary" onClick={onShare}>
            Share
          </button>
        )}
        {user && (
          <div className="navbar-user">
            <span className="navbar-user-name">{user.username || user.name}</span>
            <span className="navbar-user-email">{user.email}</span>
          </div>
        )}
        <button className="btn btn-ghost" onClick={logout}>
          Sign out
        </button>
      </div>
    </nav>
  );
}
