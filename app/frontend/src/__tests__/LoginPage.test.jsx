import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import LoginPage from '../pages/LoginPage';
import * as api from '../api';

vi.mock('../api', () => ({
  apiFetch: vi.fn(),
}));

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders email and password fields', () => {
    renderLoginPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('shows an error when submitting with empty fields', async () => {
    api.apiFetch.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Login failed' }),
    });
    renderLoginPage();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => expect(screen.getByText('Login failed')).toBeInTheDocument());
  });

  it('stores access_token in localStorage on successful login', async () => {
    api.apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'test-token', refresh_token: 'ref-token' }),
    });
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => expect(localStorage.getItem('access_token')).toBe('test-token'));
  });
});
