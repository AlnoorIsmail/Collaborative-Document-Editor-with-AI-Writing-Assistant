function formatDateTime(value) {
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function getVersionLabel(version) {
  return version.is_restore_version
    ? `Restored version ${version.version_number}`
    : `Version ${version.version_number}`;
}

export default function VersionHistoryPanel({
  versions,
  isLoading,
  errorMessage,
  canManageVersions,
  onRefresh,
  onRestoreVersion,
}) {
  return (
    <section className="side-panel">
      <div className="panel-heading">
        <div>
          <h3>Version history</h3>
          <p>Review previous saves and restore an earlier draft.</p>
        </div>

        <button
          type="button"
          className="btn btn-ghost"
          onClick={onRefresh}
          disabled={isLoading}
        >
          Refresh
        </button>
      </div>

      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}

      {isLoading ? (
        <div className="side-panel-empty">Loading version history…</div>
      ) : null}

      {!isLoading && !versions.length ? (
        <div className="side-panel-empty">No saved versions yet.</div>
      ) : null}

      {!isLoading && versions.length ? (
        <div className="version-list">
          {versions.map((version) => (
            <article key={version.version_id} className="version-item">
              <div className="version-item-main">
                <strong>{getVersionLabel(version)}</strong>
                <span>{formatDateTime(version.created_at)}</span>
              </div>

              <div className="version-item-meta">
                <span>By user {version.created_by}</span>
                {version.is_restore_version ? <span>Restore snapshot</span> : null}
              </div>

              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => onRestoreVersion(version)}
                disabled={!canManageVersions}
              >
                Restore
              </button>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
