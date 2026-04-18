const BASE = '/v1';
const AUTH_REFRESH_EXEMPT_PATHS = new Set([
  '/auth/login',
  '/auth/register',
  '/auth/refresh',
]);

// Shared refresh promise so concurrent 401s only fire one refresh request
let refreshPromise = null;

async function doRefresh() {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) throw new Error('No refresh token');

  const res = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) throw new Error('Token refresh failed');

  const data = await res.json();
  localStorage.setItem('access_token', data.access_token);
  if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
  return data.access_token;
}

function clearAuth() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.location.href = '/login';
}

function buildHeaders(token, extra = {}) {
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

function shouldAttemptRefresh(path, token) {
  return Boolean(token) && !AUTH_REFRESH_EXEMPT_PATHS.has(path);
}

export function getErrorMessage(errorData, fallback) {
  if (errorData && typeof errorData === 'object') {
    return errorData.message || errorData.detail || fallback;
  }

  return fallback;
}

export async function apiFetch(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options;
  const token = localStorage.getItem('access_token');

  let res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: buildHeaders(token, extraHeaders),
  });

  if (res.status !== 401 || !shouldAttemptRefresh(path, token)) return res;

  // Attempt token refresh (deduplicated)
  try {
    if (!refreshPromise) {
      refreshPromise = doRefresh().finally(() => { refreshPromise = null; });
    }
    const newToken = await refreshPromise;
    res = await fetch(`${BASE}${path}`, {
      ...rest,
      headers: buildHeaders(newToken, extraHeaders),
    });
    return res;
  } catch {
    clearAuth();
    throw new Error('Session expired');
  }
}

export async function apiJSON(path, options = {}) {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    let errData;
    try { errData = await res.json(); } catch { errData = { detail: res.statusText }; }
    const err = new Error(getErrorMessage(errData, `HTTP ${res.status}`));
    err.status = res.status;
    err.data = errData;
    throw err;
  }
  return res.json();
}
