import { useEffect, useMemo, useState } from 'react';
import { apiJSON } from '../api';

function formatVersionDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function DocumentHistoryModal({
  docId,
  currentRevision,
  canRestore,
  onClose,
  onRestoreVersion,
}) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [restoringId, setRestoringId] = useState(null);
  const [showAutosaves, setShowAutosaves] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadVersions() {
      setLoading(true);
      setError('');
      try {
        const nextVersions = await apiJSON(`/documents/${docId}/versions`);
        if (!cancelled) {
          setVersions(nextVersions);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError.message || 'Failed to load version history.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadVersions();

    return () => {
      cancelled = true;
    };
  }, [docId]);

  const currentVersionId = useMemo(
    () => versions.find((version) => version.version_number === currentRevision)?.version_id ?? null,
    [currentRevision, versions]
  );

  const autosaveVersions = useMemo(
    () => versions.filter((version) => version.save_source === 'autosave'),
    [versions]
  );

  const visibleVersions = useMemo(() => {
    if (showAutosaves) {
      return versions;
    }

    const nonAutosaveVersions = versions.filter((version) => version.save_source !== 'autosave');
    if (nonAutosaveVersions.length > 0) {
      return nonAutosaveVersions;
    }

    return autosaveVersions.length > 0 ? [autosaveVersions[0]] : [];
  }, [autosaveVersions, showAutosaves, versions]);

  const isShowingAutosaveFallback =
    !showAutosaves
    && visibleVersions.length === 1
    && visibleVersions[0]?.save_source === 'autosave'
    && autosaveVersions.length === versions.length
    && autosaveVersions.length > 0;

  function getSaveSourceLabel(version) {
    if (version.save_source === 'restore' || version.is_restore_version) {
      return 'Restore';
    }

    if (version.save_source === 'autosave') {
      return 'Autosave';
    }

    return 'Manual save';
  }

  function getSaveSourceBadgeClass(version) {
    if (version.save_source === 'restore' || version.is_restore_version) {
      return 'history-badge history-badge-restore';
    }

    if (version.save_source === 'autosave') {
      return 'history-badge history-badge-autosave';
    }

    return 'history-badge history-badge-manual';
  }

  async function handleRestore(version) {
    const confirmed = window.confirm(
      `Restore version ${version.version_number}? This will create a new version entry.`
    );
    if (!confirmed) {
      return;
    }

    setRestoringId(version.version_id);
    setError('');
    try {
      await onRestoreVersion(version);
      onClose();
    } catch (nextError) {
      setError(nextError.message || 'Failed to restore this version.');
    } finally {
      setRestoringId(null);
    }
  }

  return (
    <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal modal-wide modal-tall" role="dialog" aria-modal="true" aria-label="Version history">
        <div className="modal-header">
          <h2 className="modal-title">Version history</h2>
          <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
            &#10005;
          </button>
        </div>

        <div className="modal-body modal-scroll">
          <div className="history-header">
            <p className="share-helper-text">
              Review previous saved snapshots and restore an earlier state without deleting later
              history.
            </p>
            {autosaveVersions.length > 0 ? (
              <button
                type="button"
                className="btn btn-secondary history-toggle"
                onClick={() => setShowAutosaves((current) => !current)}
              >
                {showAutosaves ? 'Hide autosaves' : 'Show autosaves'}
              </button>
            ) : null}
          </div>

          {error && <div className="error-banner">{error}</div>}

          {loading ? (
            <div className="history-empty-state">Loading versions…</div>
          ) : versions.length === 0 ? (
            <div className="history-empty-state">No saved versions yet.</div>
          ) : (
            <div className="history-list" role="list">
              {isShowingAutosaveFallback ? (
                <div className="history-helper-note">
                  Only autosave snapshots exist so far. Open autosaves if you want to browse the
                  full background-save history.
                </div>
              ) : null}

              {visibleVersions.map((version) => {
                const isCurrent = version.version_id === currentVersionId;
                return (
                  <div className="history-card" role="listitem" key={version.version_id}>
                    <div className="history-card-main">
                      <div className="history-card-top">
                        <strong>Version {version.version_number}</strong>
                        <div className="history-card-badges">
                          {isCurrent ? <span className="history-badge">Current</span> : null}
                          <span className={getSaveSourceBadgeClass(version)}>
                            {getSaveSourceLabel(version)}
                          </span>
                        </div>
                      </div>
                      <p className="history-card-meta">
                        Saved {formatVersionDate(version.created_at)} by user {version.created_by}
                      </p>
                    </div>

                    {canRestore && !isCurrent ? (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => handleRestore(version)}
                        disabled={restoringId === version.version_id}
                      >
                        {restoringId === version.version_id ? 'Restoring…' : 'Restore'}
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
