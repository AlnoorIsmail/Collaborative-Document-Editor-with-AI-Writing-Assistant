import { useEffect, useMemo, useState } from 'react';

function formatTimestamp(iso) {
  if (!iso) {
    return '';
  }

  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function CommentsSidebar({
  isOpen,
  onClose,
  role,
  comments,
  loading,
  error,
  selection,
  currentUserId,
  onCreateComment,
  onResolveComment,
  onDeleteComment,
  onJumpToCommentContext,
  creating = false,
  busyCommentId = null,
}) {
  const [draft, setDraft] = useState('');

  const canCreateComments = role === 'owner' || role === 'editor' || role === 'commenter';
  const canManageAll = role === 'owner' || role === 'editor';
  const quotedText = useMemo(() => {
    const nextQuotedText = selection?.text?.trim() || '';
    return nextQuotedText;
  }, [selection?.text]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        onClose();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  async function handleSubmit(event) {
    event.preventDefault();
    const normalizedDraft = draft.trim();
    if (!normalizedDraft || !canCreateComments || creating) {
      return;
    }

    const created = await onCreateComment?.({
      body: normalizedDraft,
      quotedText: quotedText || null,
    });

    if (created) {
      setDraft('');
    }
  }

  return (
    <aside
      className={`comments-sidebar ${isOpen ? 'comments-sidebar-open' : 'comments-sidebar-closed'}`}
      aria-hidden={!isOpen}
    >
      <div className="comments-sidebar-header">
        <h2 className="comments-sidebar-title">Comments</h2>
        <button
          type="button"
          className="btn btn-ghost comments-sidebar-close"
          onClick={onClose}
          aria-label="Close comments sidebar"
        >
          Close
        </button>
      </div>

      <div className="comments-sidebar-body">
        {canCreateComments ? (
          <form className="comments-sidebar-composer" onSubmit={handleSubmit}>
            {quotedText ? (
              <div className="comments-quoted-preview">
                <span className="comments-quoted-label">Quoted text</span>
                <button
                  type="button"
                  className="comments-quoted-jump"
                  onClick={() => onJumpToCommentContext?.({ quoted_text: quotedText })}
                >
                  <span className="comments-quoted-text">{quotedText}</span>
                </button>
              </div>
            ) : (
              <div className="comments-sidebar-notice">
                Add a general document comment, or select text first to include it as context.
              </div>
            )}
            <label className="form-label" htmlFor="comments-body">
              New comment
            </label>
            <textarea
              id="comments-body"
              className="input comments-textarea"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Share feedback for this document..."
              disabled={creating}
            />
            <div className="comments-composer-actions">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={creating || !draft.trim()}
              >
                {creating ? 'Posting…' : 'Post comment'}
              </button>
            </div>
          </form>
        ) : (
          <div className="comments-sidebar-notice">
            Your role can read comments, but it cannot create or manage them.
          </div>
        )}

        {error ? (
          <div className="form-error" role="alert">{error}</div>
        ) : null}

        <div className="comments-thread-shell">
          {loading ? (
            <div className="comments-empty">Loading comments…</div>
          ) : comments.length === 0 ? (
            <div className="comments-empty">No comments yet.</div>
          ) : (
            <div className="comments-thread-list">
              {comments.map((comment) => {
                const canDelete =
                  canManageAll || comment.author_user_id === currentUserId;
                const isBusy = busyCommentId === comment.comment_id;

                return (
                  <article
                    key={comment.comment_id}
                    className={`comments-thread-card ${comment.status === 'resolved' ? 'comments-thread-card-resolved' : ''}`}
                  >
                    <div className="comments-thread-top">
                      <div className="comments-thread-meta">
                        <strong>{comment.author?.display_name || 'Collaborator'}</strong>
                        <span>{formatTimestamp(comment.created_at)}</span>
                      </div>
                      <span className={`comments-status-badge comments-status-${comment.status}`}>
                        {comment.status}
                      </span>
                    </div>

                    {comment.quoted_text ? (
                      <button
                        type="button"
                        className="comments-quoted-jump"
                        onClick={() => onJumpToCommentContext?.(comment)}
                      >
                        <span className="comments-quoted-label">Quoted text</span>
                        <span className="comments-quoted-block">
                          {comment.quoted_text}
                        </span>
                      </button>
                    ) : null}

                    <p className="comments-thread-body">{comment.body}</p>

                    {(canManageAll || canDelete) && comment.status !== 'resolved' ? (
                      <div className="comments-thread-actions">
                        {canManageAll ? (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => onResolveComment?.(comment)}
                            disabled={isBusy}
                          >
                            Resolve
                          </button>
                        ) : null}
                        {canDelete ? (
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => onDeleteComment?.(comment)}
                            disabled={isBusy}
                          >
                            Delete
                          </button>
                        ) : null}
                      </div>
                    ) : canDelete ? (
                      <div className="comments-thread-actions">
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => onDeleteComment?.(comment)}
                          disabled={isBusy}
                        >
                          Delete
                        </button>
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
