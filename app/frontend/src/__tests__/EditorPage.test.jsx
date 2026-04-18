import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import React, { forwardRef, useImperativeHandle, useState } from 'react';
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
  default: forwardRef(function MockTiptapEditor({ content, onChange, onSelectionUpdate }, ref) {
    const [currentContent, setCurrentContent] = useState(content);

    useImperativeHandle(ref, () => ({
      getSelectionData() {
        return {
          text: 'Selected sentence',
          from: 4,
          to: 21,
        };
      },
      replaceRange() {
        const nextContent = '<p>Before AI rewrite after</p>';
        setCurrentContent(nextContent);
        onChange(nextContent);
        return {
          applied: true,
          html: nextContent,
        };
      },
      getHTML() {
        return currentContent;
      },
      focus() {},
    }), [currentContent, onChange]);

    React.useEffect(() => {
      setCurrentContent(content);
    }, [content]);

    return (
      <div>
        <div data-testid="editor-content">{currentContent}</div>
        <button type="button" onClick={() => onChange('<p>Updated body</p>')}>
          Edit document
        </button>
        <button
          type="button"
          onClick={() =>
            onSelectionUpdate?.({
              text: 'Selected sentence',
              from: 4,
              to: 21,
            })
          }
        >
          Select text
        </button>
      </div>
    );
  }),
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

function buildDocument(overrides = {}) {
  return {
    document_id: 1,
    title: 'Draft',
    current_content: '<p>Initial body</p>',
    revision: 0,
    owner_user_id: 1,
    collaborators: [],
    ai_enabled: true,
    ...overrides,
  };
}

describe('EditorPage save flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('access_token', 'test-token');

    const documentResponses = [buildDocument()];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? buildDocument());
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
    vi.restoreAllMocks();
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

  it('runs rewrite AI after saving unsaved changes and applies the result', async () => {
    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: 'AI final content',
        revision: 2,
        latest_version_id: 11,
      }),
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? documentResponses[0]);
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

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_1',
          status: 'pending',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_1') {
        return Promise.resolve({
          interaction_id: 'ai_1',
          feature_type: 'rewrite',
          scope_type: 'document',
          status: 'completed',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: null,
          selected_text_snapshot: 'Initial body',
          surrounding_context: 'Document title: Draft',
          user_instruction: 'Make it clearer',
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_1',
            generated_output: 'AI rewritten document',
            model_name: 'local-rewrite-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      if (path === '/ai/suggestions/sug_1/accept') {
        return Promise.resolve({
          suggestion_id: 'sug_1',
          outcome: 'accepted',
          applied: true,
          new_revision: 2,
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.change(screen.getByLabelText('Feature'), {
      target: { value: 'rewrite' },
    });
    fireEvent.change(screen.getByLabelText('Rewrite instruction'), {
      target: { value: 'Make it clearer' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate rewrite' }));

    await screen.findByText('AI rewritten document');

    const saveCallIndex = api.apiJSON.mock.calls.findIndex(
      ([path]) => path === '/documents/1/content'
    );
    const aiCallIndex = api.apiJSON.mock.calls.findIndex(
      ([path]) => path === '/documents/1/ai/interactions'
    );

    expect(saveCallIndex).toBeGreaterThan(-1);
    expect(aiCallIndex).toBeGreaterThan(saveCallIndex);

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('AI final content');
    });

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/ai/suggestions/sug_1/accept',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          apply_to_range: {
            start: 0,
            end: '<p>Updated body</p>'.length,
          },
        }),
      })
    );
    expect(screen.getByText('Suggestion applied to the document.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Undo AI' })).toBeInTheDocument();
  });

  it('shows summarize output as review-only', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_2',
          status: 'pending',
          document_id: 1,
          base_revision: 0,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_2') {
        return Promise.resolve({
          interaction_id: 'ai_2',
          feature_type: 'summarize',
          scope_type: 'document',
          status: 'completed',
          document_id: 1,
          base_revision: 0,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: null,
          selected_text_snapshot: 'Initial body',
          surrounding_context: 'Document title: Draft',
          user_instruction: null,
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_2',
            generated_output: 'A short review-only summary',
            model_name: 'local-summary-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Generate summary' }));

    await screen.findByText('A short review-only summary');

    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('runs rewrite AI on selected text and applies it back into the editor', async () => {
    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: '<p>Before AI rewrite after</p>',
        revision: 2,
        latest_version_id: 11,
      }),
    ];

    const saveResponses = [
      {
        document_id: 1,
        latest_version_id: 10,
        revision: 1,
        saved_at: '2026-01-01T00:00:00Z',
      },
      {
        document_id: 1,
        latest_version_id: 11,
        revision: 2,
        saved_at: '2026-01-01T00:00:01Z',
      },
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? documentResponses[0]);
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_sel',
          status: 'pending',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_sel') {
        return Promise.resolve({
          interaction_id: 'ai_sel',
          feature_type: 'rewrite',
          scope_type: 'selection',
          status: 'completed',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: { start: 4, end: 21 },
          selected_text_snapshot: 'Selected sentence',
          surrounding_context: 'Document title: Draft',
          user_instruction: 'Tighten this section',
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_sel',
            generated_output: 'Sharper text',
            model_name: 'local-rewrite-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      if (path === '/documents/1/content') {
        return Promise.resolve(saveResponses.shift());
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    fireEvent.change(screen.getByLabelText('Feature'), {
      target: { value: 'rewrite' },
    });
    fireEvent.change(screen.getByLabelText('Scope'), {
      target: { value: 'selection' },
    });
    fireEvent.change(screen.getByLabelText('Rewrite instruction'), {
      target: { value: 'Tighten this section' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate rewrite' }));

    await screen.findByText('Sharper text');

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/ai/interactions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          feature_type: 'rewrite',
          scope_type: 'selection',
          selected_range: {
            start: 4,
            end: 21,
          },
          selected_text_snapshot: 'Selected sentence',
          surrounding_context: 'Document title: Draft\n\nDocument context: Initial body',
          user_instruction: 'Tighten this section',
          base_revision: 1,
          parameters: {},
        }),
      })
    );

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Before AI rewrite after');
    });

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/content',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          content: '<p>Before AI rewrite after</p>',
          base_revision: 1,
        }),
      })
    );
    expect(screen.getByText('Suggestion applied to the selected text.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Undo AI' })).toBeInTheDocument();
  });

  it('runs Ask AI as a review-only response for selected text', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_chat',
          status: 'pending',
          document_id: 1,
          base_revision: 0,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_chat') {
        return Promise.resolve({
          interaction_id: 'ai_chat',
          feature_type: 'chat_assistant',
          scope_type: 'selection',
          status: 'completed',
          document_id: 1,
          base_revision: 0,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: { start: 4, end: 21 },
          selected_text_snapshot: 'Selected sentence',
          surrounding_context: 'Document title: Draft',
          user_instruction: 'What should I improve here?',
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_chat',
            generated_output: 'You should make this sentence more specific.',
            model_name: 'local-chat-assistant-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    fireEvent.change(screen.getByLabelText('Feature'), {
      target: { value: 'chat_assistant' },
    });
    fireEvent.change(screen.getByLabelText('Scope'), {
      target: { value: 'selection' },
    });
    fireEvent.change(screen.getByLabelText('Ask AI'), {
      target: { value: 'What should I improve here?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }));

    await screen.findByText('You should make this sentence more specific.');

    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('undoes the last whole-document AI rewrite with version restore', async () => {
    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: 'AI final content',
        revision: 2,
        latest_version_id: 11,
      }),
      buildDocument({
        current_content: '<p>Updated body</p>',
        revision: 3,
        latest_version_id: 12,
      }),
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? documentResponses[0]);
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

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_undo_doc',
          status: 'pending',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_undo_doc') {
        return Promise.resolve({
          interaction_id: 'ai_undo_doc',
          feature_type: 'rewrite',
          scope_type: 'document',
          status: 'completed',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: null,
          selected_text_snapshot: 'Updated body',
          surrounding_context: 'Document title: Draft',
          user_instruction: 'Make it clearer',
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_undo_doc',
            generated_output: 'AI rewritten document',
            model_name: 'local-rewrite-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      if (path === '/ai/suggestions/sug_undo_doc/accept') {
        return Promise.resolve({
          suggestion_id: 'sug_undo_doc',
          outcome: 'accepted',
          applied: true,
          new_revision: 2,
        });
      }

      if (path === '/documents/1/versions/10/restore') {
        return Promise.resolve({
          document_id: 1,
          restored_from_version_id: 10,
          new_version_id: 12,
          message: 'Version restored as a new version entry.',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.change(screen.getByLabelText('Feature'), {
      target: { value: 'rewrite' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate rewrite' }));

    await screen.findByText('AI rewritten document');
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await screen.findByRole('button', { name: 'Undo AI' });
    fireEvent.click(screen.getByRole('button', { name: 'Undo AI' }));

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Updated body');
    });

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/versions/10/restore',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(screen.getByText('AI change undone.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Undo AI' })).not.toBeInTheDocument();
  });

  it('undoes the last selected-text AI rewrite with version restore', async () => {
    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: '<p>Before AI rewrite after</p>',
        revision: 2,
        latest_version_id: 11,
      }),
      buildDocument({
        current_content: '<p>Initial body</p>',
        revision: 3,
        latest_version_id: 12,
      }),
    ];

    const saveResponses = [
      {
        document_id: 1,
        latest_version_id: 10,
        revision: 1,
        saved_at: '2026-01-01T00:00:00Z',
      },
      {
        document_id: 1,
        latest_version_id: 11,
        revision: 2,
        saved_at: '2026-01-01T00:00:01Z',
      },
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? documentResponses[0]);
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/content') {
        return Promise.resolve(saveResponses.shift());
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_undo_sel',
          status: 'pending',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_undo_sel') {
        return Promise.resolve({
          interaction_id: 'ai_undo_sel',
          feature_type: 'rewrite',
          scope_type: 'selection',
          status: 'completed',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: { start: 4, end: 21 },
          selected_text_snapshot: 'Selected sentence',
          surrounding_context: 'Document title: Draft',
          user_instruction: 'Tighten this section',
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_undo_sel',
            generated_output: 'Sharper text',
            model_name: 'local-rewrite-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      if (path === '/documents/1/versions/10/restore') {
        return Promise.resolve({
          document_id: 1,
          restored_from_version_id: 10,
          new_version_id: 12,
          message: 'Version restored as a new version entry.',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    fireEvent.change(screen.getByLabelText('Feature'), {
      target: { value: 'rewrite' },
    });
    fireEvent.change(screen.getByLabelText('Scope'), {
      target: { value: 'selection' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate rewrite' }));

    await screen.findByText('Sharper text');
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await screen.findByRole('button', { name: 'Undo AI' });
    fireEvent.click(screen.getByRole('button', { name: 'Undo AI' }));

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Initial body');
    });

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/versions/10/restore',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(screen.getByText('AI change undone.')).toBeInTheDocument();
  });

  it('clears Undo AI after manual document edits', async () => {
    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: 'AI final content',
        revision: 2,
        latest_version_id: 11,
      }),
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? documentResponses[0]);
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

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_clear_edit',
          status: 'pending',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_clear_edit') {
        return Promise.resolve({
          interaction_id: 'ai_clear_edit',
          feature_type: 'rewrite',
          scope_type: 'document',
          status: 'completed',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: null,
          selected_text_snapshot: 'Updated body',
          surrounding_context: 'Document title: Draft',
          user_instruction: 'Make it clearer',
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_clear_edit',
            generated_output: 'AI rewritten document',
            model_name: 'local-rewrite-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      if (path === '/ai/suggestions/sug_clear_edit/accept') {
        return Promise.resolve({
          suggestion_id: 'sug_clear_edit',
          outcome: 'accepted',
          applied: true,
          new_revision: 2,
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.change(screen.getByLabelText('Feature'), {
      target: { value: 'rewrite' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate rewrite' }));

    await screen.findByText('AI rewritten document');
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await screen.findByRole('button', { name: 'Undo AI' });
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Undo AI' })).not.toBeInTheDocument();
    });
  });

  it('clears Undo AI after renaming the document', async () => {
    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: 'AI final content',
        revision: 2,
        latest_version_id: 11,
      }),
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? documentResponses[0]);
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

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve({
          interaction_id: 'ai_clear_title',
          status: 'pending',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/ai/interactions/ai_clear_title') {
        return Promise.resolve({
          interaction_id: 'ai_clear_title',
          feature_type: 'rewrite',
          scope_type: 'document',
          status: 'completed',
          document_id: 1,
          base_revision: 1,
          created_at: '2026-01-01T00:00:00Z',
          completed_at: '2026-01-01T00:00:01Z',
          rendered_prompt: 'prompt',
          selected_range: null,
          selected_text_snapshot: 'Updated body',
          surrounding_context: 'Document title: Draft',
          user_instruction: 'Make it clearer',
          parameters: {},
          outcome: null,
          outcome_recorded_at: null,
          suggestion: {
            suggestion_id: 'sug_clear_title',
            generated_output: 'AI rewritten document',
            model_name: 'local-rewrite-fallback',
            stale: false,
            usage: null,
          },
        });
      }

      if (path === '/ai/suggestions/sug_clear_title/accept') {
        return Promise.resolve({
          suggestion_id: 'sug_clear_title',
          outcome: 'accepted',
          applied: true,
          new_revision: 2,
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.change(screen.getByLabelText('Feature'), {
      target: { value: 'rewrite' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate rewrite' }));

    await screen.findByText('AI rewritten document');
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await screen.findByRole('button', { name: 'Undo AI' });
    fireEvent.click(screen.getByText('Draft'));

    const titleInput = screen.getByDisplayValue('Draft');
    fireEvent.change(titleInput, {
      target: { value: 'Renamed draft' },
    });
    fireEvent.keyDown(titleInput, {
      key: 'Enter',
    });

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Undo AI' })).not.toBeInTheDocument();
    });
  });

  it('can close and reopen the AI sidebar without losing draft state', async () => {
    renderEditorPage();

    await screen.findByText('Draft');

    const sidebar = screen.getByLabelText('AI Assistant', {
      selector: 'aside',
      hidden: true,
    });
    const instructionInput = screen.getByLabelText('Summary focus');

    fireEvent.change(instructionInput, {
      target: { value: 'Call out action items' },
    });
    fireEvent.click(screen.getByRole('button', { name: /close ai sidebar/i }));

    expect(sidebar).toHaveAttribute('data-state', 'closed');
    expect(screen.getByRole('button', { name: /show ai/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /show ai/i }));

    expect(sidebar).toHaveAttribute('data-state', 'open');
    expect(screen.getByLabelText('Summary focus')).toHaveValue('Call out action items');
  });

  it('shows a restricted AI notice for viewers', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(
          buildDocument({
            owner_user_id: 2,
            collaborators: [
              {
                user_id: 1,
                role: 'viewer',
              },
            ],
          })
        );
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'viewer@example.com',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');

    expect(
      screen.getByText('Your role can view this document, but it cannot run AI actions.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate summary' })).toBeDisabled();
  });

  it('shows when AI is disabled for the document', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(
          buildDocument({
            ai_enabled: false,
          })
        );
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');

    expect(screen.getByText('AI is disabled for this document.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate summary' })).toBeDisabled();
  });

  it('shows version history and restores an older version', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: '<p>Restored body</p>',
        revision: 2,
        latest_version_id: 12,
      }),
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? documentResponses[0]);
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/versions' && !options) {
        return Promise.resolve([
          {
            version_id: 5,
            version_number: 2,
            created_by: 1,
            created_at: '2026-01-01T00:10:00Z',
            is_restore_version: false,
          },
          {
            version_id: 4,
            version_number: 1,
            created_by: 1,
            created_at: '2026-01-01T00:00:00Z',
            is_restore_version: false,
          },
        ]);
      }

      if (path === '/documents/1/content') {
        return Promise.resolve({
          document_id: 1,
          latest_version_id: 10,
          revision: 1,
          saved_at: '2026-01-01T00:05:00Z',
        });
      }

      if (path === '/documents/1/versions/4/restore') {
        return Promise.resolve({
          document_id: 1,
          restored_from_version_id: 4,
          new_version_id: 12,
          message: 'Version restored as a new version entry.',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    await screen.findByText('Version history');
    expect(screen.getByText('Version 1')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'Restore' })[1]);

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Restored body');
    });

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/versions/4/restore',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });

  it('exports the document in the selected format', async () => {
    const createObjectURL = vi.fn(() => 'blob:export');
    const revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    window.URL.createObjectURL = createObjectURL;
    window.URL.revokeObjectURL = revokeObjectURL;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/export') {
        return Promise.resolve({
          document_id: 1,
          title: 'Draft',
          format: 'html',
          content_type: 'text/html',
          filename: 'draft.html',
          exported_content: '<p>Initial body</p>',
          revision: 0,
          exported_at: '2026-01-01T00:00:00Z',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));

    await screen.findByText('Export document');
    fireEvent.change(screen.getByLabelText('Export format'), {
      target: { value: 'html' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Download export' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/export',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ format: 'html' }),
        })
      );
    });

    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:export');
  });
});
