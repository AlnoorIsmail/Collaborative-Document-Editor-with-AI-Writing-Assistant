export const PENDING_SHARE_LINK_TOKEN_KEY = 'pending_share_link_token';

export function buildShareLinkUrl(token) {
  const path = `/share/${token}`;
  if (typeof window === 'undefined' || !window.location?.origin) {
    return path;
  }
  return `${window.location.origin}${path}`;
}

export function getPendingShareLinkToken() {
  return localStorage.getItem(PENDING_SHARE_LINK_TOKEN_KEY);
}

export function storePendingShareLinkToken(token) {
  localStorage.setItem(PENDING_SHARE_LINK_TOKEN_KEY, token);
}

export function clearPendingShareLinkToken() {
  localStorage.removeItem(PENDING_SHARE_LINK_TOKEN_KEY);
}
