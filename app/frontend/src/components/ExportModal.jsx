import { useState } from 'react';
import { apiJSON } from '../api';

const FORMATS = [
  { value: 'html', label: 'HTML (.html)' },
  { value: 'plain_text', label: 'Plain text (.txt)' },
  { value: 'markdown', label: 'Markdown (.md)' },
  { value: 'json', label: 'JSON (.json)' },
];

function downloadExport({ content, filename, contentType }) {
  const blob = new Blob([content], { type: contentType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

export default function ExportModal({ docId, onClose }) {
  const [format, setFormat] = useState('html');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleExport(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await apiJSON(`/documents/${docId}/export`, {
        method: 'POST',
        body: JSON.stringify({ format }),
      });
      downloadExport({
        content: response.exported_content,
        filename: response.filename,
        contentType: response.content_type,
      });
      onClose();
    } catch (nextError) {
      setError(nextError.message || 'Failed to export the document.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Export document">
        <div className="modal-header">
          <h2 className="modal-title">Export document</h2>
          <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
            &#10005;
          </button>
        </div>

        <div className="modal-body">
          <p className="share-helper-text">
            Download the current saved document in one of the available export formats. HTML keeps
            rich formatting most faithfully.
          </p>

          <form className="share-form" onSubmit={handleExport}>
            <label className="field-label">
              Export format
              <select
                className="field-select"
                value={format}
                onChange={(event) => setFormat(event.target.value)}
              >
                {FORMATS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            {error && <div className="error-banner">{error}</div>}

            <div className="modal-actions">
              <button className="btn btn-ghost" type="button" onClick={onClose}>
                Cancel
              </button>
              <button className="btn btn-primary" type="submit" disabled={loading}>
                {loading ? 'Exporting…' : 'Download export'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
