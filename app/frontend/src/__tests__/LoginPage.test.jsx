import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import LoginPage from '../pages/LoginPage';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

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

  it('shows inline email feedback while typing an invalid address', async () => {
    renderLoginPage();
    const emailInput = screen.getByLabelText(/email/i);

    fireEvent.change(emailInput, { target: { value: 'user-at-example' } });

    await waitFor(() =>
      expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    );
    expect(emailInput).toHaveAttribute('aria-invalid', 'true');
    expect(api.apiFetch).not.toHaveBeenCalled();
  });

  it('shows inline password feedback on submit when password is empty', async () => {
    renderLoginPage();
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    fireEvent.change(emailInput, { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText('Password is required.')).toBeInTheDocument()
    );
    expect(passwordInput).toHaveAttribute('aria-invalid', 'true');
    expect(api.apiFetch).not.toHaveBeenCalled();
  });

  it('maps unknown-account responses to the email field', async () => {
    api.apiFetch.mockResolvedValue({
      ok: false,
      json: async () => ({ message: 'No account exists for this email.' }),
    });
    renderLoginPage();
    const emailInput = screen.getByLabelText(/email/i);

    fireEvent.change(emailInput, { target: { value: 'missing@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
    fireEvent.submit(document.querySelector('form'));

    await waitFor(() =>
      expect(screen.getByText('No account exists for this email.')).toBeInTheDocument()
    );
    expect(emailInput).toHaveAttribute('aria-invalid', 'true');
  });

  it('maps wrong-password responses to the password field', async () => {
    api.apiFetch.mockResolvedValue({
      ok: false,
      json: async () => ({ message: 'Incorrect password.' }),
    });
    renderLoginPage();
    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(screen.getByText('Incorrect password.')).toBeInTheDocument()
    );
    expect(passwordInput).toHaveAttribute('aria-invalid', 'true');
  });

  it('keeps generic failures in the top error banner', async () => {
    api.apiFetch.mockRejectedValue(new Error('Network error'));
    renderLoginPage();

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText('Network error')).toBeInTheDocument()
    );
    expect(screen.getByText('Network error')).toHaveClass('error-banner');
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
