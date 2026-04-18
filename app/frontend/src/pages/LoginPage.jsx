import { useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { apiFetch, getErrorMessage } from '../api';
import {
  getLoginFieldErrors,
  normalizeEmail,
  validateEmailField,
  validatePasswordField,
} from '../authValidation';
import {
  clearPendingShareLinkToken,
  getPendingShareLinkToken,
} from '../shareLinks';
import { buildPageTitle, usePageTitle } from '../pageTitle';

const INITIAL_TOUCHED = {
  email: false,
  password: false,
};

const INITIAL_ERRORS = {
  email: '',
  password: '',
};

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [touched, setTouched] = useState(INITIAL_TOUCHED);
  const [fieldErrors, setFieldErrors] = useState(INITIAL_ERRORS);
  const [bannerError, setBannerError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  usePageTitle(buildPageTitle('Login'));



  
  function setFieldError(field, value) {
    setFieldErrors((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleEmailChange(event) {
    const nextEmail = event.target.value;
    setEmail(nextEmail);
    setBannerError('');
    setFieldError('email', validateEmailField(nextEmail));
  }

  function handlePasswordChange(event) {
    const nextPassword = event.target.value;
    setPassword(nextPassword);
    setBannerError('');
    setFieldError(
      'password',
      touched.password ? validatePasswordField(nextPassword, { required: true }) : ''
    );
  }

  function handleEmailBlur() {
    setTouched((current) => ({
      ...current,
      email: true,
    }));
    setFieldError('email', validateEmailField(email, { required: true }));
  }

  function handlePasswordBlur() {
    setTouched((current) => ({
      ...current,
      password: true,
    }));
    setFieldError('password', validatePasswordField(password, { required: true }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setBannerError('');

    const nextFieldErrors = getLoginFieldErrors({ email, password });
    setTouched({
      email: true,
      password: true,
    });
    setFieldErrors(nextFieldErrors);

    if (nextFieldErrors.email || nextFieldErrors.password) {
      return;
    }

    setLoading(true);
    try {
      const normalizedEmail = normalizeEmail(email);
      const res = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: normalizedEmail, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const message = getErrorMessage(data, 'Login failed');
        if (message === 'No account exists for this email.') {
          setFieldError('email', message);
          return;
        }

        if (message === 'Incorrect password.') {
          setFieldError('password', message);
          return;
        }

        throw new Error(message);
      }
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      const pendingShareToken = getPendingShareLinkToken();
      const redirectTo =
        location.state?.redirectTo
        || (pendingShareToken ? `/share/${pendingShareToken}` : null);
      clearPendingShareLinkToken();
      navigate(redirectTo || '/');
    } catch (err) {
      setBannerError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const emailErrorId = 'login-email-error';
  const passwordErrorId = 'login-password-error';

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Login</h1>
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {bannerError && <div className="error-banner">{bannerError}</div>}
          <label className="field-label">
            Email
            <input
              className={`field-input ${fieldErrors.email ? 'field-input-error' : ''}`}
              type="email"
              value={email}
              onChange={handleEmailChange}
              onBlur={handleEmailBlur}
              required
              inputMode="email"
              autoFocus
              autoComplete="email"
              aria-invalid={fieldErrors.email ? 'true' : 'false'}
              aria-describedby={emailErrorId}
            />
            <span
              className={`field-help ${fieldErrors.email ? 'field-help-error' : ''}`}
              id={emailErrorId}
              aria-hidden={fieldErrors.email ? 'false' : 'true'}
            >
              {fieldErrors.email || '\u00a0'}
            </span>
          </label>
          <label className="field-label">
            Password
            <input
              className={`field-input ${fieldErrors.password ? 'field-input-error' : ''}`}
              type="password"
              value={password}
              onChange={handlePasswordChange}
              onBlur={handlePasswordBlur}
              required
              autoComplete="current-password"
              aria-invalid={fieldErrors.password ? 'true' : 'false'}
              aria-describedby={passwordErrorId}
            />
            <span
              className={`field-help ${fieldErrors.password ? 'field-help-error' : ''}`}
              id={passwordErrorId}
              aria-hidden={fieldErrors.password ? 'false' : 'true'}
            >
              {fieldErrors.password || '\u00a0'}
            </span>
          </label>
          <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="auth-footer">
          No account? <Link to="/register">Create one</Link>
        </p>
      </div>
    </div>
  );
}
