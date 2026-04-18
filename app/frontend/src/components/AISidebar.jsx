import { useEffect, useMemo, useRef, useState } from 'react';
import { apiJSON } from '../api';

const POLL_DELAY_MS = 700;
const MAX_POLL_ATTEMPTS = 8;
const FEATURE_OPTIONS = [
  { value: 'summarize', label: 'Summarize' },
  { value: 'rewrite', label: 'Rewrite' },
  { value: 'chat_assistant', label: 'Ask AI' },
];

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
  const normalized = text.replace(/\s+/g, ' ').trim();
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

function getInstructionCopy(featureType) {
  if (featureType === 'summarize') {
    return {
      label: 'Summary focus',
      placeholder:
        'Optional: highlight decisions, risks, action items, or key takeaways...',
      runLabel: 'Generate summary',
      resultLabel: 'Summary',
    };
  }

  if (featureType === 'chat_assistant') {
    return {
      label: 'Ask AI',
      placeholder:
        'Ask a question about the document or request help with the selected text...',
      runLabel: 'Ask AI',
      resultLabel: 'Response',
    };
  }

  return {
    label: 'Rewrite instruction',
    placeholder:
      'Optional: make it clearer, more concise, more formal, or easier to read...',
    runLabel: 'Generate rewrite',
    resultLabel: 'Suggestion',
  };
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
  applySelectionSuggestion,
  undoLastAiApply,
  isOpen,
  onClose,
}) {
  const [featureType, setFeatureType] = useState('summarize');
  const [scopeType, setScopeType] = useState('document');
  const [instruction, setInstruction] = useState('');
  const [interactionId, setInteractionId] = useState('');
  const [result, setResult] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isUndoing, setIsUndoing] = useState(false);

  const isMountedRef = useRef(true);

  const canUseAI = aiEnabled && (role === 'owner' || role === 'editor');
  const savedSelection = selection?.text?.trim() ? selection : null;
  const instructionCopy = getInstructionCopy(featureType);
  const isBusy = isRunning || isApplying || isUndoing;

  const isSuggestionStale = useMemo(() => {
    if (!result || result.featureType !== 'rewrite') {
      return false;
    }

    return result.stale || hasUnsavedChanges || currentRevision !== result.baseRevision;
  }, [currentRevision, hasUnsavedChanges, result]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    setInteractionId('');
    setResult(null);
    setStatusMessage('');
    setErrorMessage('');
    setScopeType('document');
  }, [documentId]);

  useEffect(() => {
    if (!savedSelection && scopeType === 'selection') {
      setScopeType('document');
    }
  }, [savedSelection, scopeType]);

  async function pollInteraction(nextInteractionId) {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      const detail = await apiJSON(`/ai/interactions/${nextInteractionId}`);

      if (detail.status === 'completed' && detail.suggestion) {
        return detail;
      }

      if (detail.status === 'failed') {
        throw new Error('The AI interaction failed. Please try again.');
      }

      await wait(POLL_DELAY_MS);
    }

    throw new Error('The AI is still processing. Try again in a moment.');
  }

  async function handleRun() {
    setErrorMessage('');
    setStatusMessage('');
    setResult(null);
    setInteractionId('');

    if (!canUseAI) {
      setErrorMessage(getUnavailableMessage({ aiEnabled, role }));
      return;
    }

    if (scopeType === 'selection' && !savedSelection) {
      setErrorMessage('Select text in the editor to run AI on just that part.');
      return;
    }

    if (!htmlToPlainText(content).trim()) {
      setErrorMessage('Write something before asking AI to help.');
      return;
    }

    setIsRunning(true);

    try {
      const prepared = await ensureSavedDocument({
        requireUndoBaseline: featureType === 'rewrite',
      });
      const fullDocumentText = htmlToPlainText(prepared.content);
      const selectedText =
        scopeType === 'selection' ? savedSelection?.text?.trim() ?? '' : fullDocumentText;

      if (!selectedText.trim()) {
        throw new Error(
          scopeType === 'selection'
            ? 'Select text in the editor to run AI on just that part.'
            : 'Write something before asking AI to help.'
        );
      }

      const created = await apiJSON(`/documents/${prepared.documentId}/ai/interactions`, {
        method: 'POST',
        body: JSON.stringify({
          feature_type: featureType,
          scope_type: scopeType,
          selected_range:
            scopeType === 'selection'
              ? {
                  start: savedSelection.from,
                  end: savedSelection.to,
                }
              : undefined,
          selected_text_snapshot: selectedText,
          surrounding_context: buildContext({
            scopeType,
            documentTitle: prepared.title,
            documentText: fullDocumentText,
          }),
          user_instruction: instruction.trim() || undefined,
          base_revision: prepared.revision,
          parameters: {},
        }),
      });

      if (!isMountedRef.current) {
        return;
      }

      setInteractionId(created.interaction_id);
      setStatusMessage(
        scopeType === 'selection'
          ? 'AI is working on the selected text...'
          : 'AI is working on your document...'
      );

      const detail = await pollInteraction(created.interaction_id);

      if (!isMountedRef.current) {
        return;
      }

      setInteractionId(detail.interaction_id);
      setResult({
        interactionId: detail.interaction_id,
        suggestionId: detail.suggestion?.suggestion_id ?? '',
        output: detail.suggestion?.generated_output ?? '',
        featureType: detail.feature_type,
        scopeType: detail.scope_type,
        baseRevision: detail.base_revision,
        stale: Boolean(detail.suggestion?.stale),
        selectionSnapshot: scopeType === 'selection' ? savedSelection : null,
        documentApplyRange: {
          start: 0,
          end: prepared.content.length,
        },
      });

      if (detail.suggestion?.stale) {
        setStatusMessage('The result is ready, but the document changed afterward.');
      } else if (detail.feature_type === 'summarize') {
        setStatusMessage('Summary ready to review.');
      } else if (detail.feature_type === 'chat_assistant') {
        setStatusMessage('AI response ready.');
      } else {
        setStatusMessage(
          detail.scope_type === 'selection'
            ? 'Rewrite ready for the selected text.'
            : 'Suggestion ready to review.'
        );
      }
    } catch (error) {
      if (!isMountedRef.current) {
        return;
      }

      setInteractionId('');
      setResult(null);
      setErrorMessage(error.message || 'AI request failed.');
    } finally {
      if (isMountedRef.current) {
        setIsRunning(false);
      }
    }
  }

  async function handleApply() {
    if (!result?.suggestionId) {
      return;
    }

    if (result.featureType !== 'rewrite') {
      setErrorMessage('Only rewrite suggestions can be applied.');
      return;
    }

    if (isSuggestionStale) {
      setErrorMessage(
        hasUnsavedChanges
          ? 'You have local edits that are newer than this suggestion. Save them and run AI again.'
          : 'This suggestion is stale because the document changed. Run AI again.'
      );
      return;
    }

    setIsApplying(true);
    setErrorMessage('');

    try {
      if (result.scopeType === 'selection') {
        await applySelectionSuggestion({
          replacement: result.output,
          selection: result.selectionSnapshot,
        });
      } else {
        await applyDocumentSuggestion({
          suggestionId: result.suggestionId,
          applyRange: result.documentApplyRange,
        });
      }

      if (!isMountedRef.current) {
        return;
      }

      setInteractionId('');
      setResult(null);
      setStatusMessage(
        result.scopeType === 'selection'
          ? 'Suggestion applied to the selected text.'
          : 'Suggestion applied to the document.'
      );
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

  async function handleUndoAI() {
    setErrorMessage('');
    setIsUndoing(true);

    try {
      await undoLastAiApply();

      if (!isMountedRef.current) {
        return;
      }

      setInteractionId('');
      setResult(null);
      setStatusMessage('AI change undone.');
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

  async function handleReject() {
    if (!result?.suggestionId) {
      return;
    }

    setErrorMessage('');
    setIsApplying(true);

    try {
      await apiJSON(`/ai/suggestions/${result.suggestionId}/reject`, {
        method: 'POST',
      });

      if (!isMountedRef.current) {
        return;
      }

      setInteractionId('');
      setResult(null);
      setStatusMessage('Suggestion discarded.');
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

  function handleClear() {
    setInteractionId('');
    setResult(null);
    setStatusMessage('');
    setErrorMessage('');
  }

  function handleFeatureChange(event) {
    setFeatureType(event.target.value);
    setInteractionId('');
    setResult(null);
    setStatusMessage('');
    setErrorMessage('');
  }

  return (
    <aside
      className={`ai-sidebar ${isOpen ? 'ai-sidebar-open' : 'ai-sidebar-closed'}`}
      aria-label="AI Assistant"
      aria-hidden={!isOpen}
      data-state={isOpen ? 'open' : 'closed'}
    >
      <div className="ai-sidebar-header">
        <div>
          <h2 className="ai-sidebar-title">AI Assistant</h2>
          <p className="ai-sidebar-subtitle">
            Use AI on the full document or a selected passage, and ask follow-up document
            questions in one place.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost ai-sidebar-close"
          onClick={onClose}
          aria-label="Close AI sidebar"
        >
          Close
        </button>
      </div>

      <div className="ai-sidebar-body">
        {!canUseAI && (
          <div className="ai-sidebar-notice" role="status">
            {getUnavailableMessage({ aiEnabled, role })}
          </div>
        )}

        <div className="ai-control-grid">
          <label className="field-label" htmlFor="ai-feature-type">
            Feature
            <select
              id="ai-feature-type"
              className="field-select"
              value={featureType}
              onChange={handleFeatureChange}
              disabled={!canUseAI || isBusy}
            >
              {FEATURE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field-label" htmlFor="ai-scope-type">
            Scope
            <select
              id="ai-scope-type"
              className="field-select"
              value={scopeType}
              onChange={(event) => setScopeType(event.target.value)}
              disabled={!canUseAI || isBusy}
            >
              <option value="document">Whole document</option>
              <option value="selection" disabled={!savedSelection}>
                Selected text
              </option>
            </select>
          </label>
        </div>

        {savedSelection ? (
          <div className="ai-selection-preview" role="status">
            <span className="ai-selection-label">Saved selection</span>
            <p className="ai-selection-text">{truncateText(savedSelection.text)}</p>
          </div>
        ) : (
          <div className="ai-sidebar-notice" role="status">
            Select text in the editor if you want AI to work on only one part of the
            document.
          </div>
        )}

        <label className="field-label" htmlFor="ai-instruction">
          {instructionCopy.label}
          <textarea
            id="ai-instruction"
            className="field-input ai-textarea"
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            placeholder={instructionCopy.placeholder}
            disabled={!canUseAI || isBusy}
            rows={4}
          />
        </label>

        <button
          type="button"
          className="btn btn-primary btn-full"
          onClick={handleRun}
          disabled={!canUseAI || isBusy}
        >
          {isRunning ? 'Working...' : instructionCopy.runLabel}
        </button>

        {errorMessage && (
          <div className="error-banner ai-inline-state" role="alert">
            {errorMessage}
          </div>
        )}

        {!errorMessage && statusMessage && (
          <div className="ai-sidebar-status" role="status">
            {statusMessage}
          </div>
        )}

        <div className="ai-result-card">
          <div className="ai-result-header">
            <h3 className="ai-result-title">
              {result ? getInstructionCopy(result.featureType).resultLabel : instructionCopy.resultLabel}
            </h3>
            {interactionId && (
              <span className="ai-result-meta">Interaction {interactionId}</span>
            )}
          </div>

          {result ? (
            <>
              {isSuggestionStale && (
                <div className="ai-sidebar-notice ai-sidebar-notice-warning" role="status">
                  {hasUnsavedChanges
                    ? 'This result is older than your local edits.'
                    : 'This result is stale because the document revision changed.'}
                </div>
              )}

              {result.scopeType === 'selection' && result.selectionSnapshot?.text && (
                <div className="ai-selection-preview ai-selection-preview-result" role="status">
                  <span className="ai-selection-label">Selected text</span>
                  <p className="ai-selection-text">
                    {truncateText(result.selectionSnapshot.text)}
                  </p>
                </div>
              )}

              <div className="ai-result-output">{result.output}</div>

              <div className="ai-result-actions">
                {result.featureType === 'rewrite' && (
                  <>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleApply}
                      disabled={isApplying || isRunning || isUndoing || isSuggestionStale}
                    >
                      {isApplying ? 'Applying...' : 'Apply'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleReject}
                      disabled={isApplying || isRunning || isUndoing}
                    >
                      Reject
                    </button>
                  </>
                )}
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={handleClear}
                  disabled={isApplying || isRunning || isUndoing}
                >
                  Clear
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="ai-result-empty">
                {canUseAI
                  ? `${documentTitle || 'This document'} is ready for AI help.`
                  : 'AI actions are unavailable here.'}
              </div>
              {lastAiUndo && canUseAI && (
                <div className="ai-result-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleUndoAI}
                    disabled={isBusy}
                  >
                    {isUndoing ? 'Undoing...' : 'Undo AI'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
