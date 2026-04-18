import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import EditorPage from '../pages/EditorPage';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiFetch: vi.fn(),
    apiJSON: vi.fn(),
  };
});

vi.mock('../components/TiptapEditor', () => ({
  default: function MockTiptapEditor({ content, onChange }) {
    return (
      <div>
        <div data-testid="editor-content">{content}</div>
        <button type="button" onClick={() => onChange('<p>Updated body</p>')}>
          Edit document
        </button>
      </div>
    );
  },
}));

vi.mock('../components/ShareModal', () => ({
  default: function MockShareModal() {
    return <div>Share modal</div>;
  },
}));

function renderEditorPage() {
  return render(
    <MemoryRouter initialEntries={['/documents/1']}>
      <Routes>
        <Route path="/" element={<div>Documents page</div>} />
        <Route path="/documents/:id" element={<EditorPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('EditorPage save flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('access_token', 'test-token');

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve({
          document_id: 1,
          title: 'Draft',
          current_content: '<p>Initial body</p>',
          revision: 0,
          owner_user_id: 1,
          collaborators: [],
        });
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/content') {
        return Promise.resolve({
          document_id: 1,
          latest_version_id: 10,
          revision: 1,
          saved_at: '2026-01-01T00:00:00Z',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('autosaves shortly after content changes', async () => {
    renderEditorPage();

    await screen.findByText('Draft');
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_500);
    });

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/content',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          content: '<p>Updated body</p>',
          base_revision: 0,
        }),
      })
    );
    expect(screen.queryByRole('button', { name: /save now/i })).not.toBeInTheDocument();
  });

  it('sends Save now requests with the backend revision payload', async () => {
    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.click(screen.getByRole('button', { name: /save now/i }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/content',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            content: '<p>Updated body</p>',
            base_revision: 0,
          }),
        })
      );
    });

    expect(screen.queryByRole('button', { name: /save now/i })).not.toBeInTheDocument();
  });

  it('saves before navigating back to the documents list', async () => {
    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.click(screen.getByTitle('All documents'));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/content',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            content: '<p>Updated body</p>',
            base_revision: 0,
          }),
        })
      );
    });

    await screen.findByText('Documents page');
  });
});
