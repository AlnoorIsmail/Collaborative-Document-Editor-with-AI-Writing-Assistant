import { getRoleLabel } from '../documentDisplay';

export default function InvitationNotificationBanner({
  invitation,
  onReview,
  onDismiss,
}) {
  if (!invitation) {
    return null;
  }

  const inviterName =
    invitation.inviter.display_name || invitation.inviter.username || invitation.inviter.email;

  return (
    <div className="invite-notification-banner" role="status" aria-live="polite">
      <div className="invite-notification-copy">
        <strong>{inviterName}</strong>
        {' shared '}
        <strong>&ldquo;{invitation.document_title}&rdquo;</strong>
        {' with you as '}
        <strong>{getRoleLabel(invitation.role)}</strong>
        .
      </div>
      <div className="invite-notification-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onReview?.(invitation)}
        >
          Review invites
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => onDismiss?.(invitation.invitation_id)}
          aria-label="Dismiss invitation notification"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
