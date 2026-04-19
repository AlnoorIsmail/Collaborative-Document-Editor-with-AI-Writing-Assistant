import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, apiJSON, getErrorMessage } from '../api';

const QUICK_ACTIONS = [
  { value: 'summarize', label: 'Summarize', reviewOnly: true },
  { value: 'rewrite', label: 'Rewrite', reviewOnly: false },
  { value: 'translate', label: 'Translate', reviewOnly: false },
  { value: 'grammar_fix', label: 'Fix grammar', reviewOnly: false },
  { value: 'expand', label: 'Expand', reviewOnly: false },
  { value: 'restructure', label: 'Restructure', reviewOnly: false },
];

const DEFAULT_FEATURE_PARAMETERS = {
  summarize: { length: 'medium', format: 'paragraph' },
  rewrite: { tone: 'neutral' },
  translate: {},
  grammar_fix: { style: 'preserve' },
  expand: { detail_level: 'medium' },
  restructure: { structure: 'clear_flow' },
};

const AI_SIDEBAR_WIDTH_STORAGE_KEY = 'ai_sidebar_width';
const AI_SIDEBAR_DEFAULT_WIDTH = 360;
const AI_SIDEBAR_MIN_WIDTH = 320;
const AI_SIDEBAR_MAX_WIDTH = 760;
const AI_SIDEBAR_DESKTOP_BREAKPOINT = 1080;

function makeLocalId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function htmlToPlainText(html) {
  if (!html) {
    return '';
  }

  if (typeof DOMParser !== 'undefined') {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return doc.body.textContent?.replace(/\s+/g, ' ').trim() ?? '';
  }

  return html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

function truncateText(text, limit = 180) {
  const normalized = (text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return '';
  }
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit).trim()}...`;
}

function getUnavailableMessage({ aiEnabled, role }) {
  if (!aiEnabled) {
    return 'AI is disabled for this document.';
  }

  if (role === 'viewer' || role === 'commenter') {
    return 'Your role can view this document, but it cannot run AI actions.';
  }

  return 'AI is not available for your current role.';
}

function parseSseBlock(block) {
  const lines = block
    .split('\n')
    .map((line) => line.trimEnd())
    .filter(Boolean);

  if (lines.length === 0) {
    return null;
  }

  let event = 'message';
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
      continue;
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return {
    event,
    data: JSON.parse(dataLines.join('\n')),
  };
}

async function consumeSseStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let boundaryIndex = buffer.indexOf('\n\n');
    while (boundaryIndex !== -1) {
      const block = buffer.slice(0, boundaryIndex);
      buffer = buffer.slice(boundaryIndex + 2);
      const parsedEvent = parseSseBlock(block);
      if (parsedEvent) {
        await onEvent(parsedEvent);
      }
      boundaryIndex = buffer.indexOf('\n\n');
    }

    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    const parsedEvent = parseSseBlock(buffer);
    if (parsedEvent) {
      await onEvent(parsedEvent);
    }
  }
}

function formatTimestamp(value) {
  if (!value) {
    return 'Unknown time';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatFeatureLabel(featureType) {
  return QUICK_ACTIONS.find((action) => action.value === featureType)?.label
    ?? (featureType === 'chat_assistant' ? 'Chat' : featureType);
}

function formatHistoryStatus(status) {
  if (status === 'processing') {
    return 'Processing';
  }

  if (status === 'failed') {
    return 'Failed';
  }

  return status.charAt(0).toUpperCase() + status.slice(1);
}

function buildContext({ scopeType, documentTitle, documentText }) {
  const contextParts = [];

  if (documentTitle) {
    contextParts.push(`Document title: ${documentTitle}`);
  }

  if (documentText) {
    const excerptLength = scopeType === 'selection' ? 3000 : 1500;
    contextParts.push(`Document context: ${documentText.slice(0, excerptLength)}`);
  }

  if (contextParts.length === 0) {
    return undefined;
  }

  return contextParts.join('\n\n');
}

function buildThreadEntryFromDetail(detail) {
  return {
    entry_id: detail.interaction_id,
    interaction_id: detail.interaction_id,
    conversation_id: detail.conversation_id,
    entry_kind: detail.entry_kind,
    message_role: detail.message_role,
    feature_type: detail.feature_type,
    scope_type: detail.scope_type,
    status: detail.status,
    created_at: detail.created_at,
    source_revision: detail.source_revision ?? detail.base_revision,
    content: detail.suggestion?.generated_output ?? '',
    selected_range: detail.selected_range,
    selected_text_snapshot: detail.selected_text_snapshot,
    surrounding_context: detail.surrounding_context,
    reply_to_interaction_id: detail.reply_to_interaction_id,
    outcome: detail.outcome,
    review_only: detail.entry_kind === 'chat_message' || detail.feature_type === 'summarize',
    suggestion: detail.suggestion ?? null,
  };
}

function buildSelectionSnapshot(entry) {
  if (!entry?.selected_range || !entry?.selected_text_snapshot) {
    return null;
  }

  return {
    text: entry.selected_text_snapshot,
    from: entry.selected_range.start,
    to: entry.selected_range.end,
  };
}

function buildQuickActionInstruction(featureType, scopeType, message, options = {}) {
  const target = scopeType === 'selection' ? 'selected text' : 'document';
  const trimmed = message.trim();
  const targetLanguage = options.targetLanguage?.trim();

  if (featureType === 'summarize') {
    return trimmed || `Summarize the ${target}.`;
  }
  if (featureType === 'translate') {
    return trimmed || (
      targetLanguage
        ? `Translate the ${target} to ${targetLanguage}.`
        : `Translate the ${target}.`
    );
  }
  if (featureType === 'grammar_fix') {
    return trimmed || `Fix grammar in the ${target}.`;
  }
  if (featureType === 'expand') {
    return trimmed || `Expand the ${target}.`;
  }
  if (featureType === 'restructure') {
    return trimmed || `Restructure the ${target}.`;
  }

  return trimmed || `Rewrite the ${target}.`;
}

function buildQuickActionParameters(featureType, options = {}) {
  const targetLanguage = options.targetLanguage?.trim();
  if (featureType === 'translate') {
    return targetLanguage ? { target_language: targetLanguage } : {};
  }

  return {
    ...(DEFAULT_FEATURE_PARAMETERS[featureType] ?? {}),
  };
}

function getSelectedTextSnapshot(scopeType, selectedText) {
  if (scopeType !== 'selection') {
    return undefined;
  }

  return selectedText;
}

export default function AISidebar({
  documentId,
  documentTitle,
  content,
  currentRevision,
  role,
  aiEnabled,
  selection,
  hasUnsavedChanges,
  ensureSavedDocument,
  lastAiUndo,
  applyDocumentSuggestion,
  applyEditedDocumentSuggestion,
  applySelectionSuggestion,
  undoLastAiApply,
  isOpen,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState('chat');
  const [composerMessage, setComposerMessage] = useState('');
  const [attachedSelection, setAttachedSelection] = useState(null);
  const [translateTargetLanguage, setTranslateTargetLanguage] = useState('');
  const [isActionsOpen, setIsActionsOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(AI_SIDEBAR_DEFAULT_WIDTH);
  const [isDesktopViewport, setIsDesktopViewport] = useState(
    typeof window !== 'undefined' ? window.innerWidth > AI_SIDEBAR_DESKTOP_BREAKPOINT : true
  );
  const [isResizing, setIsResizing] = useState(false);
  const [threadEntries, setThreadEntries] = useState([]);
  const [threadLoading, setThreadLoading] = useState(false);
  const [threadError, setThreadError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isUndoing, setIsUndoing] = useState(false);
  const [editingEntryId, setEditingEntryId] = useState('');
  const [editedContent, setEditedContent] = useState('');
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [selectedHistoryId, setSelectedHistoryId] = useState('');
  const [selectedHistoryDetail, setSelectedHistoryDetail] = useState(null);
  const [historyDetailLoading, setHistoryDetailLoading] = useState(false);

  const isMountedRef = useRef(true);
  const streamAbortRef = useRef(null);
  const currentInteractionIdRef = useRef('');
  const cancelRequestedRef = useRef(false);
  const actionsDropdownRef = useRef(null);
  const resizeStateRef = useRef(null);

  const canUseAI = aiEnabled && (role === 'owner' || role === 'editor');
  const canViewHistory = Boolean(documentId);
  const isBusy = isRunning || isApplying || isUndoing || isCancelling || isClearing;
  const isComposerDisabled = !canUseAI || isApplying || isUndoing;
  const documentText = useMemo(() => htmlToPlainText(content), [content]);
  const contextScopeType = attachedSelection?.text?.trim() ? 'selection' : 'document';
  const hasClearableChat = threadEntries.length > 0 || historyItems.length > 0;
  const sidebarInlineStyle = isOpen && isDesktopViewport
    ? {
        '--ai-sidebar-width': `${sidebarWidth}px`,
        '--ai-sidebar-min-width': `${sidebarWidth}px`,
      }
    : undefined;

  const clampSidebarWidth = useCallback((nextWidth, viewportWidth = window.innerWidth) => {
    const maxAllowed = Math.min(
      AI_SIDEBAR_MAX_WIDTH,
      Math.max(AI_SIDEBAR_MIN_WIDTH, viewportWidth - 320)
    );
    return Math.min(Math.max(nextWidth, AI_SIDEBAR_MIN_WIDTH), maxAllowed);
  }, []);

  const loadThread = useCallback(
    async ({ silent = false } = {}) => {
      if (!documentId) {
        return;
      }

      if (!silent) {
        setThreadLoading(true);
      }
      setThreadError('');

      try {
        const entries = await apiJSON(`/documents/${documentId}/ai/chat/thread`);
        if (!isMountedRef.current) {
          return;
        }
        setThreadEntries((current) => (
          silent && entries.length === 0 && current.length > 0
            ? current
            : entries
        ));
      } catch (error) {
        if (!isMountedRef.current) {
          return;
        }
        setThreadError(error.message || 'Failed to load the AI chat thread.');
      } finally {
        if (isMountedRef.current && !silent) {
          setThreadLoading(false);
        }
      }
    },
    [documentId]
  );

  const loadHistoryDetail = useCallback(
    async (nextInteractionId, { silent = false } = {}) => {
      if (!nextInteractionId) {
        setSelectedHistoryDetail(null);
        return;
      }

      if (!silent) {
        setHistoryDetailLoading(true);
      }
      setHistoryError('');

      try {
        const detail = await apiJSON(`/ai/interactions/${nextInteractionId}`);
        if (!isMountedRef.current) {
          return;
        }
        setSelectedHistoryId(nextInteractionId);
        setSelectedHistoryDetail(detail);
      } catch (error) {
        if (!isMountedRef.current) {
          return;
        }
        setHistoryError(error.message || 'Failed to load AI interaction details.');
      } finally {
        if (isMountedRef.current && !silent) {
          setHistoryDetailLoading(false);
        }
      }
    },
    []
  );

  const loadHistory = useCallback(
    async ({ selectedInteractionId = null, silent = false } = {}) => {
      if (!canViewHistory) {
        return;
      }

      if (!silent) {
        setHistoryLoading(true);
      }
      setHistoryError('');

      try {
        const items = await apiJSON(`/documents/${documentId}/ai/interactions`);
        if (!isMountedRef.current) {
          return;
        }

        setHistoryItems(items);
        const nextSelectedId = selectedInteractionId || selectedHistoryId || items[0]?.interaction_id || '';

        if (!nextSelectedId) {
          setSelectedHistoryId('');
          setSelectedHistoryDetail(null);
          return;
        }

        await loadHistoryDetail(nextSelectedId, { silent });
      } catch (error) {
        if (!isMountedRef.current) {
          return;
        }
        setHistoryError(error.message || 'Failed to load AI history.');
      } finally {
        if (isMountedRef.current && !silent) {
          setHistoryLoading(false);
        }
      }
    },
    [canViewHistory, documentId, loadHistoryDetail, selectedHistoryId]
  );

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      streamAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const storedWidth = Number(window.localStorage.getItem(AI_SIDEBAR_WIDTH_STORAGE_KEY));
    if (Number.isFinite(storedWidth) && storedWidth > 0) {
      setSidebarWidth(clampSidebarWidth(storedWidth, window.innerWidth));
    } else {
      setSidebarWidth(clampSidebarWidth(AI_SIDEBAR_DEFAULT_WIDTH, window.innerWidth));
    }

    function handleWindowResize() {
      setIsDesktopViewport(window.innerWidth > AI_SIDEBAR_DESKTOP_BREAKPOINT);
      setSidebarWidth((current) => clampSidebarWidth(current, window.innerWidth));
    }

    handleWindowResize();
    window.addEventListener('resize', handleWindowResize);
    return () => window.removeEventListener('resize', handleWindowResize);
  }, [clampSidebarWidth]);

  useEffect(() => {
    if (typeof window === 'undefined' || !isDesktopViewport) {
      return;
    }
    window.localStorage.setItem(AI_SIDEBAR_WIDTH_STORAGE_KEY, String(sidebarWidth));
  }, [isDesktopViewport, sidebarWidth]);

  useEffect(() => {
    streamAbortRef.current?.abort();
    currentInteractionIdRef.current = '';
    cancelRequestedRef.current = false;
    setActiveTab('chat');
    setComposerMessage('');
    setAttachedSelection(null);
    setTranslateTargetLanguage('');
    setIsActionsOpen(false);
    setThreadEntries([]);
    setThreadLoading(false);
      setThreadError('');
      setStatusMessage('');
      setErrorMessage('');
      setIsClearing(false);
      setEditingEntryId('');
    setEditedContent('');
    setHistoryItems([]);
    setHistoryLoading(false);
    setHistoryError('');
    setSelectedHistoryId('');
    setSelectedHistoryDetail(null);
    setHistoryDetailLoading(false);
  }, [documentId]);

  useEffect(() => {
    if (selection?.text?.trim()) {
      setAttachedSelection(selection);
    }
  }, [selection]);

  useEffect(() => {
    function handlePointerDown(event) {
      if (!actionsDropdownRef.current?.contains(event.target)) {
        setIsActionsOpen(false);
      }
    }

    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, []);

  useEffect(() => {
    if (!isResizing) {
      return undefined;
    }

    function handlePointerMove(event) {
      if (!resizeStateRef.current) {
        return;
      }
      const nextWidth = resizeStateRef.current.startWidth + (resizeStateRef.current.startX - event.clientX);
      setSidebarWidth(clampSidebarWidth(nextWidth, window.innerWidth));
    }

    function handlePointerUp() {
      resizeStateRef.current = null;
      setIsResizing(false);
      document.body.style.removeProperty('cursor');
      document.body.style.removeProperty('user-select');
    }

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [clampSidebarWidth, isResizing]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    void loadThread();
  }, [isOpen, loadThread]);

  useEffect(() => {
    if (activeTab === 'history' && isOpen) {
      void loadHistory();
    }
  }, [activeTab, isOpen, loadHistory]);

  function updateThreadEntry(entryId, updater) {
    setThreadEntries((current) =>
      current.map((entry) => (
        entry.entry_id === entryId
          ? { ...entry, ...(typeof updater === 'function' ? updater(entry) : updater) }
          : entry
      ))
    );
  }

  function appendThreadEntries(entries) {
    setThreadEntries((current) => [...current, ...entries]);
  }

  function getScopePayload() {
    if (attachedSelection?.text?.trim()) {
      return {
        scopeType: 'selection',
        selectedRange: {
          start: attachedSelection.from,
          end: attachedSelection.to,
        },
        selectedText: attachedSelection.text.trim(),
        selectionSnapshot: attachedSelection,
      };
    }

    return {
      scopeType: 'document',
      selectedRange: undefined,
      selectedText: documentText,
      selectionSnapshot: null,
    };
  }

  async function prepareRequest({ requireUndoBaseline = false } = {}) {
    if (!canUseAI) {
      throw new Error(getUnavailableMessage({ aiEnabled, role }));
    }

    const { scopeType, selectedRange, selectedText, selectionSnapshot } = getScopePayload();

    if (!selectedText.trim()) {
      throw new Error(
        scopeType === 'selection'
          ? 'Select text in the editor to give AI a focused context.'
          : 'Write something before asking AI to help.'
      );
    }

    const prepared = await ensureSavedDocument({ requireUndoBaseline });
    return {
      prepared,
      scopeType,
      selectedRange,
      selectedText,
      selectedTextSnapshot: getSelectedTextSnapshot(scopeType, selectedText),
      selectionSnapshot,
      surroundingContext: buildContext({
        scopeType,
        documentTitle: prepared.title,
        documentText,
      }),
    };
  }

  async function startStream({
    endpoint,
    body,
    localUserEntry,
    assistantSeed,
    completionStatusMessage,
  }) {
    const controller = new AbortController();
    const localAssistantId = makeLocalId('assistant');
    let selectedInteractionId = '';

    streamAbortRef.current = controller;
    appendThreadEntries([localUserEntry]);

    try {
      const response = await apiFetch(endpoint, {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      const contentType = response.headers?.get?.('content-type') || '';
      if (!response.ok || !response.body || !contentType.includes('text/event-stream')) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch {
          errorData = null;
        }
        throw new Error(getErrorMessage(errorData, `HTTP ${response.status}`));
      }

      await consumeSseStream(response, async ({ event, data }) => {
        if (!isMountedRef.current) {
          return;
        }

        if (event === 'meta') {
          currentInteractionIdRef.current = data.interaction_id;
          selectedInteractionId = data.interaction_id;
          appendThreadEntries([
            {
              ...assistantSeed,
              entry_id: localAssistantId,
              interaction_id: data.interaction_id,
              status: 'processing',
            },
          ]);
          return;
        }

        if (event === 'chunk') {
          updateThreadEntry(localAssistantId, (entry) => ({
            ...entry,
            content: data.output ?? entry.content,
            status: 'processing',
          }));
          return;
        }

        if (event === 'complete') {
          selectedInteractionId = data.interaction_id;
          updateThreadEntry(localAssistantId, buildThreadEntryFromDetail(data));
          setStatusMessage(completionStatusMessage);
          return;
        }

        if (event === 'cancelled') {
          updateThreadEntry(localAssistantId, (entry) => ({
            ...entry,
            status: 'failed',
          }));
          const abortError = new Error('AI generation canceled.');
          abortError.name = 'AbortError';
          throw abortError;
        }

        if (event === 'error') {
          updateThreadEntry(localAssistantId, (entry) => ({
            ...entry,
            status: 'failed',
          }));
          throw new Error(data.message || 'AI generation failed.');
        }
      });
    } finally {
      if (selectedInteractionId) {
        await wait(0);
        void loadThread({ silent: true });
        void loadHistory({ selectedInteractionId, silent: true });
      }
    }
  }

  async function handleSend() {
    if (!composerMessage.trim()) {
      setErrorMessage('Write a message before sending it to AI.');
      return;
    }

    setActiveTab('chat');
    setErrorMessage('');
    setStatusMessage('');
    cancelRequestedRef.current = false;
    setIsRunning(true);

    try {
      const preparedRequest = await prepareRequest();
      const localUserEntry = {
        entry_id: makeLocalId('user'),
        interaction_id: null,
        conversation_id: `local-${documentId}`,
        entry_kind: 'chat_message',
        message_role: 'user',
        feature_type: 'chat_assistant',
        scope_type: preparedRequest.scopeType,
        status: 'completed',
        created_at: new Date().toISOString(),
        source_revision: preparedRequest.prepared.revision,
        content: composerMessage.trim(),
        selected_range: preparedRequest.selectedRange,
        selected_text_snapshot: preparedRequest.selectedTextSnapshot ?? null,
        surrounding_context: preparedRequest.surroundingContext,
        reply_to_interaction_id: null,
        outcome: null,
        review_only: true,
        suggestion: null,
      };

      await startStream({
        endpoint: `/documents/${preparedRequest.prepared.documentId}/ai/chat/messages/stream`,
        body: {
          mode: 'chat',
          message: composerMessage.trim(),
          selected_range: preparedRequest.selectedRange,
          selected_text_snapshot: preparedRequest.selectedTextSnapshot,
          surrounding_context: preparedRequest.surroundingContext,
          base_revision: preparedRequest.prepared.revision,
        },
        localUserEntry,
        assistantSeed: {
          conversation_id: `local-${documentId}`,
          entry_kind: 'chat_message',
          message_role: 'assistant',
          feature_type: 'chat_assistant',
          scope_type: preparedRequest.scopeType,
          created_at: new Date().toISOString(),
          source_revision: preparedRequest.prepared.revision,
          content: '',
          selected_range: preparedRequest.selectedRange,
          selected_text_snapshot: preparedRequest.selectedTextSnapshot ?? null,
          surrounding_context: preparedRequest.surroundingContext,
          reply_to_interaction_id: null,
          outcome: null,
          review_only: true,
          suggestion: null,
        },
        completionStatusMessage: 'AI response ready.',
      });
      setComposerMessage('');
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }
      if (cancelRequestedRef.current || error?.name === 'AbortError') {
        setStatusMessage('AI generation canceled.');
      } else {
        setErrorMessage(error.message || 'AI request failed.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsRunning(false);
        setIsCancelling(false);
      }
      streamAbortRef.current = null;
      currentInteractionIdRef.current = '';
      cancelRequestedRef.current = false;
    }
  }

  async function handleSuggestEdit() {
    if (!composerMessage.trim()) {
      setErrorMessage('Describe the edit you want AI to suggest.');
      return;
    }

    setActiveTab('chat');
    setErrorMessage('');
    setStatusMessage('');
    cancelRequestedRef.current = false;
    setIsRunning(true);

    try {
      const preparedRequest = await prepareRequest({ requireUndoBaseline: true });
      const localUserEntry = {
        entry_id: makeLocalId('user'),
        interaction_id: null,
        conversation_id: `local-${documentId}`,
        entry_kind: 'suggestion',
        message_role: 'user',
        feature_type: 'rewrite',
        scope_type: preparedRequest.scopeType,
        status: 'completed',
        created_at: new Date().toISOString(),
        source_revision: preparedRequest.prepared.revision,
        content: composerMessage.trim(),
        selected_range: preparedRequest.selectedRange,
        selected_text_snapshot: preparedRequest.selectedTextSnapshot ?? null,
        surrounding_context: preparedRequest.surroundingContext,
        reply_to_interaction_id: null,
        outcome: null,
        review_only: false,
        suggestion: null,
      };

      await startStream({
        endpoint: `/documents/${preparedRequest.prepared.documentId}/ai/chat/messages/stream`,
        body: {
          mode: 'suggest_edit',
          message: composerMessage.trim(),
          selected_range: preparedRequest.selectedRange,
          selected_text_snapshot: preparedRequest.selectedTextSnapshot,
          surrounding_context: preparedRequest.surroundingContext,
          base_revision: preparedRequest.prepared.revision,
        },
        localUserEntry,
        assistantSeed: {
          conversation_id: `local-${documentId}`,
          entry_kind: 'suggestion',
          message_role: 'assistant',
          feature_type: 'rewrite',
          scope_type: preparedRequest.scopeType,
          created_at: new Date().toISOString(),
          source_revision: preparedRequest.prepared.revision,
          content: '',
          selected_range: preparedRequest.selectedRange,
          selected_text_snapshot: preparedRequest.selectedTextSnapshot ?? null,
          surrounding_context: preparedRequest.surroundingContext,
          reply_to_interaction_id: null,
          outcome: null,
          review_only: false,
          suggestion: null,
        },
        completionStatusMessage:
          preparedRequest.scopeType === 'selection'
            ? 'Suggestion ready for the selected text.'
            : 'Suggestion ready to review.',
      });
      setComposerMessage('');
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }
      if (cancelRequestedRef.current || error?.name === 'AbortError') {
        setStatusMessage('AI generation canceled.');
      } else {
        setErrorMessage(error.message || 'AI request failed.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsRunning(false);
        setIsCancelling(false);
      }
      streamAbortRef.current = null;
      currentInteractionIdRef.current = '';
      cancelRequestedRef.current = false;
    }
  }

  async function handleQuickAction(featureType) {
    setActiveTab('chat');
    setErrorMessage('');
    setStatusMessage('');
    cancelRequestedRef.current = false;

    const targetLanguage = translateTargetLanguage.trim();
    if (featureType === 'translate' && !targetLanguage) {
      setErrorMessage('Choose a target language before running Translate.');
      return;
    }

    setIsRunning(true);

    try {
      const preparedRequest = await prepareRequest({
        requireUndoBaseline: featureType !== 'summarize',
      });
      const instruction = buildQuickActionInstruction(
        featureType,
        preparedRequest.scopeType,
        composerMessage,
        { targetLanguage }
      );
      const localUserEntry = {
        entry_id: makeLocalId('user'),
        interaction_id: null,
        conversation_id: `local-${documentId}`,
        entry_kind: featureType === 'summarize' ? 'chat_message' : 'suggestion',
        message_role: 'user',
        feature_type: featureType,
        scope_type: preparedRequest.scopeType,
        status: 'completed',
        created_at: new Date().toISOString(),
        source_revision: preparedRequest.prepared.revision,
        content: instruction,
        selected_range: preparedRequest.selectedRange,
        selected_text_snapshot: preparedRequest.selectedTextSnapshot ?? null,
        surrounding_context: preparedRequest.surroundingContext,
        reply_to_interaction_id: null,
        outcome: null,
        review_only: featureType === 'summarize',
        suggestion: null,
      };

      await startStream({
        endpoint: `/documents/${preparedRequest.prepared.documentId}/ai/interactions/stream`,
        body: {
          feature_type: featureType,
          scope_type: preparedRequest.scopeType,
          selected_range: preparedRequest.selectedRange,
          selected_text_snapshot: preparedRequest.selectedTextSnapshot,
          surrounding_context: preparedRequest.surroundingContext,
          user_instruction: composerMessage.trim() || undefined,
          base_revision: preparedRequest.prepared.revision,
          parameters: buildQuickActionParameters(featureType, { targetLanguage }),
        },
        localUserEntry,
        assistantSeed: {
          conversation_id: `local-${documentId}`,
          entry_kind: featureType === 'summarize' ? 'chat_message' : 'suggestion',
          message_role: 'assistant',
          feature_type: featureType,
          scope_type: preparedRequest.scopeType,
          created_at: new Date().toISOString(),
          source_revision: preparedRequest.prepared.revision,
          content: '',
          selected_range: preparedRequest.selectedRange,
          selected_text_snapshot: preparedRequest.selectedTextSnapshot ?? null,
          surrounding_context: preparedRequest.surroundingContext,
          reply_to_interaction_id: null,
          outcome: null,
          review_only: featureType === 'summarize',
          suggestion: null,
        },
        completionStatusMessage:
          featureType === 'summarize'
            ? 'Summary ready to review.'
            : preparedRequest.scopeType === 'selection'
              ? `${formatFeatureLabel(featureType)} ready for the selected text.`
              : `${formatFeatureLabel(featureType)} ready to review.`,
      });
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }
      if (cancelRequestedRef.current || error?.name === 'AbortError') {
        setStatusMessage('AI generation canceled.');
      } else {
        setErrorMessage(error.message || 'AI request failed.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsRunning(false);
        setIsCancelling(false);
      }
      streamAbortRef.current = null;
      currentInteractionIdRef.current = '';
      cancelRequestedRef.current = false;
    }
  }

  async function handleCancelRun() {
    cancelRequestedRef.current = true;
    setIsCancelling(true);

    try {
      streamAbortRef.current?.abort();
      if (currentInteractionIdRef.current) {
        await apiJSON(`/ai/interactions/${currentInteractionIdRef.current}/cancel`, {
          method: 'POST',
        });
      }
      if (isMountedRef.current) {
        setStatusMessage('AI generation canceled.');
        void loadThread({ silent: true });
        void loadHistory({ selectedInteractionId: currentInteractionIdRef.current, silent: true });
      }
    } catch (error) {
      if (isMountedRef.current && !cancelRequestedRef.current) {
        setErrorMessage(error.message || 'Failed to cancel AI generation.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsCancelling(false);
      }
    }
  }

  async function handleClearChat() {
    if (!documentId || !hasClearableChat || isBusy) {
      return;
    }

    setErrorMessage('');
    setStatusMessage('');
    setIsClearing(true);

    try {
      await apiJSON(`/documents/${documentId}/ai/chat/thread`, {
        method: 'DELETE',
      });
      if (!isMountedRef.current) {
        return;
      }
      setThreadEntries([]);
      setHistoryItems([]);
      setSelectedHistoryId('');
      setSelectedHistoryDetail(null);
      setEditingEntryId('');
      setEditedContent('');
      setStatusMessage('AI chat cleared.');
    } catch (error) {
      if (isMountedRef.current) {
        setErrorMessage(error.message || 'Failed to clear the AI chat.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsClearing(false);
      }
    }
  }

  function handleComposerSubmit() {
    if (isRunning) {
      void handleCancelRun();
      return;
    }

    void handleSend();
  }

  function handleComposerKeyDown(event) {
    if (event.key !== 'Enter' || event.shiftKey) {
      return;
    }

    if (isRunning || !composerMessage.trim() || isComposerDisabled) {
      return;
    }

    event.preventDefault();
    void handleSend();
  }

  function handleResizeStart(event) {
    if (!isDesktopViewport || !isOpen) {
      return;
    }
    event.preventDefault();
    resizeStateRef.current = {
      startX: event.clientX,
      startWidth: sidebarWidth,
    };
    setIsResizing(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  function handleResizeKeyDown(event) {
    if (!isDesktopViewport || !isOpen) {
      return;
    }

    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
      return;
    }

    event.preventDefault();
    const delta = event.key === 'ArrowLeft' ? 24 : -24;
    setSidebarWidth((current) => clampSidebarWidth(current + delta, window.innerWidth));
  }

  function isEntryStale(entry) {
    if (!entry || entry.review_only) {
      return false;
    }

    return Boolean(entry.suggestion?.stale) || hasUnsavedChanges || currentRevision !== entry.source_revision;
  }

  async function handleApply(entry) {
    if (!entry?.suggestion?.suggestion_id || entry.review_only) {
      return;
    }

    if (isEntryStale(entry)) {
      setErrorMessage(
        hasUnsavedChanges
          ? 'You have local edits newer than this suggestion. Save them and run AI again.'
          : 'This suggestion is stale because the document changed. Run AI again.'
      );
      return;
    }

    setIsApplying(true);
    setErrorMessage('');

    try {
      if (entry.scope_type === 'selection') {
        await applySelectionSuggestion({
          replacement: entry.content,
          selection: buildSelectionSnapshot(entry),
        });
      } else {
        await applyDocumentSuggestion({
          suggestionId: entry.suggestion.suggestion_id,
          applyRange: {
            start: 0,
            end: content.length,
          },
        });
      }

      if (!isMountedRef.current) {
        return;
      }

      setStatusMessage(
        entry.scope_type === 'selection'
          ? 'Suggestion applied to the selected text.'
          : 'Suggestion applied to the document.'
      );
      setEditingEntryId('');
      setEditedContent('');
      void loadThread({ silent: true });
      void loadHistory({ selectedInteractionId: entry.interaction_id, silent: true });
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }
      setErrorMessage(error.message || 'Failed to apply the suggestion.');
    } finally {
      if (isMountedRef.current) {
        setIsApplying(false);
      }
    }
  }

  async function handleApplyEdited(entry) {
    const nextOutput = editedContent.trim();
    if (!nextOutput) {
      setErrorMessage('Edited suggestion text cannot be empty.');
      return;
    }

    if (isEntryStale(entry)) {
      setErrorMessage(
        hasUnsavedChanges
          ? 'You have local edits newer than this suggestion. Save them and run AI again.'
          : 'This suggestion is stale because the document changed. Run AI again.'
      );
      return;
    }

    setIsApplying(true);
    setErrorMessage('');

    try {
      if (entry.scope_type === 'selection') {
        await applySelectionSuggestion({
          replacement: nextOutput,
          selection: buildSelectionSnapshot(entry),
        });
      } else {
        await applyEditedDocumentSuggestion({
          suggestionId: entry.suggestion.suggestion_id,
          editedOutput: nextOutput,
          applyRange: {
            start: 0,
            end: content.length,
          },
        });
      }

      if (!isMountedRef.current) {
        return;
      }

      setStatusMessage(
        entry.scope_type === 'selection'
          ? 'Edited suggestion applied to the selected text.'
          : 'Edited suggestion applied to the document.'
      );
      setEditingEntryId('');
      setEditedContent('');
      void loadThread({ silent: true });
      void loadHistory({ selectedInteractionId: entry.interaction_id, silent: true });
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }
      setErrorMessage(error.message || 'Failed to apply the edited suggestion.');
    } finally {
      if (isMountedRef.current) {
        setIsApplying(false);
      }
    }
  }

  async function handleReject(entry) {
    if (!entry?.suggestion?.suggestion_id) {
      return;
    }

    setIsApplying(true);
    setErrorMessage('');

    try {
      await apiJSON(`/ai/suggestions/${entry.suggestion.suggestion_id}/reject`, {
        method: 'POST',
      });

      if (!isMountedRef.current) {
        return;
      }

      setStatusMessage('Suggestion discarded.');
      setEditingEntryId('');
      setEditedContent('');
      void loadThread({ silent: true });
      void loadHistory({ selectedInteractionId: entry.interaction_id, silent: true });
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }
      setErrorMessage(error.message || 'Failed to discard the suggestion.');
    } finally {
      if (isMountedRef.current) {
        setIsApplying(false);
      }
    }
  }

  async function handleUndoAI() {
    setErrorMessage('');
    setIsUndoing(true);

    try {
      await undoLastAiApply();

      if (!isMountedRef.current) {
        return;
      }

      setStatusMessage('AI change undone.');
      void loadThread({ silent: true });
      void loadHistory({ silent: true });
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }
      setErrorMessage(error.message || 'Failed to undo the AI change.');
    } finally {
      if (isMountedRef.current) {
        setIsUndoing(false);
      }
    }
  }

  function renderSuggestionCard(entry) {
    const isEditing = editingEntryId === entry.entry_id;
    const entryStale = isEntryStale(entry);
    const hasPartialOutput = entry.status === 'failed' && Boolean(entry.content?.trim());
    return (
      <article key={entry.entry_id} className="ai-thread-card ai-thread-card-suggestion">
        <div className="ai-thread-card-top">
          <div>
            <p className="ai-thread-meta">
              {formatFeatureLabel(entry.feature_type)} · {formatTimestamp(entry.created_at)}
            </p>
            <h3 className="ai-thread-card-title">{formatFeatureLabel(entry.feature_type)}</h3>
          </div>
          <span className={`ai-history-badge ai-history-badge-${entry.status}`}>
            {formatHistoryStatus(entry.status)}
          </span>
        </div>

        {isEditing ? (
          <label className="field-label" htmlFor={`ai-edit-${entry.entry_id}`}>
            Edit before apply
            <textarea
              id={`ai-edit-${entry.entry_id}`}
              className="field-input ai-textarea"
              value={editedContent}
              onChange={(event) => setEditedContent(event.target.value)}
              disabled={isBusy}
            />
          </label>
        ) : (
          <div className="ai-result-output">{entry.content}</div>
        )}

        {entryStale && (
          <div className="ai-sidebar-notice ai-sidebar-notice-warning">
            This suggestion is stale because the document changed after it was generated.
          </div>
        )}

        {hasPartialOutput && (
          <div className="ai-sidebar-notice ai-sidebar-notice-warning">
            Partial output was kept after the AI stream was interrupted.
          </div>
        )}

        <div className="ai-result-actions">
          {isEditing ? (
            <>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleApplyEdited(entry)}
                disabled={isBusy || !editedContent.trim()}
              >
                Apply edited
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setEditingEntryId('');
                  setEditedContent('');
                }}
                disabled={isBusy}
              >
                Cancel edit
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleApply(entry)}
                disabled={isBusy || entryStale}
              >
                Accept
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setEditingEntryId(entry.entry_id);
                  setEditedContent(entry.content);
                }}
                disabled={isBusy}
              >
                Edit
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void handleReject(entry)}
                disabled={isBusy}
              >
                Reject
              </button>
              {lastAiUndo && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => void handleUndoAI()}
                  disabled={isUndoing || isBusy}
                >
                  {isUndoing ? 'Undoing...' : 'Undo AI'}
                </button>
              )}
            </>
          )}
        </div>
      </article>
    );
  }

  function renderThreadEntry(entry) {
    const hasPartialOutput = entry.status === 'failed' && Boolean(entry.content?.trim());
    if (entry.message_role === 'user') {
      return (
        <article key={entry.entry_id} className="ai-thread-card ai-thread-card-user">
          <p className="ai-thread-meta">{formatTimestamp(entry.created_at)}</p>
          <p className="ai-thread-user-text">{entry.content}</p>
          {entry.scope_type === 'selection' && entry.selected_text_snapshot && (
            <div className="ai-selection-preview ai-selection-preview-user">
              <span className="ai-selection-label">Selected context</span>
              <p className="ai-selection-text">{truncateText(entry.selected_text_snapshot)}</p>
            </div>
          )}
        </article>
      );
    }

    if (entry.entry_kind === 'suggestion' && !entry.review_only) {
      return renderSuggestionCard(entry);
    }

    return (
      <article key={entry.entry_id} className="ai-thread-card ai-thread-card-assistant">
        <div className="ai-thread-card-top">
          <p className="ai-thread-meta">
            {formatFeatureLabel(entry.feature_type)} · {formatTimestamp(entry.created_at)}
          </p>
          <span className={`ai-history-badge ai-history-badge-${entry.status}`}>
            {formatHistoryStatus(entry.status)}
          </span>
        </div>
        <div className="ai-result-output">{entry.content || 'AI is still generating...'}</div>
        {hasPartialOutput && (
          <div className="ai-sidebar-notice ai-sidebar-notice-warning">
            Partial output was kept after the AI stream was interrupted.
          </div>
        )}
      </article>
    );
  }

  return (
    <aside
      className={`ai-sidebar ${isOpen ? 'ai-sidebar-open' : 'ai-sidebar-closed'} ${isResizing ? 'ai-sidebar-resizing' : ''}`}
      aria-label="AI Assistant"
      aria-hidden={!isOpen}
      data-state={isOpen ? 'open' : 'closed'}
      style={sidebarInlineStyle}
    >
      <div
        className="ai-sidebar-resize-handle"
        role="separator"
        aria-label="Resize AI sidebar"
        aria-orientation="vertical"
        tabIndex={isDesktopViewport && isOpen ? 0 : -1}
        onPointerDown={handleResizeStart}
        onKeyDown={handleResizeKeyDown}
      />
      <div className="ai-sidebar-header">
        <h2 className="ai-sidebar-title">AI Assistant</h2>
        <div className="ai-sidebar-header-actions">
          <button
            type="button"
            className="btn btn-ghost ai-sidebar-icon-btn"
            onClick={() => void handleClearChat()}
            aria-label="Clear AI chat"
            title="Clear AI chat"
            disabled={!hasClearableChat || isBusy || threadLoading}
          >
            🗑
          </button>
          <button
            type="button"
            className="btn btn-ghost ai-sidebar-close"
            onClick={onClose}
            aria-label="Close AI sidebar"
          >
            Close
          </button>
        </div>
      </div>

      <div className="ai-sidebar-tabs" role="tablist" aria-label="AI sidebar panels">
        <button
          type="button"
          className={`ai-sidebar-tab ${activeTab === 'chat' ? 'ai-sidebar-tab-active' : ''}`}
          onClick={() => setActiveTab('chat')}
          role="tab"
          aria-selected={activeTab === 'chat'}
        >
          Chat
        </button>
        <button
          type="button"
          className={`ai-sidebar-tab ${activeTab === 'history' ? 'ai-sidebar-tab-active' : ''}`}
          onClick={() => setActiveTab('history')}
          role="tab"
          aria-selected={activeTab === 'history'}
        >
          AI History
        </button>
      </div>

      <div className="ai-sidebar-body">
        {activeTab === 'chat' ? (
          <div className="ai-chat-panel">
            {!canUseAI && (
              <div className="ai-sidebar-notice ai-sidebar-notice-warning">
                {getUnavailableMessage({ aiEnabled, role })}
              </div>
            )}

            <div className="ai-chat-toolbar">
              <div className="ai-chat-toolbar-row">
                <div className="ai-toolbar-dropdown" ref={actionsDropdownRef}>
                  <button
                    type="button"
                    className="btn btn-secondary ai-toolbar-trigger"
                    onClick={() => {
                      setIsActionsOpen((current) => !current);
                    }}
                    aria-expanded={isActionsOpen}
                    aria-haspopup="menu"
                    disabled={!canUseAI || isBusy}
                  >
                    <span>Shortcuts</span>
                    <span className="ai-toolbar-chevron" aria-hidden="true">
                      {isActionsOpen ? '▾' : '▸'}
                    </span>
                  </button>

                  {isActionsOpen ? (
                    <div className="ai-toolbar-menu" role="menu" aria-label="AI quick actions">
                      <label className="field-label ai-toolbar-field" htmlFor="ai-translate-target-language">
                        Translate to
                        <input
                          id="ai-translate-target-language"
                          className="field-input"
                          type="text"
                          value={translateTargetLanguage}
                          onChange={(event) => setTranslateTargetLanguage(event.target.value)}
                          placeholder="e.g. French, Arabic, Japanese"
                          disabled={!canUseAI || isBusy}
                        />
                      </label>

                      {QUICK_ACTIONS.map((action) => (
                        <button
                          key={action.value}
                          type="button"
                          role="menuitem"
                          className="btn btn-secondary ai-toolbar-menu-item"
                          onClick={() => {
                            setIsActionsOpen(false);
                            void handleQuickAction(action.value);
                          }}
                          disabled={!canUseAI || isBusy}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className="ai-chat-context">
                  <div className="ai-context-inline">
                    <div className="ai-context-trigger-copy">
                      <span className="ai-selection-label">Context</span>
                      <span className="ai-context-value">
                        {attachedSelection?.text?.trim()
                          ? truncateText(attachedSelection.text, 48)
                          : 'Whole document'}
                      </span>
                    </div>

                    {attachedSelection?.text?.trim() ? (
                      <div className="ai-chat-context-footer">
                        <p className="ai-thread-meta">
                          Range {attachedSelection.from}–{attachedSelection.to}
                        </p>
                        <button
                          type="button"
                          className="btn btn-ghost ai-context-clear"
                          onClick={() => {
                            setAttachedSelection(null);
                          }}
                          disabled={isBusy}
                        >
                          Clear
                        </button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>

            <div className="ai-chat-status-stack">
              {statusMessage && (
                <div className="ai-sidebar-status">{statusMessage}</div>
              )}

              {errorMessage && (
                <div className="form-error" role="alert">{errorMessage}</div>
              )}

              {threadError && (
                <div className="form-error" role="alert">{threadError}</div>
              )}
            </div>

            <div className="ai-thread-shell">
              <div className="ai-thread-list">
                {threadLoading ? (
                  <div className="ai-result-empty">Loading AI thread...</div>
                ) : threadEntries.length === 0 ? (
                  <div className="ai-result-empty">
                    Ask a question, select text for focused context, or use one of the
                    shortcut actions in the menu above.
                  </div>
                ) : (
                  threadEntries.map(renderThreadEntry)
                )}
              </div>
            </div>

            <div className="ai-chat-composer">
              <textarea
                id="ai-chat-message"
                aria-label="Message"
                className="field-input ai-textarea"
                value={composerMessage}
                onChange={(event) => setComposerMessage(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="Ask AI about the document or the selected text..."
                disabled={!canUseAI || isBusy}
              />

              <div className="ai-run-actions ai-run-actions-single">
                <button
                  type="button"
                  className={`ai-composer-submit ${isRunning ? 'ai-composer-submit-running' : ''}`}
                  onClick={handleComposerSubmit}
                  disabled={
                    isComposerDisabled
                    || (!isRunning && !composerMessage.trim())
                    || (isRunning && isCancelling)
                  }
                  aria-label={isRunning ? 'Stop AI generation' : 'Send message'}
                  title={isRunning ? 'Stop AI generation' : 'Send message'}
                >
                  <span className="ai-composer-submit-icon" aria-hidden="true">
                    {isRunning ? '■' : '↑'}
                  </span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="ai-history-panel">
            <div className="ai-history-header">
              <div>
                <h3 className="ai-history-title">AI History</h3>
                <p className="ai-history-subtitle">
                  Audit completed AI interactions for this document, including chat
                  replies and suggestion outcomes.
                </p>
              </div>
            </div>

            {historyError && (
              <div className="form-error" role="alert">{historyError}</div>
            )}

            <div className="ai-history-grid">
              <div className="ai-history-list">
                {historyLoading ? (
                  <div className="ai-result-empty">Loading AI history...</div>
                ) : historyItems.length === 0 ? (
                  <div className="ai-result-empty">No AI interactions yet.</div>
                ) : (
                  historyItems.map((item) => (
                    <button
                      key={item.interaction_id}
                      type="button"
                      className={`ai-history-item ${selectedHistoryId === item.interaction_id ? 'ai-history-item-active' : ''}`}
                      onClick={() => void loadHistoryDetail(item.interaction_id)}
                    >
                      <div className="ai-history-item-top">
                        <p className="ai-history-feature">{formatFeatureLabel(item.feature_type)}</p>
                        <span className={`ai-history-badge ai-history-badge-${item.status}`}>
                          {formatHistoryStatus(item.status)}
                        </span>
                      </div>
                      <div className="ai-history-item-meta">
                        <span>{item.entry_kind === 'chat_message' ? 'Chat' : 'Suggestion'}</span>
                        <span>{item.scope_type === 'selection' ? 'Selected text' : 'Whole document'}</span>
                      </div>
                      <div className="ai-history-item-meta">
                        <span>{formatTimestamp(item.created_at)}</span>
                        {item.outcome && <span>{item.outcome}</span>}
                      </div>
                    </button>
                  ))
                )}
              </div>

              <div className="ai-history-detail">
                {historyDetailLoading ? (
                  <div className="ai-result-empty">Loading detail...</div>
                ) : !selectedHistoryDetail ? (
                  <div className="ai-result-empty">Select an item to inspect it.</div>
                ) : (
                  <>
                    <div className="ai-history-detail-header">
                      <h3 className="ai-history-detail-title">
                        {formatFeatureLabel(selectedHistoryDetail.feature_type)}
                      </h3>
                      <span className={`ai-history-badge ai-history-badge-${selectedHistoryDetail.status}`}>
                        {formatHistoryStatus(selectedHistoryDetail.status)}
                      </span>
                    </div>

                    <div className="ai-history-detail-meta">
                      <span>{selectedHistoryDetail.entry_kind === 'chat_message' ? 'Chat' : 'Suggestion'}</span>
                      <span>{selectedHistoryDetail.scope_type === 'selection' ? 'Selected text' : 'Whole document'}</span>
                      <span>Revision {selectedHistoryDetail.source_revision ?? selectedHistoryDetail.base_revision}</span>
                    </div>

                    {selectedHistoryDetail.user_instruction && (
                      <div className="ai-history-section">
                        <span className="ai-selection-label">Request</span>
                        <p className="ai-selection-text">{selectedHistoryDetail.user_instruction}</p>
                      </div>
                    )}

                    {selectedHistoryDetail.selected_text_snapshot && (
                      <div className="ai-history-section">
                        <span className="ai-selection-label">Selected text snapshot</span>
                        <p className="ai-selection-text">
                          {selectedHistoryDetail.selected_text_snapshot}
                        </p>
                      </div>
                    )}

                    {selectedHistoryDetail.suggestion?.generated_output && (
                      <div className="ai-history-section">
                        <span className="ai-selection-label">Response</span>
                        <div className="ai-result-output">
                          {selectedHistoryDetail.suggestion.generated_output}
                        </div>
                      </div>
                    )}

                    <div className="ai-history-section">
                      <span className="ai-selection-label">Rendered prompt</span>
                      <pre className="ai-history-prompt">{selectedHistoryDetail.rendered_prompt}</pre>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
