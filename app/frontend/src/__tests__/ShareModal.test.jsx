import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
      username: 'owner',
      display_name: 'Owner',
    },
    collaborators: [
      {
        permission_id: 'perm_1',
        user: {
          user_id: 'usr_2',
          email: 'viewer@example.com',
          username: 'viewer',
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
    expect(
      screen.getByText('Shared links always require sign-in before access is granted.')
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Create link' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/share-links',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    const [, requestOptions] = api.apiJSON.mock.calls.find(([path]) => path === '/share-links');
    expect(JSON.parse(requestOptions.body)).toMatchObject({
      document_id: '1',
      role: 'viewer',
      require_sign_in: true,
    });
    expect(typeof JSON.parse(requestOptions.body).expires_at).toBe('string');

    expect(screen.getByText(/\/share\/new-token/i)).toBeInTheDocument();
  });

  it('validates the invite email or username inline before sending an invitation', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1/sharing' && !options) {
        return Promise.resolve(buildOverview());
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    render(<ShareModal docId="1" onClose={() => {}} />);

    await screen.findByText('Invite by email or username');
    fireEvent.change(screen.getByPlaceholderText('Add by email address or username'), {
      target: { value: 'bad user' },
    });

    expect(screen.getByText('Enter a valid email address or username.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Invite' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

    expect(api.apiJSON).not.toHaveBeenCalledWith(
      '/documents/1/invitations',
      expect.anything()
    );
  });

  it('shows a field error when the invite email has no account in the system', async () => {
    const user = userEvent.setup();
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1/sharing' && !options) {
        return Promise.resolve(buildOverview());
      }

      if (path === '/documents/1/invitations') {
        return Promise.reject(new Error('No account exists for this email.'));
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    render(<ShareModal docId="1" onClose={() => {}} />);

    await screen.findByText('Invite by email or username');
    fireEvent.change(screen.getByPlaceholderText('Add by email address or username'), {
      target: { value: 'missing@example.com' },
    });
    await user.click(screen.getByRole('button', { name: 'Invite' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/invitations',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    await screen.findByText('No account exists for this email.');
    expect(screen.queryByText('Failed to send invitation.')).not.toBeInTheDocument();
  });

  it('can invite a registered user by username', async () => {
    const user = userEvent.setup();
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1/sharing' && !options) {
        return Promise.resolve(buildOverview());
      }

      if (path === '/documents/1/invitations') {
        return Promise.resolve({
          invitation_id: 'inv_2',
          document_id: 'doc_1',
          invited_email: 'viewer@example.com',
          role: 'editor',
          status: 'pending',
          expires_at: '2026-01-08T00:00:00Z',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    render(<ShareModal docId="1" onClose={() => {}} />);

    await screen.findByText('Invite by email or username');
    await user.type(screen.getByPlaceholderText('Add by email address or username'), 'viewer');
    await user.click(screen.getByRole('button', { name: 'Invite' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/invitations',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            invitee: 'viewer',
            role: 'editor',
          }),
        })
      );
    });

    expect(screen.getByText('Invitation sent to viewer@example.com.')).toBeInTheDocument();
  });
});
