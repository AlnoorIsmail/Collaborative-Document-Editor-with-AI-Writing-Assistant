import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiJSON } from '../api';
import Navbar from '../components/Navbar';
import TiptapEditor from '../components/TiptapEditor';
import ShareModal from '../components/ShareModal';
import AISidebar from '../components/AISidebar';
import DocumentHistoryModal from '../components/DocumentHistoryModal';
import ExportModal from '../components/ExportModal';
import PresenceBar from '../components/PresenceBar';
import {
  buildRealtimeSocketUrl,
  clearOfflineDraft,
  readOfflineDraft,
  writeOfflineDraft,
} from '../realtime';

const AUTO_SAVE_DELAY = 1_500;
const REALTIME_SEND_DELAY = 450;

function resolveRole(docData, userData) {
  if (!userData) {
    return 'viewer';
  }

  const ownerId = docData.owner_id || docData.owner_user_id;
  const userId = userData.id || userData.user_id;

  if (ownerId && userId && ownerId === userId) {
    return 'owner';
  }

  const collaborator = (docData.collaborators || []).find(
    (entry) => entry.user_id === userId || entry.email === userData.email
  );

  return collaborator?.role || docData.role || 'viewer';
}

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [doc, setDoc] = useState(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState('owner');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [revision, setRevision] = useState(0);
  const [saveStatus, setSaveStatus] = useState('saved');
  const [selection, setSelection] = useState(null);
  const [lastAiUndo, setLastAiUndo] = useState(null);
  const [isAiOpen, setIsAiOpen] = useState(true);
  const [showShare, setShowShare] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [presence, setPresence] = useState([]);
  const [realtimeStatus, setRealtimeStatus] = useState('connecting');
  const [realtimeMessage, setRealtimeMessage] = useState('');
  const [conflictState, setConflictState] = useState(null);
  const [error, setError] = useState('');

  const editorRef = useRef(null);
  const docRef = useRef(null);
  const contentRef = useRef('');
  const titleRef = useRef('');
  const revisionRef = useRef(0);
  const userRef = useRef(null);
  const selectionRef = useRef(null);
  const lastAiUndoRef = useRef(null);
  const isDirtyRef = useRef(false);
  const savePromiseRef = useRef(null);
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  const applyDocumentState = useCallback((docData, userData = userRef.current) => {
    setDoc(docData);
    docRef.current = docData;
    setTitle(docData.title || '');
    titleRef.current = docData.title || '';

    const initialContent = docData.current_content || docData.content || '';
    setContent(initialContent);
    contentRef.current = initialContent;

    const nextRevision = docData.revision ?? 0;
    setRevision(nextRevision);
    revisionRef.current = nextRevision;
    setSelection(null);
    selectionRef.current = null;
    isDirtyRef.current = false;
    setSaveStatus('saved');
    setError('');
    setRole(resolveRole(docData, userData));
  }, []);

  const clearLastAiUndo = useCallback(() => {
    lastAiUndoRef.current = null;
    setLastAiUndo(null);
  }, []);

  const rememberLastAiUndo = useCallback((undoSnapshot) => {
    lastAiUndoRef.current = undoSnapshot;
    setLastAiUndo(undoSnapshot);
  }, []);

  const refreshDocument = useCallback(async () => {
    const docData = await apiJSON(`/documents/${id}`);
    applyDocumentState(docData);
    return docData;
  }, [applyDocumentState, id]);

  const syncRealtimeDocument = useCallback(
    ({
      nextContent,
      nextRevision,
      nextLatestVersionId,
      updatedAt,
    }) => {
      setContent(nextContent);
      contentRef.current = nextContent;
      setRevision(nextRevision);
      revisionRef.current = nextRevision;
      isDirtyRef.current = false;
      setSaveStatus('saved');
      setDoc((current) => {
        if (!current) {
          return current;
        }

        const nextDoc = {
          ...current,
          current_content: nextContent,
          revision: nextRevision,
          latest_version_id: nextLatestVersionId ?? current.latest_version_id,
          updated_at: updatedAt ?? current.updated_at,
        };
        docRef.current = nextDoc;
        return nextDoc;
      });
      clearOfflineDraft(id);
    },
    [id]
  );

  useEffect(() => {
    clearLastAiUndo();
  }, [clearLastAiUndo, id]);

  useEffect(() => {
    Promise.all([
      apiJSON(`/documents/${id}`),
      apiJSON('/auth/me'),
    ])
      .then(([docData, userData]) => {
        userRef.current = userData;
        setUser(userData);
        applyDocumentState(docData, userData);
        const recoveredDraft = readOfflineDraft(id);
        if (recoveredDraft?.content && recoveredDraft.content !== (docData.current_content || '')) {
          setContent(recoveredDraft.content);
          contentRef.current = recoveredDraft.content;
          if (typeof recoveredDraft.revision === 'number') {
            setRevision(recoveredDraft.revision);
            revisionRef.current = recoveredDraft.revision;
          }
          isDirtyRef.current = true;
          setSaveStatus('unsaved');
          setRealtimeMessage('Recovered an unsent local draft from a disconnected session.');
        }
      })
      .catch(err => {
        if (err.status === 404) navigate('/');
        else setError(err.message);
      });
  }, [applyDocumentState, id, navigate]);

  const performSaveContent = useCallback(async ({ force = false } = {}) => {
    if (role === 'viewer') return true;
    if (!isDirtyRef.current && !force) return true;

    const contentToSave = contentRef.current;
    const baseRevision = revisionRef.current;
    setSaveStatus('saving');
    try {
      const saved = await apiJSON(`/documents/${id}/content`, {
        method: 'PATCH',
        body: JSON.stringify({
          content: contentToSave,
          base_revision: baseRevision,
        }),
      });

      setRevision(saved.revision);
      revisionRef.current = saved.revision;
      setDoc((current) =>
        {
          const nextDoc =
            current
              ? {
                  ...current,
                  current_content: contentToSave,
                  revision: saved.revision,
                  latest_version_id: saved.latest_version_id,
                }
              : current;
          docRef.current = nextDoc;
          return nextDoc;
        }
      );

      const hasNewUnsavedChanges = contentRef.current !== contentToSave;
      isDirtyRef.current = hasNewUnsavedChanges;
      setSaveStatus(hasNewUnsavedChanges ? 'unsaved' : 'saved');
      return !hasNewUnsavedChanges;
    } catch {
      setSaveStatus('unsaved');
      return false;
    }
  }, [id, role]);

  useEffect(() => {
    savePromiseRef.current = null;
  }, [id]);

  const saveContent = useCallback(async ({ force = false } = {}) => {
    if (savePromiseRef.current) {
      await savePromiseRef.current;
      if (!isDirtyRef.current && !force) {
        return true;
      }
    }

    const savePromise = performSaveContent({ force });
    savePromiseRef.current = savePromise;

    try {
      return await savePromise;
    } finally {
      if (savePromiseRef.current === savePromise) {
        savePromiseRef.current = null;
      }
    }
  }, [performSaveContent]);

  const ensureSavedDocument = useCallback(async ({ requireUndoBaseline = false } = {}) => {
    const saved = await saveContent();

    if (!saved) {
      throw new Error('Save the latest document changes before using AI.');
    }

    if (requireUndoBaseline && !docRef.current?.latest_version_id) {
      const baselineSave = await apiJSON(`/documents/${id}/content`, {
        method: 'PATCH',
        body: JSON.stringify({
          content: contentRef.current,
          base_revision: revisionRef.current,
        }),
      });

      setRevision(baselineSave.revision);
      revisionRef.current = baselineSave.revision;
      isDirtyRef.current = false;
      setSaveStatus('saved');
      setDoc((current) => {
        const nextDoc =
          current
            ? {
                ...current,
                current_content: contentRef.current,
                revision: baselineSave.revision,
                latest_version_id: baselineSave.latest_version_id,
              }
            : current;
        docRef.current = nextDoc;
        return nextDoc;
      });
    }

    return {
      documentId: id,
      title: titleRef.current,
      content: contentRef.current,
      revision: revisionRef.current,
      latestVersionId: docRef.current?.latest_version_id ?? null,
    };
  }, [id, saveContent]);

  useEffect(() => {
    if (role === 'viewer' || !doc || saveStatus !== 'unsaved' || realtimeStatus === 'connected') {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      void saveContent();
    }, AUTO_SAVE_DELAY);

    return () => window.clearTimeout(timer);
  }, [content, doc, role, saveContent, saveStatus]);

  useEffect(() => {
    function handleUnload() {
      if (isDirtyRef.current) {
        const token = localStorage.getItem('access_token');
        if (!token) {
          return;
        }

        fetch(`/v1/documents/${id}/content`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            content: contentRef.current,
            base_revision: revisionRef.current,
          }),
          keepalive: true,
        }).catch(() => {});
      }
    }
    window.addEventListener('beforeunload', handleUnload);
    return () => window.removeEventListener('beforeunload', handleUnload);
  }, [id]);

  function handleContentChange(newContent) {
    clearLastAiUndo();
    setContent(newContent);
    contentRef.current = newContent;
    setSelection(null);
    selectionRef.current = null;
    isDirtyRef.current = true;
    setSaveStatus('unsaved');
    setRealtimeMessage('');
    writeOfflineDraft(id, {
      content: newContent,
      revision: revisionRef.current,
      updatedAt: Date.now(),
    });

    if (
      typeof WebSocket !== 'undefined'
      && socketRef.current?.readyState === WebSocket.OPEN
    ) {
      socketRef.current.send(JSON.stringify({ type: 'typing', active: true }));
    }
  }

  function handleSelectionUpdate(nextSelection) {
    if (!nextSelection?.text?.trim()) {
      return;
    }

    setSelection(nextSelection);
    selectionRef.current = nextSelection;
  }

  async function handleTitleChange(newTitle) {
    clearLastAiUndo();
    try {
      const updated = await apiJSON(`/documents/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: newTitle }),
      });
      titleRef.current = updated.title;
      setTitle(updated.title);
      setDoc((current) => {
        if (!current) {
          return current;
        }

        const nextDoc = {
          ...current,
          title: updated.title,
          ai_enabled: updated.ai_enabled,
          updated_at: updated.updated_at,
        };
        docRef.current = nextDoc;
        return nextDoc;
      });
    } catch {
      // non-critical, ignore
    }
  }

  function handleSaveNow() {
    saveContent({ force: true });
  }

  const handleRestoreVersion = useCallback(async (version) => {
    const saved = await saveContent({ force: true });
    if (!saved) {
      throw new Error('Save the latest document changes before restoring a version.');
    }

    clearLastAiUndo();
    await apiJSON(`/documents/${id}/versions/${version.version_id}/restore`, {
      method: 'POST',
    });
    await refreshDocument();
  }, [clearLastAiUndo, id, refreshDocument, saveContent]);

  const getAiUndoSnapshot = useCallback(() => {
    const currentDoc = docRef.current;
    const latestVersionId = currentDoc?.latest_version_id;

    if (!latestVersionId) {
      throw new Error('No saved document version is available for AI undo.');
    }

    return {
      versionId: latestVersionId,
      revision: revisionRef.current,
    };
  }, []);

  const applyDocumentSuggestion = useCallback(async ({ suggestionId, applyRange }) => {
    clearLastAiUndo();
    const undoSnapshot = getAiUndoSnapshot();

    await apiJSON(`/ai/suggestions/${suggestionId}/accept`, {
      method: 'POST',
      body: JSON.stringify({
        apply_to_range: applyRange,
      }),
    });

    await refreshDocument();
    rememberLastAiUndo(undoSnapshot);
  }, [clearLastAiUndo, getAiUndoSnapshot, refreshDocument, rememberLastAiUndo]);

  const applySelectionSuggestion = useCallback(async ({ replacement, selection: selectionOverride }) => {
    clearLastAiUndo();
    const undoSnapshot = getAiUndoSnapshot();
    const savedSelection = selectionOverride ?? selectionRef.current;
    const editor = editorRef.current;

    if (!savedSelection?.text?.trim() || !editor?.replaceRange) {
      throw new Error('Select text in the editor before applying this AI suggestion.');
    }

    const applied = editor.replaceRange({
      from: savedSelection.from,
      to: savedSelection.to,
      text: replacement,
    });

    if (!applied?.applied) {
      throw new Error('The selected text could not be updated. Try selecting it again.');
    }

    setContent(applied.html);
    contentRef.current = applied.html;
    setSelection(null);
    selectionRef.current = null;
    isDirtyRef.current = true;
    setSaveStatus('unsaved');

    const saved = await saveContent({ force: true });

    if (!saved) {
      throw new Error('The AI text was inserted, but saving failed. Try saving again.');
    }

    await refreshDocument();
    rememberLastAiUndo(undoSnapshot);
  }, [clearLastAiUndo, getAiUndoSnapshot, refreshDocument, rememberLastAiUndo, saveContent]);

  const undoLastAiApply = useCallback(async () => {
    const undoSnapshot = lastAiUndoRef.current;

    if (!undoSnapshot?.versionId) {
      throw new Error('There is no applied AI change to undo.');
    }

    try {
      await apiJSON(`/documents/${id}/versions/${undoSnapshot.versionId}/restore`, {
        method: 'POST',
      });
      await refreshDocument();
      clearLastAiUndo();
    } catch (error) {
      clearLastAiUndo();
      throw error;
    }
  }, [clearLastAiUndo, id, refreshDocument]);

  async function handleBack() {
    const saved = await saveContent({ force: true });
    if (saved) {
      navigate('/');
    }
  }

  const applyRemoteConflictVersion = useCallback(() => {
    if (!conflictState) {
      return;
    }

    syncRealtimeDocument({
      nextContent: conflictState.content,
      nextRevision: conflictState.revision,
      nextLatestVersionId: conflictState.latest_version_id,
    });
    setConflictState(null);
    setRealtimeMessage('Loaded the latest remote version.');
  }, [conflictState, syncRealtimeDocument]);

  const keepLocalDraft = useCallback(() => {
    if (!conflictState || socketRef.current?.readyState !== WebSocket.OPEN) {
      return;
    }

    setRevision(conflictState.revision);
    revisionRef.current = conflictState.revision;
    setDoc((current) => {
      if (!current) {
        return current;
      }

      const nextDoc = {
        ...current,
        revision: conflictState.revision,
        latest_version_id: conflictState.latest_version_id ?? current.latest_version_id,
      };
      docRef.current = nextDoc;
      return nextDoc;
    });
    setConflictState(null);
    setSaveStatus('unsaved');
    socketRef.current.send(
      JSON.stringify({
        type: 'content_update',
        content: contentRef.current,
        base_revision: conflictState.revision,
      })
    );
  }, [conflictState]);

  useEffect(() => {
    if (!doc || !user) {
      return undefined;
    }

    let cancelled = false;
    let reconnectHandle = null;

    async function connectRealtime() {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        return;
      }
      if (typeof WebSocket === 'undefined') {
        setRealtimeStatus('offline');
        setRealtimeMessage('This browser does not support realtime collaboration.');
        return;
      }

      setRealtimeStatus('connecting');

      try {
        const bootstrap = await apiJSON(`/documents/${id}/sessions`, {
          method: 'POST',
          body: JSON.stringify({
            last_known_revision: revisionRef.current,
          }),
        });

        if (cancelled) {
          return;
        }

        const socketUrl = buildRealtimeSocketUrl({
          realtimeUrl: bootstrap.realtime_url,
          documentId: id,
          sessionId: bootstrap.session_id,
          sessionToken: bootstrap.session_token,
          accessToken,
        });

        const nextSocket = new WebSocket(socketUrl);
        socketRef.current = nextSocket;

        nextSocket.onopen = () => {
          if (cancelled) {
            return;
          }
          setRealtimeStatus('connected');
          setRealtimeMessage('');
          setPresence(
            (bootstrap.active_collaborators || []).map((collaborator) => ({
              ...collaborator,
              typing: false,
            }))
          );
        };

        nextSocket.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.type === 'session_joined') {
            setPresence(payload.presence || []);
            setRealtimeStatus('connected');
            return;
          }

          if (payload.type === 'presence_snapshot') {
            setPresence(payload.presence || []);
            return;
          }

          if (payload.type === 'content_updated') {
            const actorUserId = payload.actor_user_id;
            const isOwnUpdate = actorUserId && actorUserId === userRef.current?.user_id;

            if (isOwnUpdate || !isDirtyRef.current) {
              syncRealtimeDocument({
                nextContent: payload.content,
                nextRevision: payload.revision,
                nextLatestVersionId: payload.latest_version_id,
                updatedAt: payload.saved_at,
              });
              setConflictState(null);
              if (!isOwnUpdate && payload.actor_display_name) {
                setRealtimeMessage(`${payload.actor_display_name} updated the document.`);
              } else {
                setRealtimeMessage('');
              }
              return;
            }

            setConflictState({
              content: payload.content,
              revision: payload.revision,
              latest_version_id: payload.latest_version_id,
              message: `${payload.actor_display_name || 'Another collaborator'} updated this document while you were still editing.`,
            });
            return;
          }

          if (payload.type === 'conflict_detected') {
            setConflictState({
              content: payload.content,
              revision: payload.revision,
              latest_version_id: payload.latest_version_id,
              message: payload.message,
            });
            return;
          }

          if (payload.type === 'error') {
            setRealtimeMessage(payload.message || 'Realtime collaboration hit an error.');
          }
        };

        nextSocket.onclose = () => {
          if (cancelled) {
            return;
          }
          socketRef.current = null;
          setRealtimeStatus('offline');
          setRealtimeMessage('Realtime disconnected. Local saves will continue and retry.');
          reconnectHandle = window.setTimeout(() => {
            void connectRealtime();
          }, 1_500);
          reconnectTimerRef.current = reconnectHandle;
        };

        nextSocket.onerror = () => {
          if (!cancelled) {
            setRealtimeStatus('offline');
          }
        };
      } catch (nextError) {
        if (!cancelled) {
          setRealtimeStatus('offline');
          setRealtimeMessage(nextError.message || 'Realtime collaboration is unavailable right now.');
        }
      }
    }

    void connectRealtime();

    return () => {
      cancelled = true;
      if (reconnectHandle) {
        window.clearTimeout(reconnectHandle);
      }
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      setPresence([]);
    };
  }, [doc, id, syncRealtimeDocument, user]);

  useEffect(() => {
    if (
      role === 'viewer'
      || !doc
      || saveStatus !== 'unsaved'
      || realtimeStatus !== 'connected'
      || conflictState
    ) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(
          JSON.stringify({
            type: 'content_update',
            content: contentRef.current,
            base_revision: revisionRef.current,
          })
        );
      }
    }, REALTIME_SEND_DELAY);

    return () => window.clearTimeout(timer);
  }, [conflictState, content, doc, realtimeStatus, role, saveStatus]);

  useEffect(() => {
    if (realtimeStatus !== 'connected' || !socketRef.current) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(
          JSON.stringify({
            type: 'heartbeat',
            last_known_revision: revisionRef.current,
          })
        );
      }
    }, 10_000);

    return () => window.clearInterval(timer);
  }, [realtimeStatus]);

  const isReadOnly = role === 'viewer';

  if (error) {
    return (
      <div className="editor-error">
        <p>{error}</p>
        <button className="btn btn-primary" onClick={() => navigate('/')}>Back to documents</button>
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
        onSaveNow={handleSaveNow}
        onOpenHistory={() => setShowHistory(true)}
        onOpenExport={() => setShowExport(true)}
        onShare={() => setShowShare(true)}
        isOwner={role === 'owner'}
        isReadOnly={isReadOnly}
        canRestoreHistory={role !== 'viewer'}
        onBack={handleBack}
        user={user}
        isAiOpen={isAiOpen}
        onToggleAi={() => setIsAiOpen((current) => !current)}
      />

      {isReadOnly && (
        <div className="readonly-banner">
          You have view-only access to this document.
        </div>
      )}

      <PresenceBar
        users={presence}
        currentUserId={user?.user_id ?? user?.id ?? null}
        realtimeStatus={realtimeStatus}
        realtimeMessage={realtimeMessage}
        conflictState={conflictState}
        onAcceptRemote={applyRemoteConflictVersion}
        onKeepLocal={keepLocalDraft}
      />

      <div
        className={`editor-layout ${isAiOpen ? 'editor-layout-ai-open' : 'editor-layout-ai-closed'}`}
      >
        <div className="editor-main">
          <TiptapEditor
            ref={editorRef}
            content={content}
            onChange={handleContentChange}
            onSelectionUpdate={handleSelectionUpdate}
            readOnly={isReadOnly}
            placeholder="Start writing…"
          />
        </div>

        {isAiOpen && (
          <button
            type="button"
            className="ai-sidebar-backdrop"
            onClick={() => setIsAiOpen(false)}
            aria-label="Dismiss AI sidebar overlay"
          />
        )}

        <AISidebar
          documentId={id}
          documentTitle={title}
          content={content}
          currentRevision={revision}
          role={role}
          aiEnabled={Boolean(doc.ai_enabled)}
          selection={selection}
          hasUnsavedChanges={saveStatus !== 'saved'}
          ensureSavedDocument={ensureSavedDocument}
          lastAiUndo={lastAiUndo}
          applyDocumentSuggestion={applyDocumentSuggestion}
          applySelectionSuggestion={applySelectionSuggestion}
          undoLastAiApply={undoLastAiApply}
          isOpen={isAiOpen}
          onClose={() => setIsAiOpen(false)}
        />
      </div>

      {showShare && (
        <ShareModal
          docId={id}
          onClose={() => setShowShare(false)}
        />
      )}

      {showHistory && (
        <DocumentHistoryModal
          docId={id}
          currentRevision={revision}
          canRestore={role !== 'viewer'}
          onClose={() => setShowHistory(false)}
          onRestoreVersion={handleRestoreVersion}
        />
      )}

      {showExport && (
        <ExportModal
          docId={id}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  );
}
