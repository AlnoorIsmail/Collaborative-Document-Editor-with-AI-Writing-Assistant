import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiJSON } from '../api';
import AIPanel from '../components/AIPanel';
import Navbar from '../components/Navbar';
import ShareModal from '../components/ShareModal';
import TiptapEditor from '../components/TiptapEditor';
import VersionHistoryPanel from '../components/VersionHistoryPanel';
import {
  createEmptyAiState,
  mapAiHistoryEntry,
  pollAiInteraction,
  streamTextProgressively,
} from '../services/ai';

const AUTO_SAVE_INTERVAL = 30_000;

function stripHtml(html) {
  if (!html) return '';

  if (typeof window === 'undefined' || !window.document) {
    return html.replace(/<[^>]+>/g, ' ');
  }

  const scratch = window.document.createElement('div');
  scratch.innerHTML = html;
  return scratch.textContent || '';
}

function getFallbackSelection() {
  return { text: '', from: 0, to: 0 };
}

function buildApplyRange(selection, fullText) {
  if (selection?.text) {
    return {
      start: Math.max(selection.from || 0, 0),
      end: Math.max(selection.to || selection.from || 0, selection.from || 0),
    };
  }

  return {
    start: 0,
    end: Math.max(fullText.length, 0),
  };
}

function buildLocalHistoryEntry({
  id,
  feature,
  instruction,
  status,
  scope,
  originalText,
  suggestionText,
  partialOutput = false,
  suggestionId = '',
}) {
  return {
    id,
    feature,
    instruction: instruction.trim() || 'No extra instruction',
    status,
    scope,
    model: 'backend-ai',
    partialOutput,
    originalText,
    suggestionText,
    createdAt: new Date().toISOString(),
    suggestionId,
  };
}

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [doc, setDoc] = useState(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState('owner');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saveStatus, setSaveStatus] = useState('saved');
  const [showShare, setShowShare] = useState(false);
  const [error, setError] = useState('');
  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(true);
  const [versionError, setVersionError] = useState('');
  const [aiHistory, setAiHistory] = useState([]);
  const [selectionState, setSelectionState] = useState(getFallbackSelection());
  const [aiForm, setAiForm] = useState({
    feature: 'rewrite',
    instruction: '',
  });
  const [aiState, setAiState] = useState(createEmptyAiState());
  const [undoState, setUndoState] = useState(null);

  const editorRef = useRef(null);
  const contentRef = useRef('');
  const revisionRef = useRef(0);
  const isDirtyRef = useRef(false);
  const aiAbortRef = useRef(null);
  const aiOutputRef = useRef('');

  const isReadOnly = role === 'viewer';
  const canUseAi = doc?.ai_enabled && !isReadOnly;

  const prependHistoryEntry = useCallback((entry) => {
    setAiHistory((currentHistory) => [entry, ...currentHistory]);
  }, []);

  const updateHistoryEntry = useCallback((interactionId, updates) => {
    setAiHistory((currentHistory) =>
      currentHistory.map((item) =>
        item.id === interactionId ? { ...item, ...updates } : item,
      ),
    );
  }, []);

  const loadVersions = useCallback(async () => {
    setVersionsLoading(true);
    setVersionError('');

    try {
      const data = await apiJSON(`/documents/${id}/versions`);
      setVersions(data);
    } catch (err) {
      setVersionError(err.message || 'Could not load version history.');
    } finally {
      setVersionsLoading(false);
    }
  }, [id]);

  const loadAiHistory = useCallback(async () => {
    try {
      const interactions = await apiJSON(`/documents/${id}/ai/interactions`);
      const details = await Promise.all(
        interactions.map((interaction) =>
          apiJSON(`/ai/interactions/${interaction.interaction_id}`).catch(() => null),
        ),
      );

      setAiHistory(
        interactions.map((interaction, index) =>
          mapAiHistoryEntry(interaction, details[index]),
        ),
      );
    } catch {
      setAiHistory([]);
    }
  }, [id]);

  const loadDocument = useCallback(async () => {
    setError('');

    try {
      const [docData, userData, versionData] = await Promise.all([
        apiJSON(`/documents/${id}`),
        apiJSON('/auth/me'),
        apiJSON(`/documents/${id}/versions`).catch(() => []),
      ]);

      const initialContent = docData.current_content || '';

      setDoc(docData);
      setUser(userData);
      setRole(docData.role || 'viewer');
      setTitle(docData.title || '');
      setContent(initialContent);
      setVersions(versionData);
      setVersionsLoading(false);
      setVersionError('');

      contentRef.current = initialContent;
      revisionRef.current = docData.revision || versionData[0]?.version_number || 0;
      isDirtyRef.current = false;
      aiOutputRef.current = '';
      setSaveStatus('saved');
      setSelectionState(getFallbackSelection());
      setUndoState(null);
      setAiState(createEmptyAiState());
    } catch (err) {
      if (err.status === 404) {
        navigate('/');
        return;
      }

      setError(err.message || 'Could not load this document.');
    }
  }, [id, navigate]);

  useEffect(() => {
    loadDocument();
    loadAiHistory();
  }, [loadAiHistory, loadDocument]);

  const saveContent = useCallback(async () => {
    if (!isDirtyRef.current) return;

    setSaveStatus('saving');

    try {
      const response = await apiJSON(`/documents/${id}/content`, {
        method: 'PATCH',
        body: JSON.stringify({
          content: contentRef.current,
          base_revision: revisionRef.current,
        }),
      });

      isDirtyRef.current = false;
      setSaveStatus('saved');
      revisionRef.current = response.revision || revisionRef.current;
      setDoc((currentDoc) =>
        currentDoc
          ? {
              ...currentDoc,
              current_content: contentRef.current,
              latest_version_id: response.latest_version_id,
              revision: response.revision || currentDoc.revision,
              updated_at: response.saved_at,
            }
          : currentDoc,
      );
      await loadVersions();
    } catch {
      setSaveStatus('unsaved');
    }
  }, [id, loadVersions]);

  useEffect(() => {
    const timer = window.setInterval(saveContent, AUTO_SAVE_INTERVAL);
    return () => window.clearInterval(timer);
  }, [saveContent]);

  useEffect(() => () => {
    aiAbortRef.current?.abort();
  }, []);

  function handleContentChange(nextContent) {
    contentRef.current = nextContent;
    setContent(nextContent);
    isDirtyRef.current = true;
    setSaveStatus('unsaved');
  }

  async function handleTitleChange(nextTitle) {
    setTitle(nextTitle);

    try {
      const updatedDoc = await apiJSON(`/documents/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: nextTitle }),
      });

      setDoc((currentDoc) =>
        currentDoc
          ? {
              ...currentDoc,
              title: updatedDoc.title,
              updated_at: updatedDoc.updated_at,
            }
          : currentDoc,
      );
    } catch {
      // Title updates are non-blocking for this PoC.
    }
  }

  async function handleRestoreVersion(version) {
    if (isReadOnly) return;

    try {
      await apiJSON(`/documents/${id}/versions/${version.version_id}/restore`, {
        method: 'POST',
      });

      await Promise.all([loadDocument(), loadAiHistory()]);
      setSaveStatus('saved');
    } catch (err) {
      setVersionError(err.message || 'Could not restore that version.');
    }
  }

  async function handleGenerateSuggestion() {
    if (!doc) return;

    if (!canUseAi) {
      setAiState({
        ...createEmptyAiState(),
        status: 'error',
        error: isReadOnly
          ? 'Viewer mode is read-only. AI actions are disabled.'
          : 'AI is disabled for this document.',
      });
      return;
    }

    const editorSelection = editorRef.current?.getSelection?.() || getFallbackSelection();
    const activeSelection = editorSelection.text.trim()
      ? { ...editorSelection, text: editorSelection.text.trim() }
      : selectionState.text.trim()
        ? { ...selectionState, text: selectionState.text.trim() }
        : null;
    const plainText = editorRef.current?.getText?.() || stripHtml(contentRef.current);
    const baselineText = activeSelection ? activeSelection.text : plainText.trim();
    const baselineContent = contentRef.current;
    const scope = activeSelection ? 'selection' : 'document';

    if (!baselineText.trim()) {
      setAiState({
        ...createEmptyAiState(),
        status: 'error',
        error: 'Add some content before generating a suggestion.',
      });
      return;
    }

    aiAbortRef.current?.abort();
    const abortController = new AbortController();
    aiAbortRef.current = abortController;

    const temporaryInteractionId = `ai-${Date.now()}`;
    aiOutputRef.current = '';
    setAiState({
      status: 'streaming',
      output: '',
      editableOutput: '',
      error: '',
      interactionId: temporaryInteractionId,
      suggestionId: '',
      baselineText,
      baselineContent,
      selection: activeSelection,
      scope,
      partialOutputPreserved: false,
    });

    try {
      const accepted = await apiJSON(`/documents/${id}/ai/interactions`, {
        method: 'POST',
        body: JSON.stringify({
          feature_type: aiForm.feature,
          scope_type: scope,
          selection_range: activeSelection
            ? { start: activeSelection.from, end: activeSelection.to }
            : undefined,
          selected_text_snapshot: activeSelection?.text,
          surrounding_context: baselineContent,
          user_prompt: aiForm.instruction || undefined,
          base_revision: revisionRef.current,
          options: {},
        }),
        signal: abortController.signal,
      });

      const detail = await pollAiInteraction({
        interactionId: accepted.interaction_id,
        request: (path, options) => apiJSON(path, options),
        signal: abortController.signal,
      });
      const finalOutput = detail.suggestion?.generated_output || '';

      await streamTextProgressively({
        text: finalOutput,
        signal: abortController.signal,
        onUpdate(nextOutput) {
          aiOutputRef.current = nextOutput;
          setAiState((currentState) =>
            currentState.interactionId === temporaryInteractionId
              ? { ...currentState, output: nextOutput }
              : currentState,
          );
        },
      });

      const historyEntry = buildLocalHistoryEntry({
        id: accepted.interaction_id,
        feature: aiForm.feature,
        instruction: aiForm.instruction,
        status: 'ready',
        scope,
        originalText: baselineText,
        suggestionText: finalOutput,
        suggestionId: detail.suggestion?.suggestion_id || '',
      });

      prependHistoryEntry(historyEntry);
      aiOutputRef.current = finalOutput;
      setAiState((currentState) =>
        currentState.interactionId === temporaryInteractionId
          ? {
              ...currentState,
              status: 'ready',
              interactionId: accepted.interaction_id,
              suggestionId: detail.suggestion?.suggestion_id || '',
              output: finalOutput,
              editableOutput: finalOutput,
            }
          : currentState,
      );
    } catch (err) {
      const partialOutput = aiOutputRef.current;

      if (err.name === 'AbortError') {
        prependHistoryEntry(
          buildLocalHistoryEntry({
            id: temporaryInteractionId,
            feature: aiForm.feature,
            instruction: aiForm.instruction,
            status: 'cancelled',
            scope,
            originalText: baselineText,
            suggestionText: partialOutput,
            partialOutput: Boolean(partialOutput),
          }),
        );
        setAiState((currentState) =>
          currentState.interactionId === temporaryInteractionId
            ? {
                ...currentState,
                status: 'cancelled',
                output: partialOutput,
                editableOutput: partialOutput,
                partialOutputPreserved: Boolean(partialOutput),
                error: partialOutput
                  ? 'Generation cancelled. Partial output was kept for review.'
                  : 'Generation cancelled before any output arrived.',
              }
            : currentState,
        );
      } else {
        prependHistoryEntry(
          buildLocalHistoryEntry({
            id: temporaryInteractionId,
            feature: aiForm.feature,
            instruction: aiForm.instruction,
            status: 'error',
            scope,
            originalText: baselineText,
            suggestionText: partialOutput,
            partialOutput: Boolean(partialOutput),
          }),
        );
        setAiState((currentState) =>
          currentState.interactionId === temporaryInteractionId
            ? {
                ...currentState,
                status: 'error',
                output: partialOutput,
                editableOutput: partialOutput,
                partialOutputPreserved: Boolean(partialOutput),
                error: err.message || 'The AI request failed. Try again.',
              }
            : currentState,
        );
      }
    } finally {
      if (aiAbortRef.current === abortController) {
        aiAbortRef.current = null;
      }
    }
  }

  async function handleAcceptSuggestion() {
    if (!doc || !aiState.editableOutput.trim() || !aiState.interactionId) return;
    if (aiForm.feature === 'summarize') return;
    if (contentRef.current !== aiState.baselineContent) {
      setAiState((currentState) => ({
        ...currentState,
        status: 'error',
        error: 'The document changed after generation. Regenerate the suggestion before applying it.',
      }));
      return;
    }

    const nextText = aiState.editableOutput.trim();
    const previousContent = contentRef.current;
    const currentPlainText = editorRef.current?.getText?.() || stripHtml(contentRef.current);
    const applyToRange = buildApplyRange(aiState.selection, currentPlainText);
    const suggestionWasEdited = nextText !== aiState.output.trim();

    try {
      if (suggestionWasEdited) {
        await apiJSON(`/ai/suggestions/${aiState.suggestionId}/apply-edited`, {
          method: 'POST',
          body: JSON.stringify({
            edited_output: nextText,
            apply_to_range: applyToRange,
          }),
        });
      } else {
        await apiJSON(`/ai/suggestions/${aiState.suggestionId}/accept`, {
          method: 'POST',
          body: JSON.stringify({
            apply_to_range: applyToRange,
          }),
        });
      }
    } catch (err) {
      setAiState((currentState) => ({
        ...currentState,
        status: 'error',
        error: err.message || 'Could not apply the AI suggestion.',
      }));
      return;
    }

    const nextContent =
      aiState.scope === 'selection' && aiState.selection
        ? editorRef.current?.replaceRange(
            aiState.selection.from,
            aiState.selection.to,
            nextText,
          ) || contentRef.current
        : editorRef.current?.setContent(nextText) || nextText;

    contentRef.current = nextContent;
    setContent(nextContent);
    isDirtyRef.current = true;
    setSaveStatus('unsaved');
    setUndoState({
      previousContent,
      interactionId: aiState.interactionId,
    });
    setSelectionState(getFallbackSelection());
    updateHistoryEntry(aiState.interactionId, {
      status: suggestionWasEdited ? 'modified' : 'accepted',
      suggestionText: nextText,
    });
    setAiState((currentState) => ({
      ...currentState,
      status: 'accepted',
      output: nextText,
      editableOutput: nextText,
      baselineText: nextText,
      baselineContent: nextContent,
    }));
  }

  async function handleRejectSuggestion() {
    if (!aiState.interactionId || !aiState.suggestionId) {
      setAiState(createEmptyAiState());
      return;
    }

    try {
      await apiJSON(`/ai/suggestions/${aiState.suggestionId}/reject`, {
        method: 'POST',
      });
      updateHistoryEntry(aiState.interactionId, {
        status: 'rejected',
        suggestionText: aiState.editableOutput || aiState.output,
      });
      setAiState(createEmptyAiState());
    } catch (err) {
      setAiState((currentState) => ({
        ...currentState,
        status: 'error',
        error: err.message || 'Could not reject the suggestion.',
      }));
    }
  }

  function handleUndoSuggestion() {
    if (!undoState) return;

    const restoredContent =
      editorRef.current?.setContent(undoState.previousContent) || undoState.previousContent;

    contentRef.current = restoredContent;
    setContent(restoredContent);
    isDirtyRef.current = true;
    setSaveStatus('unsaved');
    setSelectionState(getFallbackSelection());
    updateHistoryEntry(undoState.interactionId, {
      status: 'accepted_then_undone',
    });
    setUndoState(null);
    setAiState((currentState) => ({
      ...currentState,
      status: currentState.editableOutput ? 'ready' : 'idle',
    }));
  }

  if (error) {
    return (
      <div className="editor-error">
        <p>{error}</p>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          Back to documents
        </button>
      </div>
    );
  }

  if (!doc) {
    return <div className="editor-loading">Loading document…</div>;
  }

  return (
    <div className="editor-page">
      <Navbar
        title={title}
        onTitleChange={handleTitleChange}
        saveStatus={saveStatus}
        onSaveNow={saveContent}
        onShare={() => setShowShare(true)}
        isOwner={role === 'owner'}
        isReadOnly={isReadOnly}
        onBack={() => navigate('/')}
        user={user}
      />

      {isReadOnly ? (
        <div className="readonly-banner">
          You have view-only access to this document.
        </div>
      ) : null}

      <div className="editor-layout">
        <div className="editor-main">
          <TiptapEditor
            ref={editorRef}
            content={content}
            onChange={handleContentChange}
            readOnly={isReadOnly}
            placeholder="Start writing…"
            onSelectionUpdate={(nextSelection) =>
              setSelectionState(nextSelection || getFallbackSelection())
            }
          />
        </div>

        <aside className="editor-sidebar">
          <VersionHistoryPanel
            versions={versions}
            isLoading={versionsLoading}
            errorMessage={versionError}
            canManageVersions={!isReadOnly}
            onRefresh={loadVersions}
            onRestoreVersion={handleRestoreVersion}
          />

          <AIPanel
            role={role}
            aiEnabled={doc.ai_enabled}
            aiForm={aiForm}
            aiState={aiState}
            aiHistory={aiHistory}
            selectionState={selectionState}
            undoState={undoState}
            onFeatureChange={(feature) => {
              aiOutputRef.current = '';
              setAiForm((currentForm) => ({ ...currentForm, feature }));
              setAiState(createEmptyAiState());
            }}
            onInstructionChange={(instruction) =>
              setAiForm((currentForm) => ({ ...currentForm, instruction }))
            }
            onGenerateSuggestion={handleGenerateSuggestion}
            onCancelSuggestion={() => aiAbortRef.current?.abort()}
            onClearSuggestion={() => {
              aiOutputRef.current = '';
              setAiState(createEmptyAiState());
            }}
            onSuggestionChange={(editableOutput) =>
              setAiState((currentState) => ({ ...currentState, editableOutput }))
            }
            onAcceptSuggestion={handleAcceptSuggestion}
            onRejectSuggestion={handleRejectSuggestion}
            onUndoSuggestion={handleUndoSuggestion}
          />
        </aside>
      </div>

      {showShare ? (
        <ShareModal
          docId={id}
          collaborators={doc.collaborators || []}
          onClose={() => setShowShare(false)}
          onUpdate={(updated) =>
            setDoc((currentDoc) => ({ ...currentDoc, collaborators: updated }))
          }
        />
      ) : null}
    </div>
  );
}
