function truncateText(text, limit = 220) {
  const normalized = (text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return 'No preview available.';
  }
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit).trim()}...`;
}

function rangeLabel(range) {
  if (!range) {
    return 'Unknown range';
  }
  return `${range.start}-${range.end}`;
}

export default function ConflictResolutionTray({
  conflict,
  role,
  resolutionDraft,
  onResolutionDraftChange,
  onUseCandidate,
  onResolveManual,
  onAskAiMerge,
  onAcceptAiMerge,
  onRejectAiMerge,
  onUseAiMergeAsDraft,
  aiMergeState,
  resolving,
}) {
  if (!conflict) {
    return null;
  }

  const canResolve = role === 'owner' || role === 'editor';
  const isStale = Boolean(conflict.stale || conflict.status === 'stale');

  return (
    <aside className="conflict-resolution-tray" aria-label="Conflict resolution">
      <div className="conflict-resolution-header">
        <div>
          <h3 className="conflict-resolution-title">Resolve overlapping edits</h3>
          <p className="conflict-resolution-subtitle">
            {isStale
              ? 'The original conflict region moved. Review the preserved alternatives and resolve it manually.'
              : `Conflict range ${rangeLabel(conflict.anchor_range)} with ${conflict.candidates.length} preserved alternatives.`}
          </p>
        </div>
        <span className={`conflict-resolution-status conflict-resolution-status-${isStale ? 'stale' : 'open'}`}>
          {isStale ? 'Stale conflict' : 'Unresolved conflict'}
        </span>
      </div>

      <div className="conflict-resolution-region">
        <span className="conflict-resolution-label">Current region</span>
        <p>{truncateText(conflict.exact_text_snapshot)}</p>
      </div>

      <div className="conflict-resolution-candidates">
        {conflict.candidates.map((candidate) => (
          <section key={candidate.candidate_id} className="conflict-candidate-card">
            <div className="conflict-candidate-header">
              <strong>{candidate.user_display_name}</strong>
              <span>Range {rangeLabel(candidate.range)}</span>
            </div>
            <p className="conflict-candidate-preview">
              {truncateText(candidate.candidate_content_snapshot)}
            </p>
            {canResolve ? (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => onUseCandidate(candidate)}
                disabled={resolving}
              >
                {candidate.user_id ? `Use ${candidate.user_display_name}'s version` : 'Use this version'}
              </button>
            ) : null}
          </section>
        ))}
      </div>

      {canResolve ? (
        <div className="conflict-resolution-manual">
          <label className="field-label" htmlFor="conflict-resolution-draft">
            Final merged content
          </label>
          <textarea
            id="conflict-resolution-draft"
            className="field-input ai-textarea"
            value={resolutionDraft}
            onChange={(event) => onResolutionDraftChange(event.target.value)}
            disabled={resolving}
            placeholder="Edit the final merged result here."
          />
          <div className="conflict-resolution-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={onResolveManual}
              disabled={resolving || !resolutionDraft.trim()}
            >
              Save resolution
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onAskAiMerge}
              disabled={resolving || aiMergeState.loading}
            >
              {aiMergeState.loading ? 'Merging...' : 'Ask AI to merge'}
            </button>
          </div>
        </div>
      ) : null}

      {aiMergeState.error ? (
        <div className="ai-sidebar-notice ai-sidebar-notice-warning">
          {aiMergeState.error}
        </div>
      ) : null}

      {aiMergeState.suggestion ? (
        <section className="conflict-ai-suggestion">
          <div className="conflict-ai-suggestion-header">
            <strong>AI merge suggestion</strong>
            <span>{aiMergeState.partial ? 'Partial output' : 'Ready for review'}</span>
          </div>
          <p className="conflict-ai-suggestion-body">
            {aiMergeState.suggestion.generated_output || 'The AI merge suggestion is empty.'}
          </p>
          {canResolve ? (
            <div className="conflict-resolution-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={onAcceptAiMerge}
                disabled={resolving}
              >
                Accept AI merge
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onUseAiMergeAsDraft}
                disabled={resolving}
              >
                Edit before apply
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onRejectAiMerge}
                disabled={resolving}
              >
                Reject AI merge
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      {!canResolve ? (
        <div className="ai-sidebar-notice">
          Your role can review unresolved conflicts, but only owners and editors can resolve them.
        </div>
      ) : null}
    </aside>
  );
}
