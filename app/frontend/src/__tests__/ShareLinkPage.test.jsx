import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ShareLinkPage from '../pages/ShareLinkPage';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiJSON: vi.fn(),
  };
});

function renderShareLinkPage(initialEntry = '/share/test-token') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/share/:token" element={<ShareLinkPage />} />
        <Route path="/documents/:id" element={<div>Document opened</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ShareLinkPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    document.title = 'frontend';
  });

  it('prompts for sign in when opening a share link while signed out', async () => {
    renderShareLinkPage();

    await screen.findByText('Sign in to redeem this share link and open the document.');

    expect(document.title).toBe('Open shared document • CollabDocs');
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument();
    expect(localStorage.getItem('pending_share_link_token')).toBe('test-token');
  });

  it('redeems the share link and redirects to the document when signed in', async () => {
    localStorage.setItem('access_token', 'token');
    api.apiJSON.mockResolvedValue({
      document_id: 'doc_1',
      role: 'viewer',
      access_granted: true,
    });

    renderShareLinkPage();

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/share-links/test-token/redeem',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    await screen.findByText('Document opened');
  });
});
