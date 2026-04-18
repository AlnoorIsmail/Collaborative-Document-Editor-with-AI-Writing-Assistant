import { useEffect } from 'react';
import { DEFAULT_DOCUMENT_TITLE } from './documentDisplay';

export const APP_NAME = 'CollabDocs';

export function buildPageTitle(label) {
  const normalizedLabel = `${label ?? ''}`.replace(/\s+/g, ' ').trim();
  return normalizedLabel ? `${normalizedLabel} • ${APP_NAME}` : APP_NAME;
}

export function buildDocumentPageTitle(title) {
  const normalizedTitle = `${title ?? ''}`.replace(/\s+/g, ' ').trim();
  return buildPageTitle(normalizedTitle || DEFAULT_DOCUMENT_TITLE);
}

export function usePageTitle(title) {
  useEffect(() => {
    document.title = title;
  }, [title]);
}
