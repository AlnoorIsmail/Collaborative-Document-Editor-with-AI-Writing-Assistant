import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ShareModal from '../components/ShareModal';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiJSON: vi.fn(),
  };
});

function buildOverview() {
  return {
    document_id: 'doc_1',
    owner: {
      user_id: 'usr_1',
      email: 'owner@example.com',
      display_name: 'Owner',
    },
    collaborators: [
      {
        permission_id: 'perm_1',
        user: {
          user_id: 'usr_2',
          email: 'viewer@example.com',
          display_name: 'Viewer',
        },
        role: 'viewer',
        ai_allowed: false,
        granted_at: '2026-01-01T00:00:00Z',
      },
    ],
    invitations: [
      {
        invitation_id: 'inv_1',
        invited_email: 'pending@example.com',
        role: 'editor',
        status: 'pending',
        created_at: '2026-01-01T00:00:00Z',
        expires_at: '2026-01-08T00:00:00Z',
      },
    ],
    share_links: [
      {
        link_id: 'link_1',
        token: 'abc123',
        role: 'viewer',
        require_sign_in: true,
        revoked: false,
        created_at: '2026-01-01T00:00:00Z',
        expires_at: '2026-01-08T00:00:00Z',
      },
    ],
  };
}

describe('ShareModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the sharing overview and can revoke collaborator access', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1/sharing' && !options) {
        return Promise.resolve(buildOverview());
      }

      if (path === '/documents/1/permissions/perm_1') {
        return Promise.resolve(null);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    render(<ShareModal docId="1" onClose={() => {}} />);

    await screen.findByText('Current access');
    expect(screen.getByText('viewer@example.com')).toBeInTheDocument();
    expect(screen.getByText('pending@example.com')).toBeInTheDocument();
    expect(screen.getByText(/\/share\/abc123/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/permissions/perm_1',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  it('creates a new share link and shows the generated URL', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1/sharing' && !options) {
        return Promise.resolve(buildOverview());
      }

      if (path === '/share-links') {
        return Promise.resolve({
          link_id: 'link_2',
          document_id: 'doc_1',
          token: 'new-token',
          role: 'viewer',
          require_sign_in: true,
          expires_at: '2026-01-08T00:00:00Z',
          revoked: false,
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    render(<ShareModal docId="1" onClose={() => {}} />);

    await screen.findByText('Share link');
    fireEvent.click(screen.getByRole('button', { name: 'Create link' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/share-links',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    expect(screen.getByText(/\/share\/new-token/i)).toBeInTheDocument();
  });
});
