import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DocumentsPage from '../pages/DocumentsPage';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiJSON: vi.fn(),
  };
});

function renderDocumentsPage() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<div>Opened document</div>} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('DocumentsPage dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    document.title = 'frontend';
  });

  it('renders documents as cards with previews, labels, and distinct fallback titles', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents' && !options) {
        return Promise.resolve([
          {
            document_id: 5,
            title: '',
            preview_text: '',
            role: 'owner',
            owner: { display_name: 'You' },
            created_at: '2026-04-01T00:00:00Z',
            updated_at: '2026-04-10T00:00:00Z',
          },
          {
            document_id: 8,
            title: '',
            preview_text: 'Second untitled preview',
            role: 'editor',
            owner: { display_name: 'Afsah' },
            created_at: '2026-04-02T00:00:00Z',
            updated_at: '2026-04-09T00:00:00Z',
          },
          {
            document_id: 9,
            title: 'Project Notes',
            preview_text: 'Sprint goals and launch checklist',
            role: 'viewer',
            owner: { display_name: 'Anagha' },
            created_at: '2026-04-03T00:00:00Z',
            updated_at: '2026-04-08T00:00:00Z',
          },
        ]);
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          name: 'Owner',
          email: 'owner@example.com',
        });
      }

      if (path === '/invitations') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    const { container } = renderDocumentsPage();

    await screen.findByText('Project Notes');

    expect(document.title).toBe('CollabDocs');
    expect(screen.getByRole('list', { name: /document dashboard/i })).toHaveClass('docs-grid');
    expect(container.querySelectorAll('.doc-card')).toHaveLength(3);
    expect(screen.getByText('Untitled Document')).toBeInTheDocument();
    expect(screen.getByText('Untitled Document 1')).toBeInTheDocument();
    expect(screen.getByText('Empty document')).toBeInTheDocument();
    expect(screen.getByText('Owned by you')).toBeInTheDocument();
    expect(screen.getByText('Editor')).toBeInTheDocument();
    expect(screen.getByText('Owner: Afsah')).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: /more actions for untitled document/i })
    );

    expect(screen.getByRole('button', { name: 'Rename' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Share' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  it('creates new documents through the backend fallback-title flow', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents' && !options) {
        return Promise.resolve([]);
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          name: 'Owner',
          email: 'owner@example.com',
        });
      }

      if (path === '/invitations') {
        return Promise.resolve([]);
      }

      if (path === '/documents' && options?.method === 'POST') {
        return Promise.resolve({
          document_id: 42,
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderDocumentsPage();

    await screen.findByText('No documents yet.');
    fireEvent.click(screen.getByRole('button', { name: /create your first document/i }));

    await screen.findByText('Opened document');

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ initial_content: '' }),
        })
      );
    });
  });

  it('renders pending invitations and accepts them into the document list', async () => {
    let documentFetchCount = 0;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents' && !options) {
        documentFetchCount += 1;
        return Promise.resolve(
          documentFetchCount === 1
            ? []
            : [
                {
                  document_id: 9,
                  title: 'Shared Draft',
                  preview_text: 'Welcome to the shared draft',
                  role: 'editor',
                  owner: { display_name: 'Owner' },
                  created_at: '2026-04-01T00:00:00Z',
                  updated_at: '2026-04-10T00:00:00Z',
                },
              ]
        );
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          display_name: 'Recipient',
          email: 'recipient@example.com',
        });
      }

      if (path === '/invitations' && !options) {
        return Promise.resolve([
          {
            invitation_id: 'inv_1',
            document_id: 'doc_9',
            document_title: 'Shared Draft',
            role: 'editor',
            invited_email: 'recipient@example.com',
            inviter: {
              user_id: 'usr_1',
              email: 'owner@example.com',
              username: 'owner',
              display_name: 'Owner',
            },
            created_at: '2026-04-19T12:00:00Z',
            expires_at: '2026-04-21T12:00:00Z',
          },
        ]);
      }

      if (path === '/invitations/inv_1/accept' && options?.method === 'POST') {
        return Promise.resolve({
          invitation_id: 'inv_1',
          status: 'accepted',
          document_id: 'doc_9',
          role: 'editor',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderDocumentsPage();

    await screen.findByText('Pending invitations');
    expect(screen.getByText('Shared Draft')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/invitations/inv_1/accept',
        expect.objectContaining({ method: 'POST' })
      );
    });

    await screen.findByRole('button', { name: /open shared draft/i });
    expect(
      screen.getByText('Invitation accepted. The shared document is now in your list.')
    ).toBeInTheDocument();
  });

  it('shows a live banner when a new invitation appears during polling', async () => {
    vi.useFakeTimers();
    let invitationFetchCount = 0;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents' && !options) {
        return Promise.resolve([]);
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          display_name: 'Recipient',
          email: 'recipient@example.com',
        });
      }

      if (path === '/invitations' && !options) {
        invitationFetchCount += 1;
        return Promise.resolve(
          invitationFetchCount >= 2
            ? [
                {
                  invitation_id: 'inv_2',
                  document_id: 'doc_11',
                  document_title: 'Quarterly Plan',
                  role: 'viewer',
                  invited_email: 'recipient@example.com',
                  inviter: {
                    user_id: 'usr_3',
                    email: 'owner@example.com',
                    username: 'owner',
                    display_name: 'Owner',
                  },
                  created_at: '2026-04-19T12:00:00Z',
                  expires_at: '2026-04-21T12:00:00Z',
                },
              ]
            : []
        );
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderDocumentsPage();

    await act(async () => {});
    expect(screen.getByText('No documents yet.')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(screen.getByRole('status')).toHaveTextContent(
      'Owner shared “Quarterly Plan” with you as Viewer.'
    );
    expect(screen.getByRole('button', { name: /review invites/i })).toBeInTheDocument();
  });
});
