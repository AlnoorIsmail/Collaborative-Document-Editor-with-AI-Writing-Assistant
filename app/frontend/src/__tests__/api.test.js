import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, getErrorMessage } from '../api';

describe('apiFetch auth refresh behavior', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not attempt token refresh for login failures', async () => {
    localStorage.setItem('access_token', 'stale-access');
    localStorage.setItem('refresh_token', 'stale-refresh');

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ message: 'Incorrect password.' }),
    });

    vi.stubGlobal('fetch', fetchMock);

    const response = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: 'alice@example.com', password: 'wrong-password' }),
    });

    expect(response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      '/v1/auth/login',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('prefers backend message fields when building errors', () => {
    expect(getErrorMessage({ message: 'Incorrect password.' }, 'Login failed')).toBe(
      'Incorrect password.'
    );
    expect(getErrorMessage({ detail: 'Fallback detail' }, 'Login failed')).toBe(
      'Fallback detail'
    );
    expect(getErrorMessage(null, 'Login failed')).toBe('Login failed');
  });
});
