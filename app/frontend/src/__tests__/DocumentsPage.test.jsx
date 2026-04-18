import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    const { container } = renderDocumentsPage();

    await screen.findByText('Project Notes');

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
});
