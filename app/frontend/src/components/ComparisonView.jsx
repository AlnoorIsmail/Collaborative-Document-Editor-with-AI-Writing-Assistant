export default function ComparisonView({
  originalText,
  suggestionText,
  scope = 'document',
}) {
  if (!originalText && !suggestionText) {
    return null;
  }

  return (
    <div className="ai-compare-card">
      <div className="panel-heading">
        <div>
          <h3>Compare</h3>
          <p>{scope === 'selection' ? 'Selected text vs suggestion' : 'Document text vs suggestion'}</p>
        </div>
      </div>

      <div className="ai-compare-grid">
        <div className="ai-compare-pane">
          <span className="ai-compare-label">Original</span>
          <pre>{originalText || 'No source text available yet.'}</pre>
        </div>

        <div className="ai-compare-pane">
          <span className="ai-compare-label">Suggestion</span>
          <pre>{suggestionText || 'No suggestion yet.'}</pre>
        </div>
      </div>
    </div>
  );
}
