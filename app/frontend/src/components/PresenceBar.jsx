function formatNames(users, currentUserId) {
  if (!users.length) {
    return 'Only you are here right now.';
  }

  return users
    .map((user) => (user.user_id === currentUserId ? 'You' : user.display_name))
    .join(', ');
}

export default function PresenceBar({
  users,
  currentUserId,
  realtimeStatus,
  realtimeMessage,
  conflictState,
  onAcceptRemote,
  onKeepLocal,
}) {
  const showLivePresence = realtimeStatus === 'connected';
  const connectedAndSolo =
    realtimeStatus === 'connected' && users.length <= 1 && !realtimeMessage;
  const typingUsers = users.filter(
    (user) => user.typing && user.user_id !== currentUserId
  );

  return (
    <>
      <div className="presence-bar">
        <div className="presence-pill-group">
          {showLivePresence ? (
            <span className="presence-pill presence-pill-primary">
              Live: {formatNames(users, currentUserId)}
            </span>
          ) : null}
          {!connectedAndSolo ? (
            <span className={`presence-pill presence-pill-status presence-pill-status-${realtimeStatus}`}>
              {realtimeStatus === 'connected'
                ? 'Realtime connected'
                : realtimeStatus === 'connecting'
                  ? 'Connecting…'
                  : realtimeStatus === 'reconnecting'
                    ? 'Reconnecting…'
                    : realtimeStatus === 'unsupported'
                      ? 'Realtime unsupported'
                      : 'Realtime offline'}
            </span>
          ) : null}
          {typingUsers.length ? (
            <span className="presence-pill">
              {typingUsers.map((user) => user.display_name).join(', ')} typing…
            </span>
          ) : null}
          {realtimeMessage ? (
            <span className="presence-pill">{realtimeMessage}</span>
          ) : null}
        </div>
      </div>

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
