import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { apiJSON } from '../api';
import {
  clearPendingShareLinkToken,
  getPendingShareLinkToken,
  storePendingShareLinkToken,
} from '../shareLinks';
import { buildPageTitle, usePageTitle } from '../pageTitle';

export default function ShareLinkPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('Checking this share link…');
  usePageTitle(buildPageTitle('Open shared document'));

  useEffect(() => {
    let cancelled = false;

    async function redeemLink() {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        storePendingShareLinkToken(token);
        if (!cancelled) {
          setStatus('auth-required');
          setMessage('Sign in to redeem this share link and open the document.');
        }
        return;
      }

      try {
        const response = await apiJSON(`/share-links/${token}/redeem`, {
          method: 'POST',
        });
        clearPendingShareLinkToken();
        if (!cancelled) {
          navigate(`/documents/${response.document_id}`, { replace: true });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error.status === 401) {
          storePendingShareLinkToken(token);
          setStatus('auth-required');
          setMessage(error.message || 'Sign in to continue with this share link.');
          return;
        }

        setStatus('error');
        setMessage(error.message || 'This share link could not be redeemed.');
      }
    }

    void redeemLink();

    return () => {
      cancelled = true;
    };
  }, [navigate, token]);

  const pendingToken = getPendingShareLinkToken();
  const targetSharePath = pendingToken ? `/share/${pendingToken}` : `/share/${token}`;

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Open shared document</h1>
        <p className="share-helper-text">{message}</p>

        {status === 'loading' ? (
          <div className="docs-loading">Opening…</div>
        ) : null}

        {status === 'auth-required' ? (
          <div className="modal-actions modal-actions-stacked">
            <Link className="btn btn-primary btn-full" to="/login" state={{ redirectTo: targetSharePath }}>
              Sign in
            </Link>
            <Link className="btn btn-secondary btn-full" to="/register" state={{ redirectTo: targetSharePath }}>
              Create account
            </Link>
          </div>
        ) : null}

        {status === 'error' ? (
          <div className="modal-actions modal-actions-stacked">
            <Link className="btn btn-primary btn-full" to="/">
              Back to documents
            </Link>
            <Link className="btn btn-ghost btn-full" to="/login">
              Sign in with another account
            </Link>
          </div>
        ) : null}
      </div>
    </div>
  );
}
