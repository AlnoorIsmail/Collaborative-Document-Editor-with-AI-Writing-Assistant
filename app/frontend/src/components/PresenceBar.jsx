import { useEffect, useMemo, useRef, useState } from 'react';
import { resolvePresenceColor } from '../presenceColors';

function formatLiveSummary(users, currentUserId) {
  if (!users.length) {
    return 'Live: You';
  }

  if (users.length === 1) {
    const onlyUser = users[0];
    return `Live: ${onlyUser.user_id === currentUserId ? 'You' : onlyUser.display_name}`;
  }

  return `Live: ${users.length} online`;
}

function formatRealtimeStatus(status) {
  if (status === 'connected') {
    return 'Realtime connected';
  }
  if (status === 'connecting') {
    return 'Connecting…';
  }
  if (status === 'reconnecting') {
    return 'Reconnecting…';
  }
  if (status === 'unsupported') {
    return 'Realtime unsupported';
  }
  return 'Realtime offline';
}

export function PresenceSummary({
  users,
  currentUserId,
  realtimeStatus,
  realtimeMessage,
  variant = 'bar',
}) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const showLivePresence = realtimeStatus === 'connected';
  const connectedAndSolo =
    realtimeStatus === 'connected' && users.length <= 1 && !realtimeMessage;
  const liveUsers = useMemo(
    () => users.map((user) => ({
      ...user,
      color: resolvePresenceColor(user.color_token, user.user_id),
      label: user.display_name || 'Collaborator',
      isCurrentUser: user.user_id === currentUserId,
    })),
    [currentUserId, users]
  );
  const hasRealtimeStatus = !connectedAndSolo;
  const hasContent = showLivePresence || hasRealtimeStatus || Boolean(realtimeMessage);

  useEffect(() => {
    if (!showLivePresence) {
      setIsOpen(false);
    }
  }, [showLivePresence]);

  useEffect(() => {
    function handlePointerDown(event) {
      if (!dropdownRef.current?.contains(event.target)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, []);

  if (!hasContent) {
    return null;
  }

  return (
    <div className={`presence-pill-group ${variant === 'inline' ? 'presence-pill-group-inline' : ''}`}>
      {showLivePresence ? (
        <div className="presence-live-dropdown" ref={dropdownRef}>
          <button
            type="button"
            className={`presence-pill presence-pill-primary presence-live-trigger ${variant === 'inline' ? 'presence-pill-inline' : ''}`}
            aria-expanded={isOpen}
            aria-haspopup="list"
            onClick={() => setIsOpen((current) => !current)}
          >
            <span>{formatLiveSummary(users, currentUserId)}</span>
            <span aria-hidden="true" className="presence-live-chevron">▾</span>
          </button>
          {isOpen ? (
            <div className="presence-live-menu" role="list" aria-label="Live collaborators">
              {liveUsers.map((user) => (
                <div key={user.session_id} className="presence-live-item" role="listitem">
                  <span
                    className="presence-live-swatch"
                    style={{ backgroundColor: user.color }}
                    aria-hidden="true"
                  />
                  <span className="presence-live-name" style={{ color: user.color }}>
                    {user.label}
                  </span>
                  {user.isCurrentUser ? (
                    <span className="presence-live-self">You</span>
                  ) : null}
                  {user.typing ? (
                    <span className="presence-live-meta">typing…</span>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      {hasRealtimeStatus ? (
        <span
          className={`presence-pill presence-pill-status presence-pill-status-${realtimeStatus} ${variant === 'inline' ? 'presence-pill-inline' : ''}`}
        >
          {formatRealtimeStatus(realtimeStatus)}
        </span>
      ) : null}
      {realtimeMessage ? (
        <span className={`presence-pill ${variant === 'inline' ? 'presence-pill-inline presence-pill-inline-message' : ''}`}>
          {realtimeMessage}
        </span>
      ) : null}
    </div>
  );
}

export default function PresenceBar({
  users,
  currentUserId,
  realtimeStatus,
  realtimeMessage,
  conflictState,
  onAcceptRemote,
  onKeepLocal,
  showSummary = true,
}) {
  return (
    <>
      {showSummary ? (
        <div className="presence-bar">
          <PresenceSummary
            users={users}
            currentUserId={currentUserId}
            realtimeStatus={realtimeStatus}
            realtimeMessage={realtimeMessage}
          />
        </div>
      ) : null}

      {conflictState ? (
        <div className="conflict-banner">
          <div className="conflict-banner-copy">
            <strong>Remote changes need review.</strong>
            <span>{conflictState.message}</span>
          </div>
          <div className="conflict-banner-actions">
            <button type="button" className="btn btn-secondary" onClick={onAcceptRemote}>
              Use remote version
            </button>
            <button type="button" className="btn btn-primary" onClick={onKeepLocal}>
              Keep my draft
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
