import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import React, { forwardRef, useImperativeHandle, useState } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import EditorPage from '../pages/EditorPage';
import * as api from '../api';

const originalWebSocket = globalThis.WebSocket;
const mockUsePendingInvitations = vi.fn(() => ({
  invitations: [],
  loading: false,
  error: '',
  clearError: vi.fn(),
  activeNotification: null,
  dismissNotification: vi.fn(),
  refreshInvitations: vi.fn(),
  acceptInvitation: vi.fn(),
  declineInvitation: vi.fn(),
}));
const mockEditorCaptureViewState = vi.fn(() => null);
const mockEditorRestoreViewState = vi.fn(() => true);
const mockEditorFocus = vi.fn();
const mockEditorSetSelection = vi.fn(() => true);

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiFetch: vi.fn(),
    apiJSON: vi.fn(),
  };
});

vi.mock('../components/TiptapEditor', () => ({
  default: forwardRef(function MockTiptapEditor(
    {
      content,
      onChange,
      onSelectionUpdate,
      readOnly = false,
      lineSpacing = 1.15,
      onLineSpacingChange,
      onSendableSteps,
      collaborationVersion = 0,
      collaborationResetKey = 0,
      remoteAwareness = [],
    },
    ref
  ) {
    const [currentContent, setCurrentContent] = useState(content);
    const [currentVersion, setCurrentVersion] = useState(collaborationVersion);
    const localInflightRef = React.useRef(false);
    const queuedBatchRef = React.useRef(null);

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
      applyRemoteSteps({ steps }) {
        const nextContent = steps?.[0]?.mockHtml ?? '<p>Remote collaborative body</p>';
        const nextVersion = currentVersion + (steps?.length ?? 0);
        setCurrentContent(nextContent);
        setCurrentVersion(nextVersion);
        localInflightRef.current = false;
        return {
          applied: true,
          html: nextContent,
          version: nextVersion,
        };
      },
      getCollaborationVersion() {
        return currentVersion;
      },
      getPendingStepBatch() {
        const payload = queuedBatchRef.current;
        queuedBatchRef.current = null;
        if (payload) {
          localInflightRef.current = true;
        }
        return payload;
      },
      focus() {
        mockEditorFocus();
      },
      setSelection(selection) {
        mockEditorSetSelection(selection);
        mockEditorFocus();
        return true;
      },
      findTextRange(query) {
        if (query === 'Selected sentence') {
          return { from: 4, to: 21 };
        }
        return null;
      },
      getViewState() {
        return mockEditorCaptureViewState();
      },
      restoreViewState(snapshot) {
        return mockEditorRestoreViewState(snapshot);
      },
    }), [currentContent, currentVersion, onChange]);

    React.useEffect(() => {
      setCurrentContent(content);
    }, [content]);

    React.useEffect(() => {
      setCurrentVersion(collaborationVersion);
    }, [collaborationVersion, collaborationResetKey]);

    return (
      <div>
        <div data-testid="editor-content">{currentContent}</div>
        <div data-testid="editor-line-spacing">{lineSpacing}</div>
        <div data-testid="remote-awareness">
          {remoteAwareness.map((entry) => `${entry.label}:${entry.from}-${entry.to}`).join('|')}
        </div>
        {!readOnly ? (
          <>
            <button type="button" onClick={() => onChange('<p>Updated body</p>')}>
              Edit document
            </button>
            <button type="button" onClick={() => onLineSpacingChange?.(1.5)}>
              Change line spacing
            </button>
            <button
              type="button"
              onClick={() => {
                const nextContent = '<p>Local collaborative body</p>';
                setCurrentContent(nextContent);
                onChange(nextContent, {
                  hasPendingCollaborationSteps: true,
                  collaborationVersion: currentVersion,
                });
                const nextPayload = {
                  batchId: 'batch-1',
                  version: currentVersion,
                  clientId: 'client-1',
                  steps: [{ mockStep: true, mockHtml: nextContent }],
                  content: nextContent,
                  lineSpacing,
                  affectedRange: { start: 4, end: 21 },
                  candidateContentSnapshot: 'Local collaborative body',
                  exactTextSnapshot: 'Initial body',
                  prefixContext: 'Before',
                  suffixContext: 'After',
                };

                if (localInflightRef.current) {
                  queuedBatchRef.current = {
                    ...nextPayload,
                    version: currentVersion + 1,
                  };
                  return;
                }

                localInflightRef.current = true;
                onSendableSteps?.(nextPayload);
              }}
            >
              Send collaboration step
            </button>
          </>
        ) : null}
        <button
          type="button"
          onClick={() =>
            onSelectionUpdate?.({
              text: 'Selected sentence',
              from: 4,
              to: 21,
              direction: 'forward',
            })
          }
        >
          Select text
        </button>
        <button
          type="button"
          onClick={() =>
            onSelectionUpdate?.({
              text: '',
              from: 8,
              to: 8,
              direction: 'forward',
            })
          }
        >
          Move cursor
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

vi.mock('../hooks/usePendingInvitations', () => ({
  default: (...args) => mockUsePendingInvitations(...args),
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

async function clickAiShortcut(label) {
  const showAiButton = screen.queryByRole('button', { name: /show ai/i });
  if (showAiButton) {
    fireEvent.click(showAiButton);
  }
  fireEvent.click(screen.getByRole('button', { name: /shortcuts/i }));
  fireEvent.click(await screen.findByRole('menuitem', { name: label }));
}

async function openAiSidebar() {
  const showAiButton = screen.queryByRole('button', { name: /show ai/i });
  if (showAiButton) {
    fireEvent.click(showAiButton);
  }
  await screen.findByLabelText('AI Assistant');
}

function buildDocument(overrides = {}) {
  return {
    document_id: 1,
    title: 'Draft',
    current_content: '<p>Initial body</p>',
    line_spacing: 1.15,
    revision: 0,
    owner_user_id: 1,
    collaborators: [],
    ai_enabled: true,
    ...overrides,
  };
}

function buildInteractionDetail(overrides = {}) {
  return {
    interaction_id: 'ai_1',
    conversation_id: 'conv_doc_1_usr_1',
    entry_kind: 'suggestion',
    message_role: 'assistant',
    feature_type: 'rewrite',
    scope_type: 'document',
    status: 'completed',
    document_id: 1,
    source_revision: 0,
    base_revision: 0,
    created_at: '2026-01-01T00:00:00Z',
    completed_at: '2026-01-01T00:00:01Z',
    rendered_prompt: 'prompt',
    selected_range: null,
    selected_text_snapshot: 'Initial body',
    surrounding_context: 'Document title: Draft',
    user_instruction: null,
    reply_to_interaction_id: null,
    parameters: {},
    outcome: null,
    outcome_recorded_at: null,
    suggestion: {
      suggestion_id: 'sug_1',
      generated_output: 'AI output',
      model_name: 'local-rewrite-fallback',
      stale: false,
      usage: null,
    },
    ...overrides,
  };
}

function buildHistoryItem(overrides = {}) {
  return {
    interaction_id: 'ai_1',
    conversation_id: 'conv_doc_1_usr_1',
    entry_kind: 'suggestion',
    message_role: 'assistant',
    feature_type: 'rewrite',
    scope_type: 'document',
    user_id: 1,
    status: 'completed',
    created_at: '2026-01-01T00:00:00Z',
    source_revision: 0,
    model_name: 'local-rewrite-fallback',
    outcome: null,
    total_tokens: 42,
    ...overrides,
  };
}

function buildThreadEntries(entries) {
  return entries.map((entry, index) => ({
    entry_id: `thread_${index + 1}`,
    interaction_id: null,
    conversation_id: 'conv_doc_1_usr_1',
    entry_kind: 'chat_message',
    message_role: 'user',
    feature_type: 'chat_assistant',
    scope_type: 'document',
    status: 'completed',
    created_at: `2026-01-01T00:00:0${index}Z`,
    source_revision: 0,
    content: '',
    selected_range: null,
    selected_text_snapshot: null,
    surrounding_context: null,
    reply_to_interaction_id: null,
    outcome: null,
    review_only: true,
    suggestion: null,
    ...entry,
  }));
}

function createSseResponse(events, { delayMs = 0, signal } = {}) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      let aborted = false;

      function handleAbort() {
        aborted = true;
        const abortError = new Error('Aborted');
        abortError.name = 'AbortError';
        controller.error(abortError);
      }

      signal?.addEventListener?.('abort', handleAbort, { once: true });

      try {
        for (const event of events) {
          if (aborted) {
            return;
          }

          controller.enqueue(
            encoder.encode(`event: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`)
          );

          if (delayMs) {
            await new Promise((resolve) => {
              window.setTimeout(resolve, delayMs);
            });
          }
        }

        if (!aborted) {
          controller.close();
        }
      } finally {
        signal?.removeEventListener?.('abort', handleAbort);
      }
    },
  });

  return new Response(stream, {
    status: 202,
    headers: {
      'Content-Type': 'text/event-stream',
    },
  });
}

class MockWebSocket {
  static instances = [];

  static OPEN = 1;

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.OPEN;
    this.sentMessages = [];
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.onopen?.();
    });
  }

  send(message) {
    this.sentMessages.push(JSON.parse(message));
  }

  close(event = { code: 1006, reason: '' }) {
    this.readyState = 3;
    this.onclose?.(event);
  }

  emit(payload) {
    this.onmessage?.({
      data: JSON.stringify(payload),
    });
  }
}

describe('EditorPage save flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePendingInvitations.mockReturnValue({
      invitations: [],
      loading: false,
      error: '',
      clearError: vi.fn(),
      activeNotification: null,
      dismissNotification: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptInvitation: vi.fn(),
      declineInvitation: vi.fn(),
    });
    mockEditorCaptureViewState.mockImplementation(() => null);
    mockEditorRestoreViewState.mockImplementation(() => true);
    mockEditorFocus.mockImplementation(() => {});
    mockEditorSetSelection.mockImplementation(() => true);
    api.apiFetch.mockReset();
    api.apiFetch.mockResolvedValue(null);
    api.apiJSON.mockReset();
    localStorage.clear();
    sessionStorage.clear();
    document.title = 'frontend';
    localStorage.setItem('access_token', 'test-token');
    MockWebSocket.instances = [];
    globalThis.WebSocket = undefined;

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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/comments') {
        return Promise.resolve([]);
      }

      if (path === '/invitations') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/content') {
        return Promise.resolve({
          document_id: 1,
          latest_version_id: 10,
          line_spacing: 1.15,
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
    globalThis.WebSocket = originalWebSocket;
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
          line_spacing: 1.15,
          save_source: 'autosave',
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
            line_spacing: 1.15,
            save_source: 'manual',
          }),
        })
      );
    });

    expect(screen.queryByRole('button', { name: /save now/i })).not.toBeInTheDocument();
  });

  it('treats commenters as read-only and hides AI access', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument({ role: 'commenter' }));
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 2,
          email: 'commenter@example.com',
        });
      }

      if (path === '/documents/1/comments') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    expect(screen.getByText(/comment-only access/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /edit document/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /show ai/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /comments/i })).toBeInTheDocument();
  });

  it('shows a live invitation banner on the editor page when a new invite arrives', async () => {
    const dismissNotification = vi.fn();
    mockUsePendingInvitations.mockReturnValue({
      invitations: [],
      loading: false,
      error: '',
      clearError: vi.fn(),
      activeNotification: {
        invitation_id: 'inv_9',
        document_id: 'doc_7',
        document_title: 'Shared Outline',
        role: 'commenter',
        invited_email: 'user@example.com',
        inviter: {
          user_id: 'usr_3',
          email: 'owner@example.com',
          username: 'owner',
          display_name: 'Owner',
        },
        created_at: '2026-01-01T00:00:00Z',
        expires_at: '2026-01-03T00:00:00Z',
      },
      dismissNotification,
      refreshInvitations: vi.fn(),
      acceptInvitation: vi.fn(),
      declineInvitation: vi.fn(),
    });

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

      if (path === '/documents/1/comments') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');

    expect(screen.getByRole('status')).toHaveTextContent(
      'Owner shared “Shared Outline” with you as Commenter.'
    );
    fireEvent.click(screen.getByRole('button', { name: /review invites/i }));
    expect(dismissNotification).toHaveBeenCalledWith('inv_9');
    await screen.findByText('Documents page');
  });

  it('creates sidebar comments with the selected text snapshot', async () => {
    let comments = [];
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

      if (path === '/documents/1/comments' && !options) {
        return Promise.resolve(comments);
      }

      if (path === '/documents/1/comments' && options?.method === 'POST') {
        const payload = JSON.parse(options.body);
        const createdComment = {
          comment_id: 'cmt_1',
          document_id: 1,
          author_user_id: 1,
          author: { user_id: 1, display_name: 'Owner' },
          body: payload.body,
          quoted_text: payload.quoted_text,
          status: 'open',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          resolved_at: null,
          resolved_by_user_id: null,
        };
        comments = [createdComment];
        return Promise.resolve(createdComment);
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: /comments/i }));
    fireEvent.click(screen.getByRole('button', { name: /select text/i }));
    fireEvent.change(screen.getByLabelText(/new comment/i), {
      target: { value: 'Please tighten this section.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /post comment/i }));

    await waitFor(() =>
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/comments',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            body: 'Please tighten this section.',
            quoted_text: 'Selected sentence',
          }),
        })
      )
    );
    expect(screen.getByText('Please tighten this section.')).toBeInTheDocument();
    expect(screen.getAllByText('Selected sentence').length).toBeGreaterThan(0);
  });

  it('jumps to the quoted context when a comment quote is clicked', async () => {
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

      if (path === '/documents/1/comments') {
        return Promise.resolve([
          {
            comment_id: 'cmt_1',
            document_id: 1,
            author_user_id: 1,
            author: { user_id: 1, display_name: 'Owner' },
            body: 'Please tighten this section.',
            quoted_text: 'Selected sentence',
            status: 'open',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
            resolved_at: null,
            resolved_by_user_id: null,
          },
        ]);
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: /comments/i }));
    fireEvent.click(
      await screen.findByRole('button', {
        name: /quoted text[\s\S]*selected sentence/i,
      })
    );

    expect(mockEditorSetSelection).toHaveBeenCalledWith({ from: 4, to: 21 });
    expect(mockEditorFocus).toHaveBeenCalled();
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
            line_spacing: 1.15,
            save_source: 'manual',
          }),
        })
      );
    });

    await screen.findByText('Documents page');
  });

  it('navigates back immediately when there are no unsaved changes', async () => {
    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByTitle('All documents'));

    await screen.findByText('Documents page');
    expect(api.apiJSON).not.toHaveBeenCalledWith(
      '/documents/1/content',
      expect.objectContaining({
        method: 'PATCH',
      })
    );
  });

  it('saves line spacing changes with the current revision', async () => {
    renderEditorPage();

    await screen.findByText('Draft');
    expect(document.title).toBe('Draft • CollabDocs');
    fireEvent.click(screen.getByRole('button', { name: 'Change line spacing' }));
    fireEvent.click(screen.getByRole('button', { name: /save now/i }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/content',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            content: '<p>Initial body</p>',
            base_revision: 0,
            line_spacing: 1.5,
            save_source: 'manual',
          }),
        })
      );
    });

    expect(screen.getByTestId('editor-line-spacing')).toHaveTextContent('1.5');
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/content') {
        return Promise.resolve({
          document_id: 1,
          latest_version_id: 10,
          line_spacing: 1.15,
          revision: 1,
          saved_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([buildHistoryItem()]);
      }

      if (path === '/ai/interactions/ai_1') {
        return Promise.resolve(
          buildInteractionDetail({
            user_instruction: 'Make it clearer',
            source_revision: 1,
            base_revision: 1,
            suggestion: {
              suggestion_id: 'sug_1',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
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

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_1',
            status: 'processing',
            document_id: 1,
            base_revision: 1,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_1',
            delta: 'AI rewritten document',
            output: 'AI rewritten document',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_1',
            user_instruction: 'Make it clearer',
            source_revision: 1,
            base_revision: 1,
            suggestion: {
              suggestion_id: 'sug_1',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    await openAiSidebar();
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Make it clearer' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('AI rewritten document');

    const saveCallIndex = api.apiJSON.mock.calls.findIndex(
      ([path]) => path === '/documents/1/content'
    );
    const aiCallIndex = api.apiFetch.mock.calls.findIndex(
      ([path]) => path === '/documents/1/ai/interactions/stream'
    );
    const saveCallOrder = api.apiJSON.mock.invocationCallOrder[saveCallIndex];
    const aiCallOrder = api.apiFetch.mock.invocationCallOrder[aiCallIndex];

    expect(saveCallIndex).toBeGreaterThan(-1);
    expect(aiCallIndex).toBeGreaterThan(-1);
    expect(aiCallOrder).toBeGreaterThan(saveCallOrder);

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_2',
            feature_type: 'summarize',
            entry_kind: 'chat_message',
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_2') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_2',
            entry_kind: 'chat_message',
            feature_type: 'summarize',
            suggestion: {
              suggestion_id: 'sug_2',
              generated_output: 'A short review-only summary',
              model_name: 'local-summary-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_2',
            status: 'processing',
            document_id: 1,
            base_revision: 0,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_2',
            delta: 'A short review-only summary',
            output: 'A short review-only summary',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_2',
            entry_kind: 'chat_message',
            feature_type: 'summarize',
            suggestion: {
              suggestion_id: 'sug_2',
              generated_output: 'A short review-only summary',
              model_name: 'local-summary-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    await clickAiShortcut('Summarize');

    await screen.findByText('A short review-only summary');

    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('partially accepts a document suggestion by mixing original and AI parts', async () => {
    const documentResponses = [
      buildDocument({
        current_content: '<p>Original opening. Original closing.</p>',
        revision: 1,
        latest_version_id: 10,
      }),
      buildDocument({
        current_content: '<p>AI opening. Original closing.</p>',
        revision: 2,
        latest_version_id: 11,
      }),
    ];

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(
          documentResponses.shift() ?? buildDocument({
            current_content: '<p>AI opening. Original closing.</p>',
            revision: 2,
            latest_version_id: 11,
          })
        );
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_partial',
            source_revision: 1,
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_partial') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_partial',
            source_revision: 1,
            base_revision: 1,
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_partial',
              generated_output: 'AI opening. AI closing.',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      if (path === '/ai/suggestions/sug_partial/apply-edited') {
        return Promise.resolve({
          interaction_id: 'ai_partial',
          outcome: 'accepted',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_partial',
            status: 'processing',
            document_id: 1,
            base_revision: 1,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_partial',
            delta: 'AI opening. AI closing.',
            output: 'AI opening. AI closing.',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_partial',
            source_revision: 1,
            base_revision: 1,
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_partial',
              generated_output: 'AI opening. AI closing.',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    await openAiSidebar();
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Make it clearer' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('AI opening. AI closing.');
    fireEvent.click(screen.getByRole('button', { name: 'Partial accept' }));

    await screen.findByText('Partial acceptance preview');
    fireEvent.click(screen.getByRole('button', { name: /keep original for part 2/i }));

    expect(screen.getByText('AI opening. Original closing.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Apply partial' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/ai/suggestions/sug_partial/apply-edited',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            edited_output: 'AI opening. Original closing.',
            apply_to_range: {
              start: 0,
              end: '<p>Original opening. Original closing.</p>'.length,
            },
          }),
        })
      );
    });

    expect(screen.getByText('Partially accepted suggestion applied to the document.')).toBeInTheDocument();
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
        line_spacing: 1.15,
        revision: 1,
        saved_at: '2026-01-01T00:00:00Z',
      },
      {
        document_id: 1,
        latest_version_id: 11,
        line_spacing: 1.15,
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_sel',
            scope_type: 'selection',
            source_revision: 1,
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_sel') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_sel',
            scope_type: 'selection',
            source_revision: 1,
            base_revision: 1,
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Tighten this section',
            suggestion: {
              suggestion_id: 'sug_sel',
              generated_output: 'Sharper text',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      if (path === '/documents/1/content') {
        return Promise.resolve(saveResponses.shift());
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_sel',
            status: 'processing',
            document_id: 1,
            base_revision: 1,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_sel',
            delta: 'Sharper text',
            output: 'Sharper text',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_sel',
            scope_type: 'selection',
            source_revision: 1,
            base_revision: 1,
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Tighten this section',
            suggestion: {
              suggestion_id: 'sug_sel',
              generated_output: 'Sharper text',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    await openAiSidebar();
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Tighten this section' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('Sharper text');

    expect(api.apiFetch).toHaveBeenCalledWith(
      '/documents/1/ai/interactions/stream',
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
          parameters: {
            tone: 'neutral',
          },
        }),
      })
    );

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

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
          line_spacing: 1.15,
          save_source: 'manual',
        }),
      })
    );
    expect(screen.getByText('Suggestion applied to the selected text.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Undo AI' })).toBeInTheDocument();
  });

  it('refreshes the latest realtime revision before running AI when a live snapshot save reports a stale revision', async () => {
    globalThis.WebSocket = MockWebSocket;

    const documentResponses = [
      buildDocument({
        revision: 1,
        latest_version_id: 10,
      }),
      buildDocument({
        current_content: '<p>Local collaborative body</p>',
        revision: 2,
        latest_version_id: 11,
      }),
    ];
    const staleSaveError = Object.assign(
      new Error('The document revision is stale. Refresh and retry.'),
      { status: 409 }
    );

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? buildDocument({
          current_content: '<p>Local collaborative body</p>',
          revision: 2,
          latest_version_id: 11,
        }));
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 1,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_realtime',
            scope_type: 'selection',
            source_revision: 2,
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_realtime') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_realtime',
            scope_type: 'selection',
            source_revision: 2,
            base_revision: 2,
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Tighten this section',
            suggestion: {
              suggestion_id: 'sug_realtime',
              generated_output: 'Sharper text',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      if (path === '/documents/1/content') {
        return Promise.reject(staleSaveError);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_realtime',
            status: 'processing',
            document_id: 1,
            base_revision: 2,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_realtime',
            delta: 'Sharper text',
            output: 'Sharper text',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_realtime',
            scope_type: 'selection',
            source_revision: 2,
            base_revision: 2,
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Tighten this section',
            suggestion: {
              suggestion_id: 'sug_realtime',
              generated_output: 'Sharper text',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));

    await act(async () => {
      MockWebSocket.instances[0].emit({
        type: 'steps_applied',
        actor_user_id: 1,
        actor_display_name: 'Owner',
        collab_version: 1,
        steps: [{ mockHtml: '<p>Local collaborative body</p>' }],
        client_ids: ['client-1'],
        content: '<p>Local collaborative body</p>',
        line_spacing: 1.15,
        batch: {
          batch_id: 'batch-1',
          version: 0,
          client_id: 'client-1',
          affected_range: { start: 4, end: 21 },
          candidate_content_snapshot: 'Local collaborative body',
          exact_text_snapshot: 'Initial body',
          prefix_context: 'Before',
          suffix_context: 'After',
          actor_user_id: 1,
          actor_display_name: 'Owner',
        },
      });
    });

    expect(screen.getByText('Saved')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    await openAiSidebar();
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Tighten this section' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('Sharper text');

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/content',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          content: '<p>Local collaborative body</p>',
          base_revision: 1,
          line_spacing: 1.15,
          save_source: 'manual',
        }),
      })
    );
    expect(api.apiFetch).toHaveBeenCalledWith(
      '/documents/1/ai/interactions/stream',
      expect.objectContaining({
        body: JSON.stringify({
          feature_type: 'rewrite',
          scope_type: 'selection',
          selected_range: {
            start: 4,
            end: 21,
          },
          selected_text_snapshot: 'Selected sentence',
          surrounding_context: 'Document title: Draft\n\nDocument context: Local collaborative body',
          user_instruction: 'Tighten this section',
          base_revision: 2,
          parameters: {
            tone: 'neutral',
          },
        }),
      })
    );
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_chat',
            entry_kind: 'chat_message',
            feature_type: 'chat_assistant',
            scope_type: 'selection',
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_chat') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_chat',
            entry_kind: 'chat_message',
            feature_type: 'chat_assistant',
            scope_type: 'selection',
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'What should I improve here?',
            suggestion: {
              suggestion_id: 'sug_chat',
              generated_output: 'You should make this sentence more specific.',
              model_name: 'local-chat-assistant-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_chat',
            status: 'processing',
            document_id: 1,
            base_revision: 0,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_chat',
            delta: 'You should make this sentence more specific.',
            output: 'You should make this sentence more specific.',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_chat',
            entry_kind: 'chat_message',
            feature_type: 'chat_assistant',
            scope_type: 'selection',
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'What should I improve here?',
            suggestion: {
              suggestion_id: 'sug_chat',
              generated_output: 'You should make this sentence more specific.',
              model_name: 'local-chat-assistant-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    await openAiSidebar();
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'What should I improve here?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await screen.findByText('You should make this sentence more specific.');

    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('sends translate parameters and lets the user apply the translated result', async () => {
    const documentResponses = [
      buildDocument({
        latest_version_id: 9,
      }),
      buildDocument({
        current_content: '<p>Translated copy</p>',
        revision: 1,
        latest_version_id: 10,
      }),
    ];

    const saveResponses = [
      {
        document_id: 1,
        latest_version_id: 10,
        line_spacing: 1.15,
        revision: 1,
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_translate',
            scope_type: 'selection',
            feature_type: 'translate',
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_translate') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_translate',
            feature_type: 'translate',
            scope_type: 'selection',
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Translate for a French-speaking teammate.',
            parameters: { target_language: 'French' },
            suggestion: {
              suggestion_id: 'sug_translate',
              generated_output: 'Texto traducido',
              model_name: 'local-translate-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      if (path === '/documents/1/content') {
        return Promise.resolve(saveResponses.shift());
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_translate',
            status: 'processing',
            document_id: 1,
            base_revision: 0,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_translate',
            delta: 'Texto traducido',
            output: 'Texto traducido',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_translate',
            feature_type: 'translate',
            scope_type: 'selection',
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Translate for a French-speaking teammate.',
            parameters: { target_language: 'French' },
            suggestion: {
              suggestion_id: 'sug_translate',
              generated_output: 'Texto traducido',
              model_name: 'local-translate-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    await openAiSidebar();
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Translate for a French-speaking teammate.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /shortcuts/i }));
    fireEvent.change(screen.getByLabelText('Translate to'), {
      target: { value: 'French' },
    });
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Translate' }));

    await screen.findByText('Texto traducido');

    expect(api.apiFetch).toHaveBeenCalledWith(
      '/documents/1/ai/interactions/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          feature_type: 'translate',
          scope_type: 'selection',
          selected_range: {
            start: 4,
            end: 21,
          },
          selected_text_snapshot: 'Selected sentence',
          surrounding_context: 'Document title: Draft\n\nDocument context: Initial body',
          user_instruction: 'Translate for a French-speaking teammate.',
          base_revision: 0,
          parameters: {
            target_language: 'French',
          },
        }),
      })
    );

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Before AI rewrite after');
    });

    expect(screen.getByText('Suggestion applied to the selected text.')).toBeInTheDocument();
  });

  it('streams AI output progressively through the sidebar stream endpoint', async () => {
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_stream',
            feature_type: 'summarize',
            entry_kind: 'chat_message',
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_stream') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_stream',
            entry_kind: 'chat_message',
            feature_type: 'summarize',
            suggestion: {
              suggestion_id: 'sug_stream',
              generated_output: 'A short streamed summary',
              model_name: 'local-summary-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_stream',
            status: 'processing',
            document_id: 1,
            base_revision: 0,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_stream',
            delta: 'A short',
            output: 'A short',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_stream',
            delta: ' streamed summary',
            output: 'A short streamed summary',
          },
        },
        {
          type: 'complete',
          data: {
            interaction_id: 'ai_stream',
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
              suggestion_id: 'sug_stream',
              generated_output: 'A short streamed summary',
              model_name: 'local-summary-fallback',
              stale: false,
              usage: null,
            },
          },
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    await clickAiShortcut('Summarize');

    await screen.findByText('A short streamed summary');
    expect(api.apiFetch).toHaveBeenCalledWith(
      '/documents/1/ai/interactions/stream',
      expect.objectContaining({
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
        },
      })
    );
    expect(screen.getByText('Summary ready to review.')).toBeInTheDocument();
  });

  it('can cancel a streamed AI run and preserve partial output', async () => {
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve(
          buildThreadEntries([
            {
              entry_id: 'thread_user_cancel',
              message_role: 'user',
              entry_kind: 'chat_message',
              feature_type: 'summarize',
              content: 'Summarize the document.',
            },
            {
              entry_id: 'thread_cancel',
              interaction_id: 'ai_cancel',
              message_role: 'assistant',
              entry_kind: 'chat_message',
              feature_type: 'summarize',
              status: 'failed',
              content: 'Partial answer',
              review_only: true,
              suggestion: null,
            },
          ])
        );
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_cancel',
            entry_kind: 'chat_message',
            feature_type: 'summarize',
            status: 'failed',
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_cancel') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_cancel',
            entry_kind: 'chat_message',
            feature_type: 'summarize',
            status: 'failed',
            completed_at: '2026-01-01T00:00:01Z',
            suggestion: null,
          })
        );
      }

      if (path === '/ai/interactions/ai_cancel/cancel') {
        return Promise.resolve({
          interaction_id: 'ai_cancel',
          status: 'failed',
          canceled_at: '2026-01-01T00:00:01Z',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockImplementation((path, options) =>
      Promise.resolve(
        createSseResponse(
          [
            {
              type: 'meta',
              data: {
                interaction_id: 'ai_cancel',
                status: 'processing',
                document_id: 1,
                base_revision: 0,
                created_at: '2026-01-01T00:00:00Z',
              },
            },
            {
              type: 'chunk',
              data: {
                interaction_id: 'ai_cancel',
                delta: 'Partial answer',
                output: 'Partial answer',
              },
            },
            {
              type: 'chunk',
              data: {
                interaction_id: 'ai_cancel',
                delta: ' that should not finish',
                output: 'Partial answer that should not finish',
              },
            },
          ],
          { delayMs: 50, signal: options.signal }
        )
      )
    );

    renderEditorPage();

    await screen.findByText('Draft');
    await clickAiShortcut('Summarize');

    await screen.findByText('Partial answer');
    fireEvent.click(screen.getByRole('button', { name: 'Stop AI generation' }));

    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/ai/interactions/ai_cancel/cancel',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    expect(screen.getByText('AI generation canceled.')).toBeInTheDocument();
    expect(screen.getByText('Partial answer')).toBeInTheDocument();
    expect(
      screen.getByText('Partial output was kept after the AI stream was interrupted.')
    ).toBeInTheDocument();
  });

  it('preserves partial streamed output when the AI stream fails mid-response', async () => {
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve(
          buildThreadEntries([
            {
              entry_id: 'thread_user_error',
              message_role: 'user',
              entry_kind: 'chat_message',
              feature_type: 'summarize',
              content: 'Summarize the document.',
            },
            {
              entry_id: 'thread_error',
              interaction_id: 'ai_error',
              message_role: 'assistant',
              entry_kind: 'chat_message',
              feature_type: 'summarize',
              status: 'failed',
              content: 'Partial streamed output',
              review_only: true,
              suggestion: null,
            },
          ])
        );
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_error',
            entry_kind: 'chat_message',
            feature_type: 'summarize',
            status: 'failed',
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_error') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_error',
            entry_kind: 'chat_message',
            feature_type: 'summarize',
            status: 'failed',
            completed_at: '2026-01-01T00:00:01Z',
            suggestion: null,
          })
        );
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_error',
            status: 'processing',
            document_id: 1,
            base_revision: 0,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_error',
            delta: 'Partial streamed output',
            output: 'Partial streamed output',
          },
        },
        {
          type: 'error',
          data: {
            interaction_id: 'ai_error',
            message: 'Provider stream broke mid-response',
          },
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    await clickAiShortcut('Summarize');

    await screen.findByText('Partial streamed output');
    await waitFor(() => {
      expect(
        screen.getByText('Provider stream broke mid-response')
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText('Partial output was kept after the AI stream was interrupted.')
    ).toBeInTheDocument();
  });

  it('shows document-level AI history in the sidebar', async () => {
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/ai/interactions' && !options) {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_hist_1',
            feature_type: 'rewrite',
            scope_type: 'selection',
            outcome: 'accepted',
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_hist_1') {
        return Promise.resolve({
          ...buildInteractionDetail({
            interaction_id: 'ai_hist_1',
            feature_type: 'rewrite',
            scope_type: 'selection',
            outcome: 'accepted',
            outcome_recorded_at: '2026-01-01T00:00:02Z',
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Make this clearer',
            suggestion: {
              suggestion_id: 'sug_hist_1',
              generated_output: 'A clearer version of the selected sentence.',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
          interaction_id: 'ai_hist_1',
          rendered_prompt: 'FEATURE_TYPE:\nrewrite\n\nUSER_INSTRUCTION:\nMake this clearer',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('tab', { name: 'AI History' }));

    await screen.findByText(
      'Audit completed AI interactions for this document, including chat replies and suggestion outcomes.'
    );
    expect(screen.getAllByText('Rewrite').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('A clearer version of the selected sentence.')).toBeInTheDocument();
    expect(screen.getByText(/FEATURE_TYPE:/)).toBeInTheDocument();
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/content') {
        return Promise.resolve({
          document_id: 1,
          latest_version_id: 10,
          line_spacing: 1.15,
          revision: 1,
          saved_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_undo_doc',
            source_revision: 1,
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_undo_doc') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_undo_doc',
            source_revision: 1,
            base_revision: 1,
            selected_text_snapshot: 'Updated body',
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_undo_doc',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
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

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_undo_doc',
            status: 'processing',
            document_id: 1,
            base_revision: 1,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_undo_doc',
            delta: 'AI rewritten document',
            output: 'AI rewritten document',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_undo_doc',
            source_revision: 1,
            base_revision: 1,
            selected_text_snapshot: 'Updated body',
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_undo_doc',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Make it clearer' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('AI rewritten document');
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

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
        line_spacing: 1.15,
        revision: 1,
        saved_at: '2026-01-01T00:00:00Z',
      },
      {
        document_id: 1,
        latest_version_id: 11,
        line_spacing: 1.15,
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/content') {
        return Promise.resolve(saveResponses.shift());
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_undo_sel',
            scope_type: 'selection',
            source_revision: 1,
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_undo_sel') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_undo_sel',
            scope_type: 'selection',
            source_revision: 1,
            base_revision: 1,
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Tighten this section',
            suggestion: {
              suggestion_id: 'sug_undo_sel',
              generated_output: 'Sharper text',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
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

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_undo_sel',
            status: 'processing',
            document_id: 1,
            base_revision: 1,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_undo_sel',
            delta: 'Sharper text',
            output: 'Sharper text',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_undo_sel',
            scope_type: 'selection',
            source_revision: 1,
            base_revision: 1,
            selected_range: { start: 4, end: 21 },
            selected_text_snapshot: 'Selected sentence',
            user_instruction: 'Tighten this section',
            suggestion: {
              suggestion_id: 'sug_undo_sel',
              generated_output: 'Sharper text',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Tighten this section' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('Sharper text');
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

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
          line_spacing: 1.15,
          revision: 1,
          saved_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_clear_edit',
            source_revision: 1,
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_clear_edit') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_clear_edit',
            source_revision: 1,
            base_revision: 1,
            selected_text_snapshot: 'Updated body',
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_clear_edit',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
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

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_clear_edit',
            status: 'processing',
            document_id: 1,
            base_revision: 1,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_clear_edit',
            delta: 'AI rewritten document',
            output: 'AI rewritten document',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_clear_edit',
            source_revision: 1,
            base_revision: 1,
            selected_text_snapshot: 'Updated body',
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_clear_edit',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Make it clearer' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('AI rewritten document');
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Undo AI' })).toBeInTheDocument();
    }, { timeout: 3000 });
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/content') {
        return Promise.resolve({
          document_id: 1,
          latest_version_id: 10,
          line_spacing: 1.15,
          revision: 1,
          saved_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve([
          buildHistoryItem({
            interaction_id: 'ai_clear_title',
            source_revision: 1,
          }),
        ]);
      }

      if (path === '/ai/interactions/ai_clear_title') {
        return Promise.resolve(
          buildInteractionDetail({
            interaction_id: 'ai_clear_title',
            source_revision: 1,
            base_revision: 1,
            selected_text_snapshot: 'Updated body',
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_clear_title',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          })
        );
      }

      if (path === '/documents/1' && options?.method === 'PATCH') {
        return Promise.resolve({
          document_id: 1,
          title: 'Renamed draft',
          ai_enabled: true,
          line_spacing: 1.15,
          updated_at: '2026-01-01T00:00:03Z',
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

    api.apiFetch.mockResolvedValue(
      createSseResponse([
        {
          type: 'meta',
          data: {
            interaction_id: 'ai_clear_title',
            status: 'processing',
            document_id: 1,
            base_revision: 1,
            created_at: '2026-01-01T00:00:00Z',
          },
        },
        {
          type: 'chunk',
          data: {
            interaction_id: 'ai_clear_title',
            delta: 'AI rewritten document',
            output: 'AI rewritten document',
          },
        },
        {
          type: 'complete',
          data: buildInteractionDetail({
            interaction_id: 'ai_clear_title',
            source_revision: 1,
            base_revision: 1,
            selected_text_snapshot: 'Updated body',
            user_instruction: 'Make it clearer',
            suggestion: {
              suggestion_id: 'sug_clear_title',
              generated_output: 'AI rewritten document',
              model_name: 'local-rewrite-fallback',
              stale: false,
              usage: null,
            },
          }),
        },
      ])
    );

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: 'Make it clearer' },
    });
    await clickAiShortcut('Rewrite');

    await screen.findByText('AI rewritten document');
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

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
    const messageInput = screen.getByLabelText('Message');

    fireEvent.change(messageInput, {
      target: { value: 'Call out action items' },
    });
    fireEvent.click(screen.getByRole('button', { name: /close ai sidebar/i }));

    expect(sidebar).toHaveAttribute('data-state', 'closed');
    expect(screen.getByRole('button', { name: /show ai/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /show ai/i }));

    expect(sidebar).toHaveAttribute('data-state', 'open');
    expect(screen.getByLabelText('Message')).toHaveValue('Call out action items');
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');

    expect(
      screen.getByText('Your role can view this document, but it cannot run AI actions.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /shortcuts/i })).toBeDisabled();
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

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');

    expect(screen.getByText('AI is disabled for this document.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /shortcuts/i })).toBeDisabled();
  });

  it('clears the AI chat and the AI history together', async () => {
    let threadEntries = buildThreadEntries([
      {
        entry_id: 'thread_user_clear',
        message_role: 'user',
        entry_kind: 'chat_message',
        feature_type: 'chat_assistant',
        content: 'Help me tighten this paragraph.',
      },
      {
        entry_id: 'thread_assistant_clear',
        interaction_id: 'ai_clear_chat',
        message_role: 'assistant',
        entry_kind: 'chat_message',
        feature_type: 'chat_assistant',
        status: 'completed',
        content: 'Here is a tighter version.',
        review_only: true,
        suggestion: null,
      },
    ]);
    let historyItems = [
      buildHistoryItem({
        interaction_id: 'ai_clear_chat',
        entry_kind: 'chat_message',
        feature_type: 'chat_assistant',
        status: 'completed',
      }),
    ];

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

      if (path === '/documents/1/ai/chat/thread' && !options) {
        return Promise.resolve(threadEntries);
      }

      if (path === '/documents/1/ai/chat/thread' && options?.method === 'DELETE') {
        threadEntries = [];
        historyItems = [];
        return Promise.resolve({
          document_id: 1,
          deleted_entry_count: 2,
          cleared_at: '2026-01-01T00:00:00Z',
        });
      }

      if (path === '/documents/1/ai/interactions') {
        return Promise.resolve(historyItems);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Here is a tighter version.');

    fireEvent.click(screen.getByRole('button', { name: 'Clear AI chat' }));

    await screen.findByText('AI chat cleared.');
    expect(screen.queryByText('Here is a tighter version.')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'AI History' }));
    await screen.findByText('No AI interactions yet.');
  });

  it('lets the AI sidebar be resized wider on desktop', async () => {
    const originalWidth = window.innerWidth;
    window.innerWidth = 1400;

    renderEditorPage();

    await screen.findByText('Draft');

    const sidebar = screen.getByLabelText('AI Assistant');
    const resizeHandle = screen.getByRole('separator', { name: 'Resize AI sidebar' });

    expect(sidebar).toHaveStyle({
      '--ai-sidebar-width': '360px',
      '--ai-sidebar-min-width': '360px',
    });

    fireEvent.pointerDown(resizeHandle, { clientX: 1180 });
    fireEvent.pointerMove(window, { clientX: 1040 });
    fireEvent.pointerUp(window);

    await waitFor(() => {
      expect(sidebar).toHaveStyle({
        '--ai-sidebar-width': '500px',
        '--ai-sidebar-min-width': '500px',
      });
    });

    window.innerWidth = originalWidth;
  });

  it('shows version history and restores an older version', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    const documentResponses = [
      buildDocument(),
      buildDocument({
        current_content: '<p>Restored body</p>',
        line_spacing: 2,
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
            save_source: 'manual',
          },
          {
            version_id: 4,
            version_number: 1,
            created_by: 1,
            created_at: '2026-01-01T00:00:00Z',
            is_restore_version: false,
            save_source: 'manual',
          },
        ]);
      }

      if (path === '/documents/1/content') {
        return Promise.resolve({
          document_id: 1,
          latest_version_id: 10,
          line_spacing: 1.15,
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
    expect(screen.getByRole('dialog', { name: 'Version history' })).toHaveClass('modal-tall');
    expect(
      screen.getByText(
        'Review previous saved snapshots and restore an earlier state without deleting later history.'
      ).closest('.modal-scroll')
    ).not.toBeNull();
    expect(screen.getByText('Version 1')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'Restore' })[1]);

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Restored body');
    });
    expect(screen.getByTestId('editor-line-spacing')).toHaveTextContent('2');

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/versions/4/restore',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });

  it('refreshes the latest realtime revision before restoring a version', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    globalThis.WebSocket = MockWebSocket;

    const documentResponses = [
      buildDocument({
        revision: 2,
        latest_version_id: 11,
      }),
      buildDocument({
        current_content: '<p>Local collaborative body</p>',
        revision: 3,
        latest_version_id: 12,
      }),
      buildDocument({
        current_content: '<p>Restored body</p>',
        line_spacing: 2,
        revision: 4,
        latest_version_id: 13,
      }),
    ];
    const staleSaveError = Object.assign(
      new Error('The document revision is stale. Refresh and retry.'),
      { status: 409 }
    );

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(documentResponses.shift() ?? buildDocument({
          current_content: '<p>Restored body</p>',
          line_spacing: 2,
          revision: 4,
          latest_version_id: 13,
        }));
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 2,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
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
            save_source: 'manual',
          },
          {
            version_id: 4,
            version_number: 1,
            created_by: 1,
            created_at: '2026-01-01T00:00:00Z',
            is_restore_version: false,
            save_source: 'manual',
          },
        ]);
      }

      if (path === '/documents/1/content') {
        return Promise.reject(staleSaveError);
      }

      if (path === '/documents/1/versions/4/restore') {
        return Promise.resolve({
          document_id: 1,
          restored_from_version_id: 4,
          new_version_id: 13,
          message: 'Version restored as a new version entry.',
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));

    await act(async () => {
      MockWebSocket.instances[0].emit({
        type: 'steps_applied',
        actor_user_id: 1,
        actor_display_name: 'Owner',
        collab_version: 1,
        steps: [{ mockHtml: '<p>Local collaborative body</p>' }],
        client_ids: ['client-1'],
        content: '<p>Local collaborative body</p>',
        line_spacing: 1.15,
        batch: {
          batch_id: 'batch-1',
          version: 0,
          client_id: 'client-1',
          affected_range: { start: 4, end: 21 },
          candidate_content_snapshot: 'Local collaborative body',
          exact_text_snapshot: 'Initial body',
          prefix_context: 'Before',
          suffix_context: 'After',
          actor_user_id: 1,
          actor_display_name: 'Owner',
        },
      });
    });

    expect(screen.getByText('Saved')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    await screen.findByText('Version history');
    fireEvent.click(screen.getAllByRole('button', { name: 'Restore' })[0]);

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Restored body');
    });
    expect(screen.getByTestId('editor-line-spacing')).toHaveTextContent('2');

    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/content',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          content: '<p>Local collaborative body</p>',
          base_revision: 2,
          line_spacing: 1.15,
          save_source: 'manual',
        }),
      })
    );
    expect(api.apiJSON).toHaveBeenCalledWith(
      '/documents/1/versions/4/restore',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });

  it('hides autosaves in version history by default and can reveal them', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(
          buildDocument({
            revision: 3,
            latest_version_id: 7,
          })
        );
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
            version_id: 7,
            version_number: 3,
            created_by: 1,
            created_at: '2026-01-01T00:20:00Z',
            is_restore_version: false,
            save_source: 'autosave',
          },
          {
            version_id: 6,
            version_number: 2,
            created_by: 1,
            created_at: '2026-01-01T00:10:00Z',
            is_restore_version: false,
            save_source: 'manual',
          },
          {
            version_id: 5,
            version_number: 1,
            created_by: 1,
            created_at: '2026-01-01T00:00:00Z',
            is_restore_version: true,
            save_source: 'restore',
          },
        ]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    await screen.findByText('Version history');
    expect(screen.queryByText('Version 3')).not.toBeInTheDocument();
    expect(screen.getByText('Version 2')).toBeInTheDocument();
    expect(screen.getByText('Version 1')).toBeInTheDocument();
    expect(screen.getByText('Manual save')).toBeInTheDocument();
    expect(screen.getByText('Restore', { selector: '.history-badge' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Show autosaves' }));

    expect(await screen.findByText('Version 3')).toBeInTheDocument();
    expect(screen.getByText('Autosave')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hide autosaves' })).toBeInTheDocument();
  });

  it('shows the latest autosave with helper copy when autosaves are the only history', async () => {
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(
          buildDocument({
            revision: 2,
            latest_version_id: 4,
          })
        );
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
            version_id: 4,
            version_number: 2,
            created_by: 1,
            created_at: '2026-01-01T00:10:00Z',
            is_restore_version: false,
            save_source: 'autosave',
          },
          {
            version_id: 3,
            version_number: 1,
            created_by: 1,
            created_at: '2026-01-01T00:00:00Z',
            is_restore_version: false,
            save_source: 'autosave',
          },
        ]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    await screen.findByText('Only autosave snapshots exist so far. Open autosaves if you want to browse the full background-save history.');
    expect(screen.getByText('Version 2')).toBeInTheDocument();
    expect(screen.queryByText('Version 1')).not.toBeInTheDocument();
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
          exported_content: '<!doctype html><html><body><article><p>Initial body</p></article></body></html>',
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
    const exportBlob = createObjectURL.mock.calls[0][0];
    expect(exportBlob).toBeInstanceOf(Blob);
    await expect(exportBlob.text()).resolves.toContain('<article><p>Initial body</p></article>');
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:export');
  });

  it('connects to realtime collaboration and applies remote updates', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/ai/chat/thread') {
        return Promise.resolve([]);
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [
            {
              user_id: 1,
              display_name: 'Owner',
              session_id: 'sess_1',
              last_known_revision: 0,
              joined_at: '2026-01-01T00:00:00Z',
              last_seen_at: '2026-01-01T00:00:00Z',
            },
          ],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'session_joined',
        session_id: 'sess_1',
        document_id: 1,
        revision: 0,
        content: '<p>Initial body</p>',
        line_spacing: 1.15,
        collab_version: 0,
        presence: [
          {
            user_id: 1,
            display_name: 'Owner',
            session_id: 'sess_1',
            last_known_revision: 0,
            joined_at: '2026-01-01T00:00:00Z',
            last_seen_at: '2026-01-01T00:00:00Z',
            typing: false,
          },
        ],
      });
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Live:\s*You$/i })).toBeInTheDocument();
    });

    const socket = MockWebSocket.instances[0];
    expect(socket.url).toContain('/documents/1/sessions/sess_1/ws');
    expect(socket.url).toContain('session_token=socket-token');
    expect(socket.url).toContain('access_token=test-token');

    act(() => {
      socket.emit({
        type: 'presence_snapshot',
        presence: [
          {
            user_id: 1,
            display_name: 'Owner',
            session_id: 'sess_1',
            last_known_revision: 0,
            joined_at: '2026-01-01T00:00:00Z',
            last_seen_at: '2026-01-01T00:00:00Z',
            typing: false,
          },
          {
            user_id: 2,
            display_name: 'Editor',
            session_id: 'sess_2',
            last_known_revision: 0,
            joined_at: '2026-01-01T00:00:00Z',
            last_seen_at: '2026-01-01T00:00:00Z',
            typing: true,
          },
        ],
      });
    });

    await waitFor(() => {
      expect(screen.queryByText(/editor typing…/i)).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /live:\s*2 online/i }));
    const liveList = screen.getByRole('list', { name: /live collaborators/i });
    expect(within(liveList).getByText('Owner')).toHaveStyle({ color: '#db2777' });
    expect(within(liveList).getByText('Editor')).toHaveStyle({ color: '#0f766e' });
    expect(within(liveList).getByText('typing…')).toBeInTheDocument();

    act(() => {
      socket.emit({
        type: 'content_updated',
        document_id: 1,
        content: '<p>Remote body</p>',
        line_spacing: 1.5,
        revision: 1,
        latest_version_id: 11,
        actor_user_id: 2,
        actor_display_name: 'Editor',
        saved_at: '2026-01-01T00:00:05Z',
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Remote body');
    });
    expect(screen.getByTestId('editor-line-spacing')).toHaveTextContent('1.5');
  });

  it('sends local collaborative steps over the realtime socket', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));

    expect(MockWebSocket.instances[0].sentMessages).toContainEqual(
      expect.objectContaining({
        type: 'step_update',
        version: 0,
        client_id: 'client-1',
        steps: [{ mockStep: true, mockHtml: '<p>Local collaborative body</p>' }],
        content: '<p>Local collaborative body</p>',
        line_spacing: 1.15,
        affected_range: expect.objectContaining({
          start: expect.any(Number),
          end: expect.any(Number),
        }),
      })
    );
  });

  it('does not resend overlapping local step batches while waiting for confirmation', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));
    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));

    const sentStepUpdates = MockWebSocket.instances[0].sentMessages.filter(
      (message) => message.type === 'step_update'
    );

    expect(sentStepUpdates).toHaveLength(1);
  });

  it('resumes sending local step batches after the previous batch is confirmed', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));

    await act(async () => {
      MockWebSocket.instances[0].emit({
        type: 'steps_applied',
        actor_user_id: 1,
        actor_display_name: 'Owner',
        collab_version: 1,
        steps: [{ mockHtml: '<p>Local collaborative body</p>' }],
        client_ids: ['client-1'],
        content: '<p>Local collaborative body</p>',
        line_spacing: 1.15,
        batch: {
          batch_id: 'batch-1',
          version: 0,
          client_id: 'client-1',
          affected_range: { start: 4, end: 21 },
          candidate_content_snapshot: 'Local collaborative body',
          exact_text_snapshot: 'Initial body',
          prefix_context: 'Before',
          suffix_context: 'After',
          actor_user_id: 1,
          actor_display_name: 'Owner',
        },
      });
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));

    await waitFor(() => {
      const sentStepUpdates = MockWebSocket.instances[0].sentMessages.filter(
        (message) => message.type === 'step_update'
      );

      expect(sentStepUpdates).toHaveLength(2);
      expect(sentStepUpdates[1]).toEqual(
        expect.objectContaining({
          version: 1,
        })
      );
    });
  });

  it('publishes local selection awareness over the realtime socket', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    vi.useFakeTimers();

    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(140);
    });

    expect(MockWebSocket.instances[0].sentMessages).toContainEqual(
      expect.objectContaining({
        type: 'selection_update',
        from: 4,
        to: 21,
        direction: 'forward',
        collab_version: 0,
      })
    );
  });

  it('keeps the selected-text awareness update when a cursor collapse follows immediately', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    vi.useFakeTimers();

    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move cursor' }));

    expect(
      MockWebSocket.instances[0].sentMessages.filter(
        (message) => message.type === 'selection_update'
      )
    ).toEqual([]);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(MockWebSocket.instances[0].sentMessages).toContainEqual(
      expect.objectContaining({
        type: 'selection_update',
        from: 8,
        to: 8,
        direction: 'forward',
        collab_version: 0,
      })
    );
  });

  it('re-publishes the current stable selection after the collaboration version changes', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    vi.useFakeTimers();

    fireEvent.click(screen.getByRole('button', { name: 'Select text' }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(140);
    });

    const selectionMessagesBeforeVersionChange = MockWebSocket.instances[0].sentMessages.filter(
      (message) => message.type === 'selection_update'
    );
    expect(selectionMessagesBeforeVersionChange).toHaveLength(1);

    MockWebSocket.instances[0].emit({
      type: 'steps_applied',
      actor_user_id: 2,
      actor_display_name: 'Editor',
      collab_version: 1,
      steps: [{ mockHtml: '<p>Remote collaborative body</p>' }],
      client_ids: ['remote-client'],
      content: '<p>Remote collaborative body</p>',
      line_spacing: 1.15,
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });

    const selectionMessagesAfterVersionChange = MockWebSocket.instances[0].sentMessages.filter(
      (message) => message.type === 'selection_update'
    );
    expect(selectionMessagesAfterVersionChange).toHaveLength(2);
    expect(selectionMessagesAfterVersionChange.at(-1)).toEqual(
      expect.objectContaining({
        type: 'selection_update',
        from: 4,
        to: 21,
        direction: 'forward',
        collab_version: 1,
      })
    );
  });

  it('clears remote awareness while local collaboration steps are in flight', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'session_joined',
        session_id: 'sess_1',
        document_id: 1,
        revision: 0,
        content: '<p>Initial body</p>',
        line_spacing: 1.15,
        collab_version: 0,
        presence: [
          {
            user_id: 1,
            display_name: 'Owner',
            session_id: 'sess_1',
            last_known_revision: 0,
            joined_at: '2026-01-01T00:00:00Z',
            last_seen_at: '2026-01-01T00:00:00Z',
            typing: false,
          },
          {
            user_id: 2,
            display_name: 'Editor',
            session_id: 'sess_2',
            last_known_revision: 0,
            joined_at: '2026-01-01T00:00:00Z',
            last_seen_at: '2026-01-01T00:00:00Z',
            typing: false,
          },
        ],
        awareness: [],
      });
    });

    fireEvent.click(screen.getByRole('button', { name: 'Move cursor' }));

    await waitFor(() => {
      expect(MockWebSocket.instances[0].sentMessages).toContainEqual(
        expect.objectContaining({
          type: 'selection_update',
          from: 8,
          to: 8,
          direction: 'forward',
          collab_version: 0,
        })
      );
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'awareness_snapshot',
        collaborators: [
          {
            user_id: 2,
            display_name: 'Editor',
            session_id: 'sess_2',
            selection_from: 7,
            selection_to: 7,
            selection_direction: 'forward',
            collab_version: 0,
            color_token: 'presence-2',
            last_selection_at: new Date().toISOString(),
          },
        ],
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId('remote-awareness')).toHaveTextContent('Editor:7-7');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send collaboration step' }));

    expect(MockWebSocket.instances[0].sentMessages).toContainEqual(
      expect.objectContaining({
        type: 'selection_clear',
      })
    );

    await waitFor(() => {
      expect(screen.getByTestId('remote-awareness')).toBeEmptyDOMElement();
    });
  });

  it('re-publishes the current cursor awareness after the collaboration version changes', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Move cursor' }));

    await waitFor(() => {
      expect(MockWebSocket.instances[0].sentMessages).toContainEqual(
        expect.objectContaining({
          type: 'selection_update',
          from: 8,
          to: 8,
          direction: 'forward',
          collab_version: 0,
        })
      );
    });

    MockWebSocket.instances[0].emit({
      type: 'steps_applied',
      actor_user_id: 2,
      actor_display_name: 'Editor',
      collab_version: 1,
      steps: [{ mockHtml: '<p>Remote collaborative body</p>' }],
      client_ids: ['remote-client'],
      content: '<p>Remote collaborative body</p>',
      line_spacing: 1.15,
    });

    await waitFor(() => {
      expect(MockWebSocket.instances[0].sentMessages).toContainEqual(
        expect.objectContaining({
          type: 'selection_update',
          from: 8,
          to: 8,
          direction: 'forward',
          collab_version: 1,
        })
      );
    });
  });

  it('applies remote collaborative steps without forcing a snapshot overwrite', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'steps_applied',
        document_id: 1,
        steps: [{ mockHtml: '<p>Remote collaborative body</p>' }],
        client_ids: ['client-2'],
        collab_version: 1,
        content: '<p>Remote collaborative body</p>',
        line_spacing: 1.15,
        actor_user_id: 2,
        actor_display_name: 'Editor',
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId('editor-content')).toHaveTextContent('Remote collaborative body');
    });
    expect(screen.queryByText('Remote changes need review.')).not.toBeInTheDocument();
  });

  it('restores editor focus after a realtime resync rebuild', async () => {
    globalThis.WebSocket = MockWebSocket;
    mockEditorCaptureViewState.mockReturnValue({
      hasFocus: true,
      selection: { from: 6, to: 6 },
    });

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'steps_resync',
        document_id: 1,
        collab_version: 2,
        full_reset: true,
        content: '<p>Resynced body</p>',
        line_spacing: 1.15,
        revision: 2,
        latest_version_id: 11,
      });
    });

    await waitFor(() => {
      expect(screen.getByText('Realtime re-synced with the latest collaboration state.')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(mockEditorRestoreViewState).toHaveBeenCalledWith({
        hasFocus: true,
        selection: { from: 6, to: 6 },
      });
    });
  });

  it('renders remote awareness from websocket snapshots and clears it when offline', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'session_joined',
        session_id: 'sess_1',
        document_id: 1,
        revision: 0,
        content: '<p>Initial body</p>',
        line_spacing: 1.15,
        collab_version: 0,
        presence: [
          {
            user_id: 1,
            display_name: 'Owner',
            session_id: 'sess_1',
            last_known_revision: 0,
            joined_at: '2026-01-01T00:00:00Z',
            last_seen_at: '2026-01-01T00:00:00Z',
            typing: false,
          },
        ],
        awareness: [],
      });
      MockWebSocket.instances[0].emit({
        type: 'awareness_snapshot',
        collaborators: [
          {
            user_id: 2,
            display_name: 'Editor',
            session_id: 'sess_2',
            selection_from: 7,
            selection_to: 7,
            selection_direction: 'forward',
            collab_version: 0,
            color_token: 'presence-2',
            last_selection_at: new Date().toISOString(),
          },
        ],
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId('remote-awareness')).toHaveTextContent('Editor:7-7');
    });

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 1_650));
    });

    await waitFor(() => {
      expect(screen.getByTestId('remote-awareness')).toBeEmptyDOMElement();
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'awareness_snapshot',
        collaborators: [
          {
            user_id: 2,
            display_name: 'Editor',
            session_id: 'sess_2',
            selection_from: 7,
            selection_to: 12,
            selection_direction: 'forward',
            collab_version: 0,
            color_token: 'presence-2',
            last_selection_at: new Date().toISOString(),
          },
        ],
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId('remote-awareness')).toHaveTextContent('Editor:7-12');
    });

    act(() => {
      MockWebSocket.instances[0].close();
    });

    await waitFor(() => {
      expect(screen.getByTestId('remote-awareness')).toBeEmptyDOMElement();
    });
  });

  it('shows a conflict resolution tray when overlapping edits are preserved', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      if (path === '/documents/1/conflicts') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'conflict_created',
        conflict: {
          conflict_id: 77,
          conflict_key: 'conflict:1:batch-1:batch-2',
          status: 'open',
          stale: false,
          source_revision: 0,
          source_collab_version: 0,
          anchor_range: { start: 4, end: 21 },
          exact_text_snapshot: 'Selected sentence',
          prefix_context: 'Before',
          suffix_context: 'After',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          resolved_at: null,
          resolved_content: null,
          candidates: [
            {
              candidate_id: 1,
              user_id: 1,
              user_display_name: 'Owner',
              batch_id: 'batch-1',
              client_id: 'client-1',
              range: { start: 4, end: 21 },
              candidate_content_snapshot: 'My local revision',
              exact_text_snapshot: 'Selected sentence',
              prefix_context: 'Before',
              suffix_context: 'After',
              created_at: '2026-01-01T00:00:00Z',
            },
            {
              candidate_id: 2,
              user_id: 2,
              user_display_name: 'Editor',
              batch_id: 'batch-2',
              client_id: 'client-2',
              range: { start: 4, end: 21 },
              candidate_content_snapshot: 'Their remote revision',
              exact_text_snapshot: 'Selected sentence',
              prefix_context: 'Before',
              suffix_context: 'After',
              created_at: '2026-01-01T00:00:01Z',
            },
          ],
        },
      });
    });

    expect(await screen.findByText('Resolve overlapping edits')).toBeInTheDocument();
    expect(screen.getAllByText('My local revision').length).toBeGreaterThan(0);
    expect(screen.getByText('Their remote revision')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: "Use Editor's version" })).toBeInTheDocument();
  });

  it('shows conflict state to viewers without resolution actions', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument({
          owner_user_id: 2,
          collaborators: [{ user_id: 1, role: 'viewer' }],
        }));
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Viewer',
          email: 'viewer@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          collab_version: 0,
          content_snapshot: '<p>Initial body</p>',
          line_spacing_snapshot: 1.15,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      if (path === '/documents/1/conflicts') {
        return Promise.resolve([]);
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'conflict_created',
        conflict: {
          conflict_id: 88,
          conflict_key: 'conflict:1:batch-3:batch-4',
          status: 'open',
          stale: false,
          source_revision: 0,
          source_collab_version: 0,
          anchor_range: { start: 2, end: 8 },
          exact_text_snapshot: 'body',
          prefix_context: '',
          suffix_context: '',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          resolved_at: null,
          resolved_content: null,
          candidates: [],
        },
      });
    });

    expect(await screen.findByText(/only owners and editors can resolve them/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save resolution' })).not.toBeInTheDocument();
  });

  it('uses the latest refreshed access token when opening the realtime socket', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        localStorage.setItem('access_token', 'fresh-token');
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    expect(MockWebSocket.instances[0].url).toContain('access_token=fresh-token');
    expect(MockWebSocket.instances[0].url).not.toContain('access_token=test-token');
  });

  it('hides the status pill when realtime is connected and only the current user is present', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [
            {
              user_id: 1,
              display_name: 'Owner',
              session_id: 'sess_1',
              last_known_revision: 0,
              joined_at: '2026-01-01T00:00:00Z',
              last_seen_at: '2026-01-01T00:00:00Z',
            },
          ],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    act(() => {
      MockWebSocket.instances[0].emit({
        type: 'session_joined',
        session_id: 'sess_1',
        document_id: 1,
        revision: 0,
        content: '<p>Initial body</p>',
        line_spacing: 1.15,
        collab_version: 0,
        presence: [
          {
            user_id: 1,
            display_name: 'Owner',
            session_id: 'sess_1',
            last_known_revision: 0,
            joined_at: '2026-01-01T00:00:00Z',
            last_seen_at: '2026-01-01T00:00:00Z',
            typing: false,
          },
        ],
      });
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Live:\s*You$/i })).toBeInTheDocument();
    });

    expect(screen.queryByText('Realtime connected')).not.toBeInTheDocument();
    expect(screen.queryByText(/Only you are here right now/i)).not.toBeInTheDocument();
  });

  it('transitions to reconnecting when the realtime socket closes unexpectedly', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].close();
    });

    await screen.findByText('Reconnecting…');
    expect(
      screen.getByText('Realtime disconnected. Trying to reconnect while local saves continue.')
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Live:/i)).not.toBeInTheDocument();
  });

  it('re-bootstraps after a realtime auth rejection and keeps stale live presence hidden', async () => {
    globalThis.WebSocket = MockWebSocket;

    let sessionCallCount = 0;
    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        sessionCallCount += 1;
        return Promise.resolve({
          session_id: `sess_${sessionCallCount}`,
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          realtime_url: `/v1/documents/1/sessions/sess_${sessionCallCount}/ws`,
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0].close({
        code: 4401,
        reason: 'Invalid realtime session.',
      });
    });

    await screen.findByText('Reconnecting…');
    expect(screen.getByText('Invalid realtime session.')).toBeInTheDocument();
    expect(screen.queryByText(/^Live:/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(api.apiJSON).toHaveBeenCalledWith(
        '/documents/1/sessions',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  it('keeps a local draft when a remote conflict arrives and can resend it', async () => {
    globalThis.WebSocket = MockWebSocket;

    api.apiJSON.mockImplementation((path, options) => {
      if (path === '/documents/1' && !options) {
        return Promise.resolve(buildDocument());
      }

      if (path === '/auth/me') {
        return Promise.resolve({
          user_id: 1,
          display_name: 'Owner',
          email: 'user@example.com',
        });
      }

      if (path === '/documents/1/sessions') {
        return Promise.resolve({
          session_id: 'sess_1',
          session_token: 'socket-token',
          document_id: 1,
          revision: 0,
          realtime_url: '/v1/documents/1/sessions/sess_1/ws',
          resync_required: false,
          missed_revision_count: 0,
          active_collaborators: [],
        });
      }

      throw new Error(`Unexpected apiJSON call: ${path}`);
    });

    renderEditorPage();

    await screen.findByText('Draft');
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    const socket = MockWebSocket.instances[0];
    fireEvent.click(screen.getByRole('button', { name: 'Edit document' }));

    act(() => {
      socket.emit({
        type: 'content_updated',
        document_id: 1,
        content: '<p>Remote body</p>',
        line_spacing: 1.15,
        revision: 2,
        latest_version_id: 12,
        actor_user_id: 2,
        actor_display_name: 'Editor',
        saved_at: '2026-01-01T00:00:05Z',
      });
    });

    await screen.findByText('Remote changes need review.');
    fireEvent.click(screen.getByRole('button', { name: 'Keep my draft' }));

    expect(socket.sentMessages).toContainEqual({
      type: 'content_update',
      content: '<p>Updated body</p>',
      line_spacing: 1.15,
      base_revision: 2,
      save_source: 'autosave',
    });
  });
});
