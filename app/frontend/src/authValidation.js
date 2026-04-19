const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizeEmail(email) {
  return email.trim().toLowerCase();
}

export function isValidEmail(email) {
  return EMAIL_PATTERN.test(normalizeEmail(email));
}

export function validateEmailField(email, { required = false } = {}) {
  const normalizedEmail = normalizeEmail(email);

  if (!normalizedEmail) {
    return required ? 'Email is required.' : '';
  }

  if (!isValidEmail(normalizedEmail)) {
    return 'Enter a valid email address.';
  }

  return '';
}

export function validatePasswordField(password, { required = false, minLength = 0 } = {}) {
  if (!password) {
    return required ? 'Password is required.' : '';
  }

  if (minLength > 0 && password.length < minLength) {
    return `Password must be at least ${minLength} characters.`;
  }

  return '';
}

const USERNAME_PATTERN = /^[a-zA-Z0-9_]+$/;

export function validateNameField(name, { required = false } = {}) {
  if (!name.trim()) {
    return required ? 'Name is required.' : '';
  }

  return '';
}

export function validateUsernameField(username, { required = false } = {}) {
  const trimmed = username.trim();

  if (!trimmed) {
    return required ? 'Username is required.' : '';
  }

  if (trimmed.length < 3) {
    return 'Username must be at least 3 characters.';
  }

  if (!USERNAME_PATTERN.test(trimmed)) {
    return 'Username can only contain letters, numbers, and underscores.';
  }

  return '';
}

export function getLoginFieldErrors({ email, password }) {
  return {
    email: validateEmailField(email, { required: true }),
    password: validatePasswordField(password, { required: true }),
  };
}

export function getRegisterFieldErrors({ name, email, password }) {
  return {
    name: validateUsernameField(name, { required: true }),
    email: validateEmailField(email, { required: true }),
    password: validatePasswordField(password, { required: true, minLength: 8 }),
  };
}
