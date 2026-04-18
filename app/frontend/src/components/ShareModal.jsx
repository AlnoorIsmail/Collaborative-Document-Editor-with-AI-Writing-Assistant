import { useEffect, useMemo, useRef, useState } from 'react';
import { apiJSON } from '../api';
import { normalizeEmail, validateEmailField } from '../authValidation';
import { buildShareLinkUrl } from '../shareLinks';

const ROLE_OPTIONS = [
  { value: 'editor', label: 'Editor' },
  { value: 'commenter', label: 'Commenter' },
  { value: 'viewer', label: 'Viewer' },
];

const EXPIRY_OPTIONS = [
  { value: 1, label: '1 day' },
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
];

function buildExpiryTimestamp(days) {
  const date = new Date();
  date.setDate(date.getDate() + Number(days));
  return date.toISOString();
}

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function looksLikeEmail(value) {
  return value.includes('@');
}

function normalizeInvitee(value) {
  const trimmed = value.trim();
  return looksLikeEmail(trimmed) ? normalizeEmail(trimmed) : trimmed.toLowerCase();
}

function validateInviteeField(value, { required = false } = {}) {
  const trimmed = value.trim();

  if (!trimmed) {
    return required ? 'Email address or username is required.' : '';
  }

  if (looksLikeEmail(trimmed)) {
    return validateEmailField(trimmed);
  }

  return /^[a-zA-Z0-9._-]{3,64}$/.test(trimmed)
    ? ''
    : 'Enter a valid email address or username.';
}

export default function ShareModal({ docId, onClose }) {
  const [overview, setOverview] = useState(null);
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [submittingInvite, setSubmittingInvite] = useState(false);
  const [creatingLink, setCreatingLink] = useState(false);
  const [busyPermissionId, setBusyPermissionId] = useState(null);
  const [busyLinkId, setBusyLinkId] = useState(null);
  const [invitee, setInvitee] = useState('');
  const [inviteRole, setInviteRole] = useState('editor');
  const [linkRole, setLinkRole] = useState('viewer');
  const [linkRequiresSignIn, setLinkRequiresSignIn] = useState(true);
  const [linkExpiryDays, setLinkExpiryDays] = useState(7);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [inviteEmailTouched, setInviteEmailTouched] = useState(false);
  const [inviteSubmitAttempted, setInviteSubmitAttempted] = useState(false);
  const [inviteEmailServerError, setInviteEmailServerError] = useState('');
  const emailInputRef = useRef(null);

  const activeLinks = useMemo(
    () => overview?.share_links?.filter((shareLink) => !shareLink.revoked) ?? [],
    [overview]
  );
  const inviteEmailError = useMemo(() => {
    if (inviteEmailServerError) {
      return inviteEmailServerError;
    }
    if (inviteSubmitAttempted) {
      return validateInviteeField(invitee, { required: true });
    }
    if (inviteEmailTouched || invitee.trim()) {
      return validateInviteeField(invitee);
    }
    return '';
  }, [inviteEmailServerError, inviteEmailTouched, inviteSubmitAttempted, invitee]);

  async function loadOverview() {
    setLoadingOverview(true);
    try {
      const nextOverview = await apiJSON(`/documents/${docId}/sharing`);
      setOverview(nextOverview);
    } catch (nextError) {
      setError(nextError.message || 'Failed to load sharing settings.');
    } finally {
      setLoadingOverview(false);
    }
  }

  useEffect(() => {
    emailInputRef.current?.focus();
    void loadOverview();
  }, [docId]);

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        onClose();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  async function handleInviteSubmit(event) {
    event.preventDefault();
    setInviteSubmitAttempted(true);
    setInviteEmailTouched(true);

    const validationError = validateInviteeField(invitee, { required: true });
    if (validationError) {
      setError('');
      setSuccess('');
      return;
    }

    const trimmedInvitee = normalizeInvitee(invitee);

    setSubmittingInvite(true);
    setError('');
    setSuccess('');
    setInviteEmailServerError('');

    try {
      const invitation = await apiJSON(`/documents/${docId}/invitations`, {
        method: 'POST',
        body: JSON.stringify({
          invitee: trimmedInvitee,
          role: inviteRole,
        }),
      });
      setSuccess(`Invitation sent to ${invitation.invited_email}.`);
      setInvitee('');
      setInviteRole('editor');
      setInviteEmailTouched(false);
      setInviteSubmitAttempted(false);
      setInviteEmailServerError('');
      await loadOverview();
    } catch (nextError) {
      if (
        nextError.message === 'No account exists for this email.'
        || nextError.message === 'No account exists for this username.'
      ) {
        setInviteEmailServerError(nextError.message);
      } else {
        setError(nextError.message || 'Failed to send invitation.');
      }
    } finally {
      setSubmittingInvite(false);
    }
  }

  async function handleCreateLink(event) {
    event.preventDefault();
    setCreatingLink(true);
    setError('');
    setSuccess('');

    try {
      const createdLink = await apiJSON('/share-links', {
        method: 'POST',
        body: JSON.stringify({
          document_id: docId,
          role: linkRole,
          require_sign_in: linkRequiresSignIn,
          expires_at: buildExpiryTimestamp(linkExpiryDays),
        }),
      });
      setSuccess(`Share link ready: ${buildShareLinkUrl(createdLink.token)}`);
      await loadOverview();
    } catch (nextError) {
      setError(nextError.message || 'Failed to create a share link.');
    } finally {
      setCreatingLink(false);
    }
  }

  async function handleCopyLink(token) {
    const url = buildShareLinkUrl(token);
    try {
      await navigator.clipboard.writeText(url);
      setSuccess(`Copied share link: ${url}`);
      setError('');
    } catch {
      setError('Copying the share link failed. You can copy it manually from the success message.');
      setSuccess(url);
    }
  }

  async function handleRevokePermission(permissionId) {
    setBusyPermissionId(permissionId);
    setError('');
    setSuccess('');
    try {
      await apiJSON(`/documents/${docId}/permissions/${permissionId}`, {
        method: 'DELETE',
      });
      setSuccess('Access removed.');
      await loadOverview();
    } catch (nextError) {
      setError(nextError.message || 'Failed to remove access.');
    } finally {
      setBusyPermissionId(null);
    }
  }

  async function handleRevokeLink(linkId) {
    setBusyLinkId(linkId);
    setError('');
    setSuccess('');
    try {
      await apiJSON(`/share-links/${linkId}`, {
        method: 'DELETE',
      });
      setSuccess('Share link revoked.');
      await loadOverview();
    } catch (nextError) {
      setError(nextError.message || 'Failed to revoke the share link.');
    } finally {
      setBusyLinkId(null);
    }
  }

  return (
    <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal modal-wide modal-tall" role="dialog" aria-modal="true" aria-label="Share document">
        <div className="modal-header">
          <h2 className="modal-title">Share document</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            &#10005;
          </button>
        </div>

        <div className="modal-body modal-scroll">
          <p className="share-helper-text">
            Invite collaborators directly, generate shareable links, and revoke existing access from one place.
          </p>

          <section className="share-section">
            <div className="share-section-header">
              <h3 className="share-section-title">Invite by email or username</h3>
            </div>

            <form onSubmit={handleInviteSubmit} className="share-form">
              <div className="share-invite-grid">
                <label className="field-label share-field share-field-email">
                  Email or username
                  <input
                    ref={emailInputRef}
                    className={`field-input share-email-input ${inviteEmailError ? 'field-input-error' : ''}`}
                    type="text"
                    placeholder="Add by email address or username"
                    value={invitee}
                    onChange={(event) => {
                      setInvitee(event.target.value);
                      setError('');
                      setSuccess('');
                      setInviteEmailServerError('');
                    }}
                    onBlur={() => setInviteEmailTouched(true)}
                    aria-invalid={inviteEmailError ? 'true' : 'false'}
                    aria-describedby="share-invite-email-help"
                  />
                  <span
                    id="share-invite-email-help"
                    className={`field-help ${inviteEmailError ? 'field-help-error' : 'share-field-help'}`}
                  >
                    {inviteEmailError || 'Send an invitation to a valid email address or username.'}
                  </span>
                </label>

                <label className="field-label share-field">
                  Role
                  <select
                    className="field-select"
                    value={inviteRole}
                    onChange={(event) => setInviteRole(event.target.value)}
                  >
                    {ROLE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="share-invite-actions">
                  <button
                    className="btn btn-primary"
                    type="submit"
                    disabled={submittingInvite || Boolean(inviteEmailError) || !invitee.trim()}
                  >
                    {submittingInvite ? 'Sending…' : 'Invite'}
                  </button>
                </div>
              </div>
            </form>
          </section>

          <section className="share-section">
            <div className="share-section-header">
              <h3 className="share-section-title">Share link</h3>
            </div>

            <form onSubmit={handleCreateLink} className="share-form">
              <div className="share-link-grid">
                <label className="field-label">
                  Role
                  <select
                    className="field-select"
                    value={linkRole}
                    onChange={(event) => setLinkRole(event.target.value)}
                  >
                    {ROLE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field-label">
                  Expires after
                  <select
                    className="field-select"
                    value={linkExpiryDays}
                    onChange={(event) => setLinkExpiryDays(Number(event.target.value))}
                  >
                    {EXPIRY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="share-checkbox">
                <input
                  type="checkbox"
                  checked={linkRequiresSignIn}
                  onChange={(event) => setLinkRequiresSignIn(event.target.checked)}
                />
                Require sign-in before this link grants access
              </label>

              <div className="modal-actions">
                <button className="btn btn-secondary" type="submit" disabled={creatingLink}>
                  {creatingLink ? 'Creating…' : 'Create link'}
                </button>
              </div>
            </form>
          </section>

          {error && <div className="error-banner">{error}</div>}
          {success && <div className="share-success-banner">{success}</div>}

          {loadingOverview ? (
            <div className="history-empty-state">Loading sharing settings…</div>
          ) : (
            <>
              <section className="share-section">
                <div className="share-section-header">
                  <h3 className="share-section-title">Current access</h3>
                  {overview?.owner ? (
                    <span className="share-owner-pill">
                      Owner: {overview.owner.display_name}
                      {overview.owner.username ? ` (@${overview.owner.username})` : ''}
                    </span>
                  ) : null}
                </div>

                <div className="share-list">
                  {(overview?.collaborators ?? []).length === 0 ? (
                    <div className="history-empty-state">No collaborators yet.</div>
                  ) : (
                    overview.collaborators.map((collaborator) => (
                      <div className="share-list-item" key={collaborator.permission_id}>
                        <div className="share-list-text">
                          <strong>{collaborator.user.display_name}</strong>
                          <span>{collaborator.user.email}</span>
                          {collaborator.user.username ? (
                            <span>@{collaborator.user.username}</span>
                          ) : null}
                          <span>
                            {collaborator.role}
                            {collaborator.ai_allowed ? ' • AI enabled' : ''}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => handleRevokePermission(collaborator.permission_id)}
                          disabled={busyPermissionId === collaborator.permission_id}
                        >
                          {busyPermissionId === collaborator.permission_id ? 'Removing…' : 'Remove'}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="share-section">
                <div className="share-section-header">
                  <h3 className="share-section-title">Pending invitations</h3>
                </div>

                <div className="share-list">
                  {(overview?.invitations ?? []).length === 0 ? (
                    <div className="history-empty-state">No pending invitations.</div>
                  ) : (
                    overview.invitations.map((invitation) => (
                      <div className="share-list-item" key={invitation.invitation_id}>
                        <div className="share-list-text">
                          <strong>{invitation.invited_email}</strong>
                          <span>{invitation.role}</span>
                          <span>
                            {invitation.status} • expires {formatDate(invitation.expires_at)}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="share-section">
                <div className="share-section-header">
                  <h3 className="share-section-title">Active share links</h3>
                </div>

                <div className="share-list">
                  {activeLinks.length === 0 ? (
                    <div className="history-empty-state">No active share links yet.</div>
                  ) : (
                    activeLinks.map((shareLink) => (
                      <div className="share-list-item" key={shareLink.link_id}>
                        <div className="share-list-text">
                          <strong>{buildShareLinkUrl(shareLink.token)}</strong>
                          <span>
                            {shareLink.role}
                            {shareLink.require_sign_in ? ' • sign-in required' : ' • public'}
                          </span>
                          <span>Expires {formatDate(shareLink.expires_at)}</span>
                        </div>
                        <div className="share-list-actions">
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => handleCopyLink(shareLink.token)}
                          >
                            Copy
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => handleRevokeLink(shareLink.link_id)}
                            disabled={busyLinkId === shareLink.link_id}
                          >
                            {busyLinkId === shareLink.link_id ? 'Revoking…' : 'Revoke'}
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
