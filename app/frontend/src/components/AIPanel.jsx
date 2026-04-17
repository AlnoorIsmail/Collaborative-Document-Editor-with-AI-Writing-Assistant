import ComparisonView from './ComparisonView';

function getStatusLabel(status) {
  if (status === 'streaming') return 'Streaming';
  if (status === 'ready') return 'Ready';
  if (status === 'accepted') return 'Accepted';
  if (status === 'cancelled') return 'Cancelled';
  if (status === 'error') return 'Error';
  return 'Idle';
}

function formatFeature(feature) {
  if (!feature) return 'AI action';
  return feature.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDateTime(value) {
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function AIPanel({
  role,
  aiEnabled,
  aiForm,
  aiState,
  aiHistory,
  selectionState,
  undoState,
  onFeatureChange,
  onInstructionChange,
  onGenerateSuggestion,
  onCancelSuggestion,
  onClearSuggestion,
  onSuggestionChange,
  onAcceptSuggestion,
  onRejectSuggestion,
  onUndoSuggestion,
}) {
  const canUseAi = aiEnabled && role !== 'viewer';
  const isStreaming = aiState.status === 'streaming';
  const selectedText = selectionState.text.trim();
  const suggestionText = isStreaming ? aiState.output : aiState.editableOutput;
  const hasSuggestion = Boolean(suggestionText || aiState.error);
  const isSummaryMode = aiForm.feature === 'summarize';

  return (
    <section className="side-panel">
      <div className="panel-heading">
        <div>
          <h3>AI assistant</h3>
          <p>Generate, compare, edit, accept, reject, or undo.</p>
        </div>

        <span className={`status-pill ai-status-${aiState.status || 'idle'}`}>
          {getStatusLabel(aiState.status)}
        </span>
      </div>

      <div className="selection-summary">
        <strong>{selectedText ? 'Selected text' : 'Current scope'}</strong>
        <p>
          {selectedText ||
            'No selection detected. The AI action will use the full document content.'}
        </p>
      </div>

      {!canUseAi ? (
        <div className="error-banner">
          {role === 'viewer'
            ? 'Viewer mode is read-only. AI actions are disabled.'
            : 'AI is disabled for this document.'}
        </div>
      ) : null}

      <label className="field-label">
        Task
        <select
          className="field-select"
          value={aiForm.feature}
          onChange={(event) => onFeatureChange(event.target.value)}
          disabled={!canUseAi}
        >
          <option value="rewrite">Rewrite</option>
          <option value="summarize">Summarize</option>
          <option value="expand">Expand</option>
          <option value="fix_grammar">Fix grammar</option>
          <option value="custom">Custom prompt</option>
        </select>
      </label>

      <label className="field-label">
        Instruction
        <textarea
          className="field-input ai-textarea"
          value={aiForm.instruction}
          onChange={(event) => onInstructionChange(event.target.value)}
          placeholder="Example: make this clearer for the demo presentation."
          rows={3}
          disabled={!canUseAi}
        />
      </label>

      <div className="panel-button-row">
        <button
          type="button"
          className="btn btn-primary"
          onClick={onGenerateSuggestion}
          disabled={!canUseAi || isStreaming}
          data-testid="generate-ai-button"
        >
          {isStreaming ? 'Generating…' : 'Generate'}
        </button>

        {isStreaming ? (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onCancelSuggestion}
            data-testid="cancel-ai-button"
          >
            Cancel
          </button>
        ) : null}

        {hasSuggestion ? (
          <button type="button" className="btn btn-ghost" onClick={onClearSuggestion}>
            Clear
          </button>
        ) : null}

        {undoState ? (
          <button type="button" className="btn btn-ghost" onClick={onUndoSuggestion}>
            Undo
          </button>
        ) : null}
      </div>

      {aiState.error ? <div className="error-banner">{aiState.error}</div> : null}

      {aiState.partialOutputPreserved ? (
        <div className="panel-note">
          Partial output was preserved so you can still inspect or edit it.
        </div>
      ) : null}

      <ComparisonView
        originalText={aiState.baselineText}
        suggestionText={suggestionText}
        scope={aiState.scope}
      />

      <label className="field-label">
        Editable suggestion
        <textarea
          className="field-input ai-textarea ai-suggestion-editor"
          value={suggestionText}
          onChange={(event) => onSuggestionChange(event.target.value)}
          readOnly={isStreaming || !aiState.interactionId}
          rows={8}
          placeholder="Generated text will appear here."
          data-testid="editable-suggestion"
        />
      </label>

      <div className="panel-button-row">
        <button
          type="button"
          className="btn btn-primary"
          onClick={onAcceptSuggestion}
          disabled={
            !canUseAi ||
            !suggestionText ||
            isSummaryMode ||
            !['ready', 'accepted'].includes(aiState.status)
          }
          data-testid="accept-ai-button"
        >
          Accept
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onRejectSuggestion}
          disabled={!aiState.interactionId || aiState.status !== 'ready'}
          data-testid="reject-ai-button"
        >
          Reject
        </button>
      </div>

      {isSummaryMode ? (
        <div className="panel-note">
          Summaries stay review-only in this flow. Other AI actions can be edited and applied.
        </div>
      ) : null}

      <div className="history-block">
        <div className="panel-heading panel-heading-small">
          <div>
            <h3>AI history</h3>
            <p>Per-document interaction log.</p>
          </div>
        </div>

        {!aiHistory.length ? (
          <div className="side-panel-empty">No AI interactions for this document yet.</div>
        ) : (
          <div className="history-list">
            {aiHistory.map((interaction) => (
              <article key={interaction.id} className="history-item">
                <div className="history-item-top">
                  <strong>{formatFeature(interaction.feature)}</strong>
                  <span className={`mini-pill mini-pill-${interaction.status}`}>
                    {interaction.status.replaceAll('_', ' ')}
                  </span>
                </div>
                <p>{interaction.instruction}</p>
                <div className="history-item-meta">
                  <span>{formatDateTime(interaction.createdAt)}</span>
                  <span>{interaction.scope || 'document'}</span>
                  <span>{interaction.model || 'backend-ai'}</span>
                </div>
                <p className="history-snippet">
                  {(interaction.suggestionText || 'No suggestion text stored yet.').slice(0, 180)}
                </p>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
