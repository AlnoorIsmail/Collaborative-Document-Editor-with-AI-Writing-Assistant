export const PRESENCE_COLORS = {
  'presence-0': '#4f46e5',
  'presence-1': '#db2777',
  'presence-2': '#0f766e',
  'presence-3': '#ea580c',
  'presence-4': '#2563eb',
  'presence-5': '#7c3aed',
  'presence-6': '#b45309',
  'presence-7': '#059669',
};

export function resolvePresenceColor(colorToken, userId) {
  if (colorToken && PRESENCE_COLORS[colorToken]) {
    return PRESENCE_COLORS[colorToken];
  }

  const fallbackKeys = Object.keys(PRESENCE_COLORS);
  return fallbackKeys.length
    ? PRESENCE_COLORS[fallbackKeys[Math.abs(Number(userId) || 0) % fallbackKeys.length]]
    : '#4f46e5';
}
