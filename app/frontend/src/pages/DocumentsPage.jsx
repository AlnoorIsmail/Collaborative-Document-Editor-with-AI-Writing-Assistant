import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiJSON } from '../api';
import ShareModal from '../components/ShareModal';
import { buildUniqueDisplayTitles, getRoleLabel } from '../documentDisplay';
import { APP_NAME, usePageTitle } from '../pageTitle';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [sharingDocument, setSharingDocument] = useState(null);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  const displayTitles = useMemo(
    () => buildUniqueDisplayTitles(documents),
    [documents]
  );
  usePageTitle(APP_NAME);

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

  useEffect(() => {
    if (!activeMenuId) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (event.target.closest('[data-doc-actions]')) {
        return;
      }

      setActiveMenuId(null);
    }

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [activeMenuId]);

  async function createDocument() {
    setCreating(true);
    try {
      const doc = await apiJSON('/documents', {
        method: 'POST',
        body: JSON.stringify({ initial_content: '' }),
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

  function openDocument(documentId) {
    navigate(`/documents/${documentId}`);
  }

  async function renameDocument(doc) {
    const currentTitle = displayTitles.get(doc.document_id) || doc.title;
    const nextTitle = window.prompt('Rename document', currentTitle ?? '');
    setActiveMenuId(null);

    if (nextTitle === null) {
      return;
    }

    try {
      const updated = await apiJSON(`/documents/${doc.document_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: nextTitle }),
      });

      setDocuments((current) =>
        current.map((entry) =>
          entry.document_id === doc.document_id
            ? {
                ...entry,
                title: updated.title,
                updated_at: updated.updated_at,
                ai_enabled: updated.ai_enabled,
              }
            : entry
        )
      );
    } catch (nextError) {
      setError(nextError.message);
    }
  }

  async function deleteDocument(doc) {
    setActiveMenuId(null);
    const confirmed = window.confirm(`Delete "${displayTitles.get(doc.document_id) || doc.title}"?`);

    if (!confirmed) {
      return;
    }

    try {
      await apiJSON(`/documents/${doc.document_id}`, {
        method: 'DELETE',
      });
      setDocuments((current) =>
        current.filter((entry) => entry.document_id !== doc.document_id)
      );
    } catch (nextError) {
      setError(nextError.message);
    }
  }

  function shareDocument(doc) {
    setActiveMenuId(null);
    setSharingDocument(doc);
  }

  return (
    <div className="docs-page">
      <header className="docs-header">
        <span className="docs-brand">CollabDocs</span>
        <div className="docs-header-right">
          {user && (
            <div className="docs-user">
              <span className="docs-user-name">{user.display_name || user.username}</span>
              <span className="docs-user-email">{user.email}</span>
            </div>
          )}
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
          <div className="docs-grid" role="list" aria-label="Document dashboard">
            {documents.map(doc => (
              <article
                key={doc.document_id}
                className="doc-card"
              >
                {doc.role === 'owner' && (
                  <div className="doc-card-actions" data-doc-actions>
                    <button
                      type="button"
                      className="doc-card-menu-trigger"
                      aria-label={`More actions for ${displayTitles.get(doc.document_id) || doc.title}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        setActiveMenuId((current) =>
                          current === doc.document_id ? null : doc.document_id
                        );
                      }}
                    >
                      &#8942;
                    </button>

                    {activeMenuId === doc.document_id && (
                      <div className="doc-card-menu" role="menu">
                        <button
                          type="button"
                          className="doc-card-menu-item"
                          onClick={() => renameDocument(doc)}
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          className="doc-card-menu-item"
                          onClick={() => shareDocument(doc)}
                        >
                          Share
                        </button>
                        <button
                          type="button"
                          className="doc-card-menu-item doc-card-menu-item-danger"
                          onClick={() => deleteDocument(doc)}
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                )}

                <button
                  type="button"
                  className="doc-card-button"
                  onClick={() => openDocument(doc.document_id)}
                  aria-label={`Open ${displayTitles.get(doc.document_id) || doc.title}`}
                >
                  <div className="doc-card-top">
                    <div className="doc-card-labels">
                      <span className="doc-card-role">{getRoleLabel(doc.role)}</span>
                      {doc.owner?.display_name && (
                        <span className="doc-card-owner">
                          {doc.role === 'owner'
                            ? 'Owned by you'
                            : `Owner: ${doc.owner.display_name}`}
                        </span>
                      )}
                    </div>
                    <span className="doc-card-date">
                      Last edited {formatDate(doc.updated_at || doc.created_at)}
                    </span>
                  </div>

                  <div className="doc-card-body">
                    <h3 className="doc-card-title">
                      {displayTitles.get(doc.document_id) || doc.title}
                    </h3>
                    <p className="doc-card-preview">
                      {doc.preview_text || 'Empty document'}
                    </p>
                  </div>
                </button>
              </article>
            ))}
          </div>
        )}
      </main>

      {sharingDocument && (
        <ShareModal
          docId={sharingDocument.document_id}
          onClose={() => setSharingDocument(null)}
        />
      )}
    </div>
  );
}
