import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiFetch, getErrorMessage } from '../api';
import {
  getRegisterFieldErrors,
  normalizeEmail,
  validateEmailField,
  validateNameField,
  validatePasswordField,
} from '../authValidation';

const INITIAL_TOUCHED = {
  name: false,
  email: false,
  password: false,
};

const INITIAL_ERRORS = {
  name: '',
  email: '',
  password: '',
};

export default function RegisterPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [touched, setTouched] = useState(INITIAL_TOUCHED);
  const [fieldErrors, setFieldErrors] = useState(INITIAL_ERRORS);
  const [bannerError, setBannerError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  function setFieldError(field, value) {
    setFieldErrors((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleNameChange(event) {
    const nextName = event.target.value;
    setName(nextName);
    setBannerError('');
    setFieldError(
      'name',
      touched.name ? validateNameField(nextName, { required: true }) : ''
    );
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
      touched.password
        ? validatePasswordField(nextPassword, { required: true, minLength: 8 })
        : ''
    );
  }

  function markTouched(field) {
    setTouched((current) => ({
      ...current,
      [field]: true,
    }));
  }

  function handleNameBlur() {
    markTouched('name');
    setFieldError('name', validateNameField(name, { required: true }));
  }

  function handleEmailBlur() {
    markTouched('email');
    setFieldError('email', validateEmailField(email, { required: true }));
  }

  function handlePasswordBlur() {
    markTouched('password');
    setFieldError(
      'password',
      validatePasswordField(password, { required: true, minLength: 8 })
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setBannerError('');

    const nextFieldErrors = getRegisterFieldErrors({ name, email, password });
    setTouched({
      name: true,
      email: true,
      password: true,
    });
    setFieldErrors(nextFieldErrors);

    if (nextFieldErrors.name || nextFieldErrors.email || nextFieldErrors.password) {
      return;
    }

    setLoading(true);
    try {
      const normalizedEmail = normalizeEmail(email);
      const res = await apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          display_name: name.trim(),
          email: normalizedEmail,
          password,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const message = getErrorMessage(data, 'Registration failed');
        if (message === 'A user with this email already exists.') {
          setFieldError('email', message);
          return;
        }

        throw new Error(message);
      }
      const data = await res.json();
      if (data.access_token) {
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        navigate('/');
      } else {
        navigate('/login');
      }
    } catch (err) {
      setBannerError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const nameErrorId = fieldErrors.name ? 'register-name-error' : undefined;
  const emailErrorId = fieldErrors.email ? 'register-email-error' : undefined;
  const passwordErrorId = fieldErrors.password ? 'register-password-error' : undefined;

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Create account</h1>
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {bannerError && <div className="error-banner">{bannerError}</div>}
          <label className="field-label">
            Name
            <input
              className={`field-input ${fieldErrors.name ? 'field-input-error' : ''}`}
              type="text"
              value={name}
              onChange={handleNameChange}
              onBlur={handleNameBlur}
              required
              autoFocus
              autoComplete="name"
              aria-invalid={fieldErrors.name ? 'true' : 'false'}
              aria-describedby={nameErrorId}
            />
            {fieldErrors.name ? (
              <span className="field-help field-help-error" id={nameErrorId}>
                {fieldErrors.name}
              </span>
            ) : null}
          </label>
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
              autoComplete="email"
              aria-invalid={fieldErrors.email ? 'true' : 'false'}
              aria-describedby={emailErrorId}
            />
            {fieldErrors.email ? (
              <span className="field-help field-help-error" id={emailErrorId}>
                {fieldErrors.email}
              </span>
            ) : null}
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
              minLength={8}
              autoComplete="new-password"
              aria-invalid={fieldErrors.password ? 'true' : 'false'}
              aria-describedby={passwordErrorId}
            />
            {fieldErrors.password ? (
              <span className="field-help field-help-error" id={passwordErrorId}>
                {fieldErrors.password}
              </span>
            ) : null}
          </label>
          <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
