const OFFLINE_DRAFT_PREFIX = 'offline_document_draft_';

export function buildRealtimeSocketUrl({
  realtimeUrl,
  documentId,
  sessionId,
  sessionToken,
  accessToken,
}) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const fallbackBase = `/v1/documents/${documentId}/sessions/${sessionId}/ws`;

  let base = fallbackBase;
  if (typeof realtimeUrl === 'string' && realtimeUrl.includes('/sessions/')) {
    base = realtimeUrl;
  }

  const url = new URL(base, `${protocol}//${host}`);
  url.searchParams.set('session_token', sessionToken);
  url.searchParams.set('access_token', accessToken);
  return url.toString();
}

function draftStorageKey(documentId) {
  return `${OFFLINE_DRAFT_PREFIX}${documentId}`;
}

export function readOfflineDraft(documentId) {
  const raw = sessionStorage.getItem(draftStorageKey(documentId));
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function writeOfflineDraft(documentId, draft) {
  sessionStorage.setItem(draftStorageKey(documentId), JSON.stringify(draft));
}

export function clearOfflineDraft(documentId) {
  sessionStorage.removeItem(draftStorageKey(documentId));
}
