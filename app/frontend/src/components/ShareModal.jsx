import { useState, useEffect, useRef } from 'react';
import { apiFetch, getErrorMessage } from '../api';

const ROLES = [
  { value: 'editor', label: 'Editor' },
  { value: 'viewer', label: 'Viewer' },
];

export default function ShareModal({ docId, collaborators: initialCollabs, onClose, onUpdate }) {
  const [collaborators, setCollaborators] = useState(initialCollabs);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('editor');
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState(null);
  const emailInputRef = useRef(null);

  useEffect(() => {
    emailInputRef.current?.focus();
  }, []);

  // Close on Escape
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  async function saveCollaborators(updated) {
    const res = await apiFetch(`/documents/${docId}`, {
      method: 'PATCH',
      body: JSON.stringify({ collaborators: updated }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(getErrorMessage(data, 'Failed to update sharing settings'));
    }
    return updated;
  }

  async function handleAdd(e) {
    e.preventDefault();
    setError('');
    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) return;
    if (collaborators.some(c => c.email?.toLowerCase() === trimmedEmail)) {
      setError('This person already has access.');
      return;
    }
    setAdding(true);
    try {
      const updated = [...collaborators, { email: trimmedEmail, role }];
      await saveCollaborators(updated);
      setCollaborators(updated);
      onUpdate(updated);
      setEmail('');
      setRole('editor');
    } catch (err) {
      setError(err.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleRoleChange(index, newRole) {
    const updated = collaborators.map((c, i) => i === index ? { ...c, role: newRole } : c);
    try {
      await saveCollaborators(updated);
      setCollaborators(updated);
      onUpdate(updated);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRemove(index) {
    setRemoving(index);
    setError('');
    try {
      const updated = collaborators.filter((_, i) => i !== index);
      await saveCollaborators(updated);
      setCollaborators(updated);
      onUpdate(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Share document">
        <div className="modal-header">
          <h2 className="modal-title">Share document</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">&#10005;</button>
        </div>

        <div className="modal-body">
          <form onSubmit={handleAdd} className="share-form">
            <div className="share-form-row">
              <input
                ref={emailInputRef}
                className="field-input share-email-input"
                type="email"
                placeholder="Add by email address"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
              <select
                className="field-select"
                value={role}
                onChange={e => setRole(e.target.value)}
              >
                {ROLES.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
              <button className="btn btn-primary" type="submit" disabled={adding || !email.trim()}>
                {adding ? 'Adding…' : 'Invite'}
              </button>
            </div>
            {error && <div className="error-banner">{error}</div>}
          </form>

          {collaborators.length > 0 && (
            <div className="collab-list">
              <h3 className="collab-list-title">People with access</h3>
              <ul>
                {collaborators.map((collab, i) => (
                  <li key={collab.email || collab.user_id || i} className="collab-item">
                    <span className="collab-email">{collab.email}</span>
                    <select
                      className="field-select collab-role-select"
                      value={collab.role}
                      onChange={e => handleRoleChange(i, e.target.value)}
                    >
                      {ROLES.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </select>
                    <button
                      className="btn btn-ghost btn-danger"
                      onClick={() => handleRemove(i)}
                      disabled={removing === i}
                      aria-label={`Remove ${collab.email}`}
                    >
                      {removing === i ? '…' : 'Remove'}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
