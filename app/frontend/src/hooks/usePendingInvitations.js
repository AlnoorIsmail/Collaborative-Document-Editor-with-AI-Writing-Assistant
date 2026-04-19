import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiJSON } from '../api';

const INVITATION_POLL_INTERVAL_MS = 10_000;

function mergeUniqueInvitations(currentQueue, nextInvitations) {
  const queuedIds = new Set(currentQueue.map((invitation) => invitation.invitation_id));
  return [
    ...currentQueue,
    ...nextInvitations.filter((invitation) => !queuedIds.has(invitation.invitation_id)),
  ];
}

export default function usePendingInvitations({ enabled = true } = {}) {
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState('');
  const [isPageVisible, setIsPageVisible] = useState(
    () => typeof document === 'undefined' || !document.hidden
  );
  const [notificationQueue, setNotificationQueue] = useState([]);

  const initializedRef = useRef(false);
  const knownInvitationIdsRef = useRef(new Set());
  const invitationsRef = useRef([]);
  const refreshInFlightRef = useRef(false);

  const syncInvitations = useCallback((nextInvitations) => {
    invitationsRef.current = nextInvitations;
    setInvitations(nextInvitations);
  }, []);

  const refreshInvitations = useCallback(
    async ({ showLoading = false } = {}) => {
      if (!enabled || refreshInFlightRef.current) {
        return invitationsRef.current;
      }

      refreshInFlightRef.current = true;
      if (showLoading) {
        setLoading(true);
      }

      try {
        const nextInvitations = await apiJSON('/invitations');
        syncInvitations(nextInvitations);
        setError('');

        if (!initializedRef.current) {
          knownInvitationIdsRef.current = new Set(
            nextInvitations.map((invitation) => invitation.invitation_id)
          );
          initializedRef.current = true;
          return nextInvitations;
        }

        const newInvitations = nextInvitations.filter(
          (invitation) => !knownInvitationIdsRef.current.has(invitation.invitation_id)
        );
        if (newInvitations.length > 0) {
          setNotificationQueue((currentQueue) =>
            mergeUniqueInvitations(currentQueue, newInvitations)
          );
        }

        nextInvitations.forEach((invitation) => {
          knownInvitationIdsRef.current.add(invitation.invitation_id);
        });

        return nextInvitations;
      } catch (nextError) {
        if (!initializedRef.current || showLoading) {
          setError(nextError.message || 'Failed to load invitations.');
        }
        throw nextError;
      } finally {
        refreshInFlightRef.current = false;
        setLoading(false);
      }
    },
    [enabled, syncInvitations]
  );

  const dismissNotification = useCallback((invitationId) => {
    setNotificationQueue((currentQueue) => {
      if (!currentQueue.length) {
        return currentQueue;
      }

      if (!invitationId) {
        return currentQueue.slice(1);
      }

      return currentQueue.filter(
        (invitation) => invitation.invitation_id !== invitationId
      );
    });
  }, []);

  const removeInvitation = useCallback(
    (invitationId) => {
      syncInvitations(
        invitationsRef.current.filter(
          (invitation) => invitation.invitation_id !== invitationId
        )
      );
      dismissNotification(invitationId);
    },
    [dismissNotification, syncInvitations]
  );

  const acceptInvitation = useCallback(
    async (invitationId) => {
      setError('');
      const response = await apiJSON(`/invitations/${invitationId}/accept`, {
        method: 'POST',
      });
      removeInvitation(invitationId);
      return response;
    },
    [removeInvitation]
  );

  const declineInvitation = useCallback(
    async (invitationId) => {
      setError('');
      const response = await apiJSON(`/invitations/${invitationId}/decline`, {
        method: 'POST',
      });
      removeInvitation(invitationId);
      return response;
    },
    [removeInvitation]
  );

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      syncInvitations([]);
      setNotificationQueue([]);
      return undefined;
    }

    void refreshInvitations({ showLoading: !initializedRef.current });
    return undefined;
  }, [enabled, refreshInvitations, syncInvitations]);

  useEffect(() => {
    function handleVisibilityChange() {
      setIsPageVisible(!document.hidden);
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () =>
      document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  useEffect(() => {
    if (!enabled || !isPageVisible || !initializedRef.current) {
      return undefined;
    }

    void refreshInvitations();
    return undefined;
  }, [enabled, isPageVisible, refreshInvitations]);

  useEffect(() => {
    if (!enabled || !isPageVisible) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshInvitations();
    }, INVITATION_POLL_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [enabled, isPageVisible, refreshInvitations]);

  return useMemo(
    () => ({
      invitations,
      loading,
      error,
      clearError: () => setError(''),
      activeNotification: notificationQueue[0] ?? null,
      dismissNotification,
      refreshInvitations,
      acceptInvitation,
      declineInvitation,
    }),
    [
      acceptInvitation,
      declineInvitation,
      dismissNotification,
      error,
      invitations,
      loading,
      notificationQueue,
      refreshInvitations,
    ]
  );
}
