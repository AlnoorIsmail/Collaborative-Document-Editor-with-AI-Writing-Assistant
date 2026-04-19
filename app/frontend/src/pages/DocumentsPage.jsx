import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiJSON } from '../api';
import ShareModal from '../components/ShareModal';
import InvitationNotificationBanner from '../components/InvitationNotificationBanner';
import { buildUniqueDisplayTitles, getRoleLabel } from '../documentDisplay';
import usePendingInvitations from '../hooks/usePendingInvitations';
import { APP_NAME, usePageTitle } from '../pageTitle';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inviteFeedback, setInviteFeedback] = useState('');
  const [creating, setCreating] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [sharingDocument, setSharingDocument] = useState(null);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();
  const pendingInvitesRef = useRef(null);
  const lastFocusedInvitesTokenRef = useRef(null);
  const {
    invitations: pendingInvitations,
    loading: loadingInvitations,
    error: invitationsError,
    clearError: clearInvitationsError,
    activeNotification,
    dismissNotification,
    acceptInvitation,
    declineInvitation,
  } = usePendingInvitations();

  const displayTitles = useMemo(
    () => buildUniqueDisplayTitles(documents),
    [documents]
  );
  usePageTitle(APP_NAME);

  const loadDocuments = useCallback(async () => {
    const nextDocuments = await apiJSON('/documents');
    setDocuments(nextDocuments);
    return nextDocuments;
  }, []);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const [docs, me] = await Promise.all([
        loadDocuments(),
        apiJSON('/auth/me'),
      ]);
      setDocuments(docs);
      setUser(me);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [loadDocuments]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

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

  const focusPendingInvites = useCallback(() => {
    if (!pendingInvitesRef.current) {
      return;
    }

    pendingInvitesRef.current.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
    pendingInvitesRef.current.focus();
  }, []);

  useEffect(() => {
    const focusInvitesToken = location.state?.focusInvitesToken;
    if (!focusInvitesToken || loadingInvitations) {
      return;
    }
    if (lastFocusedInvitesTokenRef.current === focusInvitesToken) {
      return;
    }

    lastFocusedInvitesTokenRef.current = focusInvitesToken;
    window.requestAnimationFrame(() => {
      focusPendingInvites();
    });
  }, [focusPendingInvites, loadingInvitations, location.state]);

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

  async function handleAcceptInvitation(invitationId) {
    setInviteFeedback('');
    clearInvitationsError();

    try {
      await acceptInvitation(invitationId);
      await loadDocuments();
      setInviteFeedback('Invitation accepted. The shared document is now in your list.');
    } catch (nextError) {
      setInviteFeedback('');
      setError(nextError.message || 'Failed to accept the invitation.');
    }
  }

  async function handleDeclineInvitation(invitationId) {
    setInviteFeedback('');
    clearInvitationsError();

    try {
      await declineInvitation(invitationId);
      setInviteFeedback('Invitation declined.');
    } catch (nextError) {
      setInviteFeedback('');
      setError(nextError.message || 'Failed to decline the invitation.');
    }
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
        <InvitationNotificationBanner
          invitation={activeNotification}
          onReview={(invitation) => {
            dismissNotification(invitation.invitation_id);
            focusPendingInvites();
          }}
          onDismiss={dismissNotification}
        />

        <div className="docs-top">
          <h2>My documents</h2>
          <button className="btn btn-primary" onClick={createDocument} disabled={creating}>
            {creating ? 'Creating…' : '+ New document'}
          </button>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {invitationsError && <div className="error-banner">{invitationsError}</div>}
        {inviteFeedback && <div className="share-success-banner">{inviteFeedback}</div>}

        {(loadingInvitations || pendingInvitations.length > 0) && (
          <section
            ref={pendingInvitesRef}
            className="pending-invitations-panel"
            aria-label="Pending invitations"
            id="pending-invitations"
            tabIndex={-1}
          >
            <div className="pending-invitations-header">
              <div>
                <h3>Pending invitations</h3>
                <p>Review invites shared directly with your account.</p>
              </div>
            </div>

            {loadingInvitations ? (
              <div className="pending-invitations-empty">Checking for invitations…</div>
            ) : (
              <div className="pending-invitations-list">
                {pendingInvitations.map((invitation) => (
                  <article
                    key={invitation.invitation_id}
                    className="pending-invitation-card"
                  >
                    <div className="pending-invitation-copy">
                      <div className="pending-invitation-top">
                        <strong>{invitation.document_title}</strong>
                        <span className="doc-card-role">
                          {getRoleLabel(invitation.role)}
                        </span>
                      </div>
                      <div className="pending-invitation-meta">
                        Shared by{' '}
                        <strong>
                          {invitation.inviter.display_name || invitation.inviter.email}
                        </strong>
                        {' • '}
                        expires{' '}
                        {formatDate(invitation.expires_at)}
                      </div>
                      <div className="pending-invitation-email">
                        Invited as {invitation.invited_email}
                      </div>
                    </div>

                    <div className="pending-invitation-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => handleDeclineInvitation(invitation.invitation_id)}
                      >
                        Decline
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => handleAcceptInvitation(invitation.invitation_id)}
                      >
                        Accept
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

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
