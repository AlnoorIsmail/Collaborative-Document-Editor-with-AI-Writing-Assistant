export const DEFAULT_DOCUMENT_TITLE = 'Untitled Document';

function normalizeTitle(title) {
  const normalized = `${title ?? ''}`.replace(/\s+/g, ' ').trim();
  return normalized || DEFAULT_DOCUMENT_TITLE;
}

export function buildUniqueDisplayTitles(documents) {
  const nextCounts = new Map();
  const titleMap = new Map();

  [...documents]
    .sort((left, right) => (left.document_id ?? 0) - (right.document_id ?? 0))
    .forEach((document) => {
      const baseTitle = normalizeTitle(document.title);
      const key = baseTitle.toLocaleLowerCase();
      const nextIndex = nextCounts.get(key) ?? 0;
      const displayTitle = nextIndex === 0 ? baseTitle : `${baseTitle} ${nextIndex}`;

      titleMap.set(document.document_id, displayTitle);
      nextCounts.set(key, nextIndex + 1);
    });

  return titleMap;
}

export function getRoleLabel(role) {
  if (!role) {
    return 'Document';
  }

  return role.charAt(0).toUpperCase() + role.slice(1);
}
