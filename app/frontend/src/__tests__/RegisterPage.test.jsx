import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import RegisterPage from '../pages/RegisterPage';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

function renderRegisterPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>
  );
}

function renderRegisterPageWithRoutes() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    document.title = 'frontend';
  });

  it('renders name, email, and password fields', () => {
    renderRegisterPage();
    expect(screen.getByLabelText(/^username$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(document.title).toBe('Create account • CollabDocs');
  });

  it('shows inline email feedback while typing an invalid address', async () => {
    renderRegisterPage();
    const emailInput = screen.getByLabelText(/email/i);

    fireEvent.change(emailInput, { target: { value: 'alice-at-example' } });

    await waitFor(() =>
      expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    );
    expect(emailInput).toHaveAttribute('aria-invalid', 'true');
    expect(api.apiFetch).not.toHaveBeenCalled();
  });

  it('shows inline required-field feedback on submit', async () => {
    renderRegisterPage();
    const nameInput = screen.getByLabelText(/^username$/i);
    const passwordInput = screen.getByLabelText(/password/i);

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'alice@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText('Name is required.')).toBeInTheDocument();
      expect(screen.getByText('Password is required.')).toBeInTheDocument();
    });
    expect(nameInput).toHaveAttribute('aria-invalid', 'true');
    expect(passwordInput).toHaveAttribute('aria-invalid', 'true');
    expect(api.apiFetch).not.toHaveBeenCalled();
  });

  it('submits with display_name field, not name', async () => {
    api.apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'tok', refresh_token: 'ref' }),
    });
    renderRegisterPage();
    fireEvent.change(screen.getByLabelText(/^username$/i), { target: { value: 'Alice' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'alice@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    await waitFor(() => {
      expect(api.apiFetch).toHaveBeenCalledOnce();
      const [path, options] = api.apiFetch.mock.calls[0];
      const body = JSON.parse(options.body);
      expect(path).toBe('/auth/register');
      expect(body).toHaveProperty('display_name', 'Alice');
      expect(body).not.toHaveProperty('name');
    });
  });

  it('maps duplicate-email responses to the email field', async () => {
    api.apiFetch.mockResolvedValue({
      ok: false,
      json: async () => ({ message: 'A user with this email already exists.' }),
    });
    renderRegisterPage();
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(screen.getByLabelText(/^username$/i), { target: { value: 'Alice' } });
    fireEvent.change(emailInput, { target: { value: 'alice@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByText('A user with this email already exists.')).toBeInTheDocument()
    );
    expect(emailInput).toHaveAttribute('aria-invalid', 'true');
  });

  it('opens sign in on the first click even when validation appears on blur', async () => {
    const user = userEvent.setup();
    renderRegisterPageWithRoutes();

    await user.click(screen.getByLabelText(/^username$/i));
    await user.click(screen.getByRole('link', { name: /sign in/i }));

    await screen.findByText('Login page');
  });
});
