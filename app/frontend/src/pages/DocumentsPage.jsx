import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiJSON } from '../api';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      apiJSON('/documents'),
      apiJSON('/auth/me'),
    ])
      .then(([docs, me]) => {
        setDocuments(docs);
        setUser(me);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function createDocument() {
    setCreating(true);
    try {
      const doc = await apiJSON('/documents', {
        method: 'POST',
        body: JSON.stringify({ title: 'Untitled document', initial_content: '' }),
      });
      navigate(`/documents/${doc.document_id}`);
    } catch (err) {
      setError(err.message);
      setCreating(false);
    }
  }

  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  return (
    <div className="docs-page">
      <header className="docs-header">
        <span className="docs-brand">CollabDocs</span>
        <div className="docs-header-right">
          {user && <span className="docs-user">{user.name || user.email}</span>}
          <button className="btn btn-ghost" onClick={logout}>Sign out</button>
        </div>
      </header>

      <main className="docs-main">
        <div className="docs-top">
          <h2>My documents</h2>
          <button className="btn btn-primary" onClick={createDocument} disabled={creating}>
            {creating ? 'Creating…' : '+ New document'}
          </button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        {loading ? (
          <div className="docs-loading">Loading…</div>
        ) : documents.length === 0 ? (
          <div className="docs-empty">
            <p>No documents yet.</p>
            <button className="btn btn-primary" onClick={createDocument} disabled={creating}>
              Create your first document
            </button>
          </div>
        ) : (
          <ul className="docs-list">
            {documents.map(doc => (
              <li
                key={doc.document_id}
                className="doc-card"
                onClick={() => navigate(`/documents/${doc.document_id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && navigate(`/documents/${doc.document_id}`)}
              >
                <span className="doc-card-title">{doc.title || 'Untitled document'}</span>
                <span className="doc-card-date">{formatDate(doc.updated_at || doc.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
