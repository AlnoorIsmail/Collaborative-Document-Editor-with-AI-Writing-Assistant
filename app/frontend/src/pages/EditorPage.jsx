import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiFetch, apiJSON } from '../api';
import Navbar from '../components/Navbar';
import TiptapEditor from '../components/TiptapEditor';
import ShareModal from '../components/ShareModal';
import AISidebar from '../components/AISidebar';
import DocumentHistoryModal from '../components/DocumentHistoryModal';
import ExportModal from '../components/ExportModal';
import PresenceBar from '../components/PresenceBar';
import ConflictResolutionTray from '../components/ConflictResolutionTray';
import {
  buildRealtimeSocketUrl,
  clearOfflineDraft,
  readOfflineDraft,
  writeOfflineDraft,
} from '../realtime';
import { buildDocumentPageTitle, usePageTitle } from '../pageTitle';

const AUTO_SAVE_DELAY = 1_500;

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

function resolveUserId(userData) {
  return userData?.user_id ?? userData?.id ?? null;
}

function resolveDisplayName(userData) {
  return userData?.display_name || userData?.displayName || userData?.name || userData?.email || 'You';
}

function rangesOverlap(leftRange, rightRange) {
  if (!leftRange || !rightRange) {
    return false;
  }
  return leftRange.start <= rightRange.end && rightRange.start <= leftRange.end;
}

function makeConflictKey(documentId, localBatchId, remoteBatchId) {
  const orderedBatchIds = [localBatchId, remoteBatchId].sort();
  return `conflict:${documentId}:${orderedBatchIds.join(':')}`;
}

function upsertConflict(conflicts, nextConflict) {
  const existingIndex = conflicts.findIndex(
    (conflict) => conflict.conflict_id === nextConflict.conflict_id
  );
  if (existingIndex === -1) {
    return [...conflicts, nextConflict].sort((left, right) => (
      new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
    ));
  }

  const nextConflicts = [...conflicts];
  nextConflicts[existingIndex] = nextConflict;
  return nextConflicts;
}

function parseSseBlock(block) {
  const lines = block
    .split('\n')
    .map((line) => line.trimEnd())
    .filter(Boolean);

  if (!lines.length) {
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

  if (!dataLines.length) {
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

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [doc, setDoc] = useState(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState('owner');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [lineSpacing, setLineSpacing] = useState(1.15);
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
  const [documentConflicts, setDocumentConflicts] = useState([]);
  const [activeConflictId, setActiveConflictId] = useState(null);
  const [conflictResolutionDraft, setConflictResolutionDraft] = useState('');
  const [conflictResolveLoading, setConflictResolveLoading] = useState(false);
  const [conflictAiMerge, setConflictAiMerge] = useState({
    loading: false,
    error: '',
    interactionId: '',
    suggestion: null,
    partial: false,
  });
  const [collabVersion, setCollabVersion] = useState(null);
  const [collabEnabled, setCollabEnabled] = useState(false);
  const [collabResetKey, setCollabResetKey] = useState(0);
  const [error, setError] = useState('');
  usePageTitle(buildDocumentPageTitle(title || doc?.title));

  const editorRef = useRef(null);
  const docRef = useRef(null);
  const contentRef = useRef('');
  const titleRef = useRef('');
  const revisionRef = useRef(0);
  const lineSpacingRef = useRef(1.15);
  const collabVersionRef = useRef(0);
  const userRef = useRef(null);
  const selectionRef = useRef(null);
  const lastAiUndoRef = useRef(null);
  const isDirtyRef = useRef(false);
  const savePromiseRef = useRef(null);
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const pendingStepBatchesRef = useRef([]);
  const reportedConflictKeysRef = useRef(new Set());

  const applyDocumentState = useCallback((docData, userData = userRef.current) => {
    setDoc(docData);
    docRef.current = docData;
    setTitle(docData.title || '');
    titleRef.current = docData.title || '';

    const initialContent = docData.current_content || docData.content || '';
    setContent(initialContent);
    contentRef.current = initialContent;

    const nextLineSpacing = Number(docData.line_spacing) || 1.15;
    setLineSpacing(nextLineSpacing);
    lineSpacingRef.current = nextLineSpacing;

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

  const loadDocumentConflicts = useCallback(async () => {
    try {
      const conflicts = await apiJSON(`/documents/${id}/conflicts`);
      setDocumentConflicts(conflicts);
      setActiveConflictId((current) => {
        if (current && conflicts.some((conflict) => conflict.conflict_id === current)) {
          return current;
        }
        return conflicts[0]?.conflict_id ?? null;
      });
    } catch {
      // Conflict hydration is secondary to the main editor load and should not block editing.
    }
  }, [id]);

  const syncRealtimeDocument = useCallback(
    ({
      nextContent,
      nextLineSpacing,
      nextRevision,
      nextLatestVersionId,
      updatedAt,
      nextCollabVersion,
      resetCollaboration = false,
    }) => {
      const resolvedLineSpacing = nextLineSpacing ?? lineSpacingRef.current ?? 1.15;
      setContent(nextContent);
      contentRef.current = nextContent;
      setLineSpacing(resolvedLineSpacing);
      lineSpacingRef.current = resolvedLineSpacing;
      setRevision(nextRevision);
      revisionRef.current = nextRevision;
      if (typeof nextCollabVersion === 'number') {
        setCollabVersion(nextCollabVersion);
        collabVersionRef.current = nextCollabVersion;
      }
      if (resetCollaboration) {
        setCollabResetKey((current) => current + 1);
      }
      isDirtyRef.current = false;
      setSaveStatus('saved');
      setDoc((current) => {
        if (!current) {
          return current;
        }

        const nextDoc = {
          ...current,
          current_content: nextContent,
          line_spacing: resolvedLineSpacing ?? current.line_spacing,
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

  const activeDocumentConflict = documentConflicts.find(
    (conflict) => conflict.conflict_id === activeConflictId
  ) ?? null;

  const registerPendingStepBatch = useCallback((payload) => {
    pendingStepBatchesRef.current = [
      ...pendingStepBatchesRef.current.filter((batch) => batch.batchId !== payload.batchId),
      {
        batchId: payload.batchId,
        clientId: payload.clientId,
        version: payload.version,
        affectedRange: payload.affectedRange,
        candidateContentSnapshot: payload.candidateContentSnapshot,
        exactTextSnapshot: payload.exactTextSnapshot,
        prefixContext: payload.prefixContext,
        suffixContext: payload.suffixContext,
        userId: resolveUserId(userRef.current),
        userDisplayName: resolveDisplayName(userRef.current),
      },
    ];
  }, []);

  const clearPendingStepBatch = useCallback((batchId) => {
    pendingStepBatchesRef.current = pendingStepBatchesRef.current.filter(
      (batch) => batch.batchId !== batchId
    );
  }, []);

  const reportOverlapConflict = useCallback(async (localBatch, remoteBatch) => {
    if (!localBatch?.affectedRange || !remoteBatch?.affected_range) {
      return;
    }

    const conflictKey = makeConflictKey(id, localBatch.batchId, remoteBatch.batch_id);
    if (reportedConflictKeysRef.current.has(conflictKey)) {
      return;
    }
    reportedConflictKeysRef.current.add(conflictKey);

    try {
      const nextConflict = await apiJSON(`/documents/${id}/conflicts`, {
        method: 'POST',
        body: JSON.stringify({
          conflict_key: conflictKey,
          source_revision: revisionRef.current,
          source_collab_version: Math.min(localBatch.version, remoteBatch.version ?? localBatch.version),
          local_candidate: {
            batch_id: localBatch.batchId,
            client_id: localBatch.clientId,
            user_id: localBatch.userId,
            user_display_name: localBatch.userDisplayName,
            range: localBatch.affectedRange,
            candidate_content_snapshot: localBatch.candidateContentSnapshot,
            exact_text_snapshot: localBatch.exactTextSnapshot,
            prefix_context: localBatch.prefixContext,
            suffix_context: localBatch.suffixContext,
          },
          remote_candidate: {
            batch_id: remoteBatch.batch_id,
            client_id: remoteBatch.client_id,
            user_id: remoteBatch.actor_user_id,
            user_display_name: remoteBatch.actor_display_name,
            range: remoteBatch.affected_range,
            candidate_content_snapshot: remoteBatch.candidate_content_snapshot,
            exact_text_snapshot: remoteBatch.exact_text_snapshot,
            prefix_context: remoteBatch.prefix_context,
            suffix_context: remoteBatch.suffix_context,
          },
        }),
      });

      setDocumentConflicts((current) => upsertConflict(current, nextConflict));
      setActiveConflictId((current) => current ?? nextConflict.conflict_id);
      setRealtimeMessage('Overlapping edits were preserved for manual resolution.');
    } catch {
      // Keep the local draft and remote sync; conflict persistence can be retried by reload/reconnect.
    }
  }, [id]);

  useEffect(() => {
    clearLastAiUndo();
    setCollabVersion(null);
    collabVersionRef.current = 0;
    setCollabEnabled(false);
    setCollabResetKey((current) => current + 1);
    setDocumentConflicts([]);
    setActiveConflictId(null);
    setConflictResolutionDraft('');
    setConflictAiMerge({
      loading: false,
      error: '',
      interactionId: '',
      suggestion: null,
      partial: false,
    });
    pendingStepBatchesRef.current = [];
    reportedConflictKeysRef.current = new Set();
  }, [clearLastAiUndo, id]);

  useEffect(() => {
    if (!activeDocumentConflict) {
      setConflictResolutionDraft('');
      setConflictAiMerge({
        loading: false,
        error: '',
        interactionId: '',
        suggestion: null,
        partial: false,
      });
      return;
    }

    setConflictResolutionDraft(
      activeDocumentConflict.resolved_content
      || activeDocumentConflict.candidates?.[0]?.candidate_content_snapshot
      || activeDocumentConflict.exact_text_snapshot
      || ''
    );
    setConflictAiMerge({
      loading: false,
      error: '',
      interactionId: '',
      suggestion: null,
      partial: false,
    });
  }, [activeDocumentConflict]);

  useEffect(() => {
    Promise.all([
      apiJSON(`/documents/${id}`),
      apiJSON('/auth/me'),
    ])
      .then(([docData, userData]) => {
        userRef.current = userData;
        setUser(userData);
        applyDocumentState(docData, userData);
        void loadDocumentConflicts();
        const recoveredDraft = readOfflineDraft(id);
        const recoveredContent = recoveredDraft?.content;
        const recoveredLineSpacing = Number(recoveredDraft?.lineSpacing);
        const contentChanged =
          typeof recoveredContent === 'string'
          && recoveredContent !== (docData.current_content || '');
        const lineSpacingChanged =
          Number.isFinite(recoveredLineSpacing)
          && recoveredLineSpacing !== (Number(docData.line_spacing) || 1.15);

        if (contentChanged || lineSpacingChanged) {
          if (contentChanged) {
            setContent(recoveredContent);
            contentRef.current = recoveredContent;
          }
          if (lineSpacingChanged) {
            setLineSpacing(recoveredLineSpacing);
            lineSpacingRef.current = recoveredLineSpacing;
          }
          setDoc((current) => {
            if (!current) {
              return current;
            }

            const nextDoc = {
              ...current,
              current_content: contentChanged ? recoveredContent : current.current_content,
              line_spacing: lineSpacingChanged ? recoveredLineSpacing : current.line_spacing,
            };
            docRef.current = nextDoc;
            return nextDoc;
          });
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
  }, [applyDocumentState, id, loadDocumentConflicts, navigate]);

  const performSaveContent = useCallback(async ({ force = false, saveSource = 'manual' } = {}) => {
    if (role === 'viewer') return true;
    if (!isDirtyRef.current && !force) return true;

    const contentToSave = contentRef.current;
    const lineSpacingToSave = lineSpacingRef.current;
    const baseRevision = revisionRef.current;
    setSaveStatus('saving');
    try {
      const saved = await apiJSON(`/documents/${id}/content`, {
        method: 'PATCH',
        body: JSON.stringify({
          content: contentToSave,
          base_revision: baseRevision,
          line_spacing: lineSpacingToSave,
          save_source: saveSource,
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
                  line_spacing: saved.line_spacing ?? lineSpacingToSave,
                  revision: saved.revision,
                  latest_version_id: saved.latest_version_id,
                }
              : current;
          docRef.current = nextDoc;
          return nextDoc;
        }
      );

      const hasNewUnsavedChanges =
        contentRef.current !== contentToSave || lineSpacingRef.current !== lineSpacingToSave;
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

  const saveContent = useCallback(async ({ force = false, saveSource = 'manual' } = {}) => {
    if (savePromiseRef.current) {
      await savePromiseRef.current;
      if (!isDirtyRef.current && !force) {
        return true;
      }
    }

    const savePromise = performSaveContent({ force, saveSource });
    savePromiseRef.current = savePromise;

    try {
      return await savePromise;
    } finally {
      if (savePromiseRef.current === savePromise) {
        savePromiseRef.current = null;
      }
    }
  }, [performSaveContent]);

  const broadcastFullSnapshotUpdate = useCallback((saveSource = 'manual') => {
    if (
      typeof WebSocket === 'undefined'
      || socketRef.current?.readyState !== WebSocket.OPEN
    ) {
      return;
    }

    socketRef.current.send(
      JSON.stringify({
        type: 'snapshot_update',
        content: contentRef.current,
        line_spacing: lineSpacingRef.current,
        revision: revisionRef.current,
        save_source: saveSource,
      })
    );
  }, []);

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
          line_spacing: lineSpacingRef.current,
          save_source: 'manual',
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
                line_spacing: baselineSave.line_spacing ?? lineSpacingRef.current,
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
      lineSpacing: lineSpacingRef.current,
      revision: revisionRef.current,
      latestVersionId: docRef.current?.latest_version_id ?? null,
    };
  }, [id, saveContent]);

  useEffect(() => {
    if (role === 'viewer' || !doc || saveStatus !== 'unsaved') {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      void saveContent({ saveSource: 'autosave' });
    }, AUTO_SAVE_DELAY);

    return () => window.clearTimeout(timer);
  }, [content, doc, lineSpacing, role, saveContent, saveStatus]);

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
            line_spacing: lineSpacingRef.current,
            save_source: 'autosave',
          }),
          keepalive: true,
        }).catch(() => {});
      }
    }
    window.addEventListener('beforeunload', handleUnload);
    return () => window.removeEventListener('beforeunload', handleUnload);
  }, [id]);

  function handleContentChange(newContent, meta = {}) {
    const isRemote = Boolean(meta.isRemote);
    const hadUnsavedChanges = isDirtyRef.current;
    if (!isRemote) {
      clearLastAiUndo();
    }
    setContent(newContent);
    contentRef.current = newContent;
    if (!isRemote) {
      setSelection(null);
      selectionRef.current = null;
    }
    isDirtyRef.current = isRemote
      ? hadUnsavedChanges || Boolean(meta.hasPendingCollaborationSteps)
      : true;
    setSaveStatus(isDirtyRef.current ? 'unsaved' : 'saved');
    setRealtimeMessage(isRemote ? realtimeMessage : '');
    if (isDirtyRef.current) {
      writeOfflineDraft(id, {
        content: newContent,
        lineSpacing: lineSpacingRef.current,
        revision: revisionRef.current,
        updatedAt: Date.now(),
      });
    } else {
      clearOfflineDraft(id);
    }

    if (
      !isRemote
      && 
      typeof WebSocket !== 'undefined'
      && socketRef.current?.readyState === WebSocket.OPEN
    ) {
      socketRef.current.send(JSON.stringify({ type: 'typing', active: true }));
    }

    if (typeof meta.collaborationVersion === 'number') {
      collabVersionRef.current = meta.collaborationVersion;
    }
  }

  function handleSelectionUpdate(nextSelection) {
    if (!nextSelection?.text?.trim()) {
      return;
    }

    setSelection(nextSelection);
    selectionRef.current = nextSelection;
  }

  const handleSendableSteps = useCallback((payload) => {
    if (
      role === 'viewer'
      || typeof WebSocket === 'undefined'
      || socketRef.current?.readyState !== WebSocket.OPEN
    ) {
      return;
    }

    registerPendingStepBatch(payload);

    socketRef.current.send(
      JSON.stringify({
        type: 'step_update',
        batch_id: payload.batchId,
        version: payload.version,
        client_id: payload.clientId,
        steps: payload.steps,
        content: payload.content,
        line_spacing: payload.lineSpacing,
        affected_range: payload.affectedRange,
        candidate_content_snapshot: payload.candidateContentSnapshot,
        exact_text_snapshot: payload.exactTextSnapshot,
        prefix_context: payload.prefixContext,
        suffix_context: payload.suffixContext,
      })
    );
  }, [registerPendingStepBatch, role]);

  function handleLineSpacingChange(nextLineSpacing) {
    clearLastAiUndo();
    const normalizedLineSpacing = Math.min(3, Math.max(1, Number(nextLineSpacing) || 1.15));
    setLineSpacing(normalizedLineSpacing);
    lineSpacingRef.current = normalizedLineSpacing;
    isDirtyRef.current = true;
    setSaveStatus('unsaved');
    setRealtimeMessage('');
    setDoc((current) => {
      if (!current) {
        return current;
      }

      const nextDoc = {
        ...current,
        line_spacing: normalizedLineSpacing,
      };
      docRef.current = nextDoc;
      return nextDoc;
    });
    writeOfflineDraft(id, {
      content: contentRef.current,
      lineSpacing: normalizedLineSpacing,
      revision: revisionRef.current,
      updatedAt: Date.now(),
    });

    if (
      typeof WebSocket !== 'undefined'
      && socketRef.current?.readyState === WebSocket.OPEN
    ) {
      socketRef.current.send(
        JSON.stringify({
          type: 'line_spacing_update',
          line_spacing: normalizedLineSpacing,
        })
      );
    }
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
          line_spacing: updated.line_spacing,
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
    saveContent({ force: true, saveSource: 'manual' });
  }

  const handleRestoreVersion = useCallback(async (version) => {
    const saved = await saveContent({ force: true, saveSource: 'manual' });
    if (!saved) {
      throw new Error('Save the latest document changes before restoring a version.');
    }

    clearLastAiUndo();
    await apiJSON(`/documents/${id}/versions/${version.version_id}/restore`, {
      method: 'POST',
    });
    await refreshDocument();
    broadcastFullSnapshotUpdate('manual');
  }, [broadcastFullSnapshotUpdate, clearLastAiUndo, id, refreshDocument, saveContent]);

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
    broadcastFullSnapshotUpdate('manual');
    rememberLastAiUndo(undoSnapshot);
  }, [broadcastFullSnapshotUpdate, clearLastAiUndo, getAiUndoSnapshot, refreshDocument, rememberLastAiUndo]);

  const applyEditedDocumentSuggestion = useCallback(async ({ suggestionId, editedOutput, applyRange }) => {
    clearLastAiUndo();
    const undoSnapshot = getAiUndoSnapshot();

    await apiJSON(`/ai/suggestions/${suggestionId}/apply-edited`, {
      method: 'POST',
      body: JSON.stringify({
        edited_output: editedOutput,
        apply_to_range: applyRange,
      }),
    });

    await refreshDocument();
    broadcastFullSnapshotUpdate('manual');
    rememberLastAiUndo(undoSnapshot);
  }, [broadcastFullSnapshotUpdate, clearLastAiUndo, getAiUndoSnapshot, refreshDocument, rememberLastAiUndo]);

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

    const saved = await saveContent({ force: true, saveSource: 'manual' });

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
      broadcastFullSnapshotUpdate('manual');
      clearLastAiUndo();
    } catch (error) {
      clearLastAiUndo();
      throw error;
    }
  }, [broadcastFullSnapshotUpdate, clearLastAiUndo, id, refreshDocument]);

  async function handleBack() {
    const saved = await saveContent({ force: true, saveSource: 'manual' });
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
      nextLineSpacing: conflictState.line_spacing,
      nextRevision: conflictState.revision,
      nextLatestVersionId: conflictState.latest_version_id,
      nextCollabVersion: conflictState.collab_version,
      resetCollaboration: true,
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
        line_spacing: conflictState.line_spacing ?? current.line_spacing,
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
        line_spacing: lineSpacingRef.current,
        base_revision: conflictState.revision,
        save_source: 'autosave',
      })
    );
  }, [conflictState]);

  const resolveDocumentConflict = useCallback(async ({ candidateId = null, resolvedContent = '' }) => {
    if (!activeDocumentConflict) {
      return;
    }

    setConflictResolveLoading(true);
    try {
      await apiJSON(`/documents/${id}/conflicts/${activeDocumentConflict.conflict_id}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          candidate_id: candidateId,
          resolved_content: resolvedContent,
        }),
      });
      await refreshDocument();
      await loadDocumentConflicts();
      setConflictAiMerge({
        loading: false,
        error: '',
        interactionId: '',
        suggestion: null,
        partial: false,
      });
      setRealtimeMessage('Conflict resolved and synchronized to collaborators.');
    } finally {
      setConflictResolveLoading(false);
    }
  }, [activeDocumentConflict, id, loadDocumentConflicts, refreshDocument]);

  const handleUseConflictCandidate = useCallback(async (candidate) => {
    await resolveDocumentConflict({ candidateId: candidate.candidate_id });
  }, [resolveDocumentConflict]);

  const handleResolveConflictManual = useCallback(async () => {
    await resolveDocumentConflict({ resolvedContent: conflictResolutionDraft.trim() });
  }, [conflictResolutionDraft, resolveDocumentConflict]);

  const handleAskAiMerge = useCallback(async () => {
    if (!activeDocumentConflict) {
      return;
    }

    setConflictAiMerge({
      loading: true,
      error: '',
      interactionId: '',
      suggestion: null,
      partial: false,
    });

    try {
      const response = await apiFetch(`/documents/${id}/conflicts/${activeDocumentConflict.conflict_id}/ai-merge/stream`, {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
        },
      });

      let nextInteractionId = '';
      let streamedOutput = '';

      await consumeSseStream(response, async ({ event, data }) => {
        if (event === 'meta') {
          nextInteractionId = data.interaction_id;
          setConflictAiMerge({
            loading: true,
            error: '',
            interactionId: nextInteractionId,
            suggestion: null,
            partial: false,
          });
          return;
        }

        if (event === 'chunk') {
          streamedOutput = data.output || `${streamedOutput}${data.delta || ''}`;
          setConflictAiMerge({
            loading: true,
            error: '',
            interactionId: nextInteractionId,
            suggestion: {
              suggestion_id: '',
              generated_output: streamedOutput,
            },
            partial: true,
          });
          return;
        }

        if (event === 'complete') {
          setConflictAiMerge({
            loading: false,
            error: '',
            interactionId: data.interaction_id,
            suggestion: data.suggestion,
            partial: false,
          });
          return;
        }

        if (event === 'error' || event === 'cancelled') {
          setConflictAiMerge({
            loading: false,
            error: data.message || 'AI merge generation failed.',
            interactionId: nextInteractionId,
            suggestion: streamedOutput
              ? {
                  suggestion_id: '',
                  generated_output: streamedOutput,
                }
              : null,
            partial: Boolean(streamedOutput),
          });
        }
      });
    } catch (error) {
      setConflictAiMerge({
        loading: false,
        error: error.message || 'AI merge generation failed.',
        interactionId: '',
        suggestion: null,
        partial: false,
      });
    }
  }, [activeDocumentConflict, id]);

  const handleAcceptAiMerge = useCallback(async () => {
    const suggestionOutput = conflictAiMerge.suggestion?.generated_output?.trim();
    if (!suggestionOutput) {
      return;
    }
    await resolveDocumentConflict({ resolvedContent: suggestionOutput });
  }, [conflictAiMerge.suggestion, resolveDocumentConflict]);

  const handleRejectAiMerge = useCallback(async () => {
    const suggestionId = conflictAiMerge.suggestion?.suggestion_id;
    if (suggestionId) {
      try {
        await apiJSON(`/ai/suggestions/${suggestionId}/reject`, {
          method: 'POST',
        });
      } catch {
        // Ignore outcome-recording failures; the UI still clears the suggestion locally.
      }
    }

    setConflictAiMerge({
      loading: false,
      error: '',
      interactionId: '',
      suggestion: null,
      partial: false,
    });
  }, [conflictAiMerge.suggestion?.suggestion_id]);

  const handleUseAiMergeAsDraft = useCallback(() => {
    const suggestionOutput = conflictAiMerge.suggestion?.generated_output ?? '';
    setConflictResolutionDraft(suggestionOutput);
  }, [conflictAiMerge.suggestion]);

  useEffect(() => {
    if (!doc || !user) {
      return undefined;
    }

    let cancelled = false;
    let reconnectHandle = null;

    async function connectRealtime({ reconnecting = false } = {}) {
      if (!localStorage.getItem('access_token')) {
        setCollabEnabled(false);
        setCollabVersion(0);
        collabVersionRef.current = 0;
        return;
      }
      if (typeof WebSocket === 'undefined') {
        setCollabEnabled(false);
        setCollabVersion(0);
        collabVersionRef.current = 0;
        setRealtimeStatus('unsupported');
        setRealtimeMessage('This browser does not support realtime collaboration.');
        return;
      }

      setPresence([]);
      setRealtimeStatus(reconnecting ? 'reconnecting' : 'connecting');
      if (!reconnecting) {
        setRealtimeMessage('');
      }

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

        const bootstrapCollabVersion = Number(bootstrap.collab_version) || 0;
        const bootstrapLineSpacing = Number(bootstrap.line_spacing_snapshot) || lineSpacingRef.current;
        setCollabEnabled(true);
        setCollabVersion(bootstrapCollabVersion);
        collabVersionRef.current = bootstrapCollabVersion;
        void loadDocumentConflicts();

        if (!isDirtyRef.current) {
          syncRealtimeDocument({
            nextContent: bootstrap.content_snapshot ?? contentRef.current,
            nextLineSpacing: bootstrapLineSpacing,
            nextRevision: revisionRef.current,
            nextLatestVersionId: docRef.current?.latest_version_id ?? null,
            nextCollabVersion: bootstrapCollabVersion,
            resetCollaboration: reconnecting,
          });
        }

        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
          setCollabEnabled(false);
          setCollabVersion(0);
          collabVersionRef.current = 0;
          setRealtimeStatus('offline');
          setRealtimeMessage('Your session expired. Refresh the page to sign in again.');
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
            const nextCollabVersion = Number(payload.collab_version) || 0;
            setCollabEnabled(true);
            if (!isDirtyRef.current) {
              syncRealtimeDocument({
                nextContent: payload.content,
                nextLineSpacing: payload.line_spacing,
                nextRevision: payload.revision,
                nextLatestVersionId: payload.latest_version_id,
                nextCollabVersion,
              });
            } else {
              setCollabVersion(nextCollabVersion);
              collabVersionRef.current = nextCollabVersion;
            }
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
            const nextCollabVersion = Number(payload.collab_version) || 0;

            if (isOwnUpdate || !isDirtyRef.current) {
              syncRealtimeDocument({
                nextContent: payload.content,
                nextLineSpacing: payload.line_spacing,
                nextRevision: payload.revision,
                nextLatestVersionId: payload.latest_version_id,
                updatedAt: payload.saved_at,
                nextCollabVersion,
                resetCollaboration: Boolean(payload.collab_reset),
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
              line_spacing: payload.line_spacing,
              revision: payload.revision,
              latest_version_id: payload.latest_version_id,
              collab_version: nextCollabVersion,
              message: `${payload.actor_display_name || 'Another collaborator'} updated this document while you were still editing.`,
            });
            return;
          }

          if (payload.type === 'line_spacing_updated') {
            const nextLineSpacing = Number(payload.line_spacing) || lineSpacingRef.current;
            setLineSpacing(nextLineSpacing);
            lineSpacingRef.current = nextLineSpacing;
            setDoc((current) => {
              if (!current) {
                return current;
              }

              const nextDoc = {
                ...current,
                line_spacing: nextLineSpacing,
              };
              docRef.current = nextDoc;
              return nextDoc;
            });
            if (typeof payload.collab_version === 'number') {
              setCollabVersion(payload.collab_version);
              collabVersionRef.current = payload.collab_version;
            }
            if (payload.actor_user_id !== userRef.current?.user_id && payload.actor_display_name) {
              setRealtimeMessage(`${payload.actor_display_name} updated document formatting.`);
            }
            return;
          }

          if (payload.type === 'steps_applied') {
            const editor = editorRef.current;
            const nextCollabVersion = Number(payload.collab_version) || collabVersionRef.current;
            const remoteBatch = payload.batch || null;
            const currentUserId = resolveUserId(userRef.current);
            const isOwnStepBatch = payload.actor_user_id === currentUserId;

            if (isOwnStepBatch && remoteBatch?.batch_id) {
              clearPendingStepBatch(remoteBatch.batch_id);
            }

            if (!isOwnStepBatch && remoteBatch?.affected_range) {
              const overlappingLocalBatches = pendingStepBatchesRef.current.filter((localBatch) => (
                Math.abs((localBatch.version ?? 0) - (remoteBatch.version ?? 0)) <= 1
                && rangesOverlap(localBatch.affectedRange, remoteBatch.affected_range)
              ));
              overlappingLocalBatches.forEach((localBatch) => {
                void reportOverlapConflict(localBatch, remoteBatch);
              });
            }

            const applied = editor?.applyRemoteSteps?.({
              steps: payload.steps || [],
              clientIds: payload.client_ids || [],
            });

            if (!applied?.applied && !isDirtyRef.current) {
              syncRealtimeDocument({
                nextContent: payload.content,
                nextLineSpacing: payload.line_spacing,
                nextRevision: revisionRef.current,
                nextLatestVersionId: docRef.current?.latest_version_id ?? null,
                nextCollabVersion,
                resetCollaboration: true,
              });
            } else {
              setCollabVersion(nextCollabVersion);
              collabVersionRef.current = nextCollabVersion;
            }

            if (
              payload.actor_user_id !== userRef.current?.user_id
              && !isDirtyRef.current
              && payload.actor_display_name
            ) {
              setRealtimeMessage(`${payload.actor_display_name} updated the document.`);
            }
            return;
          }

          if (payload.type === 'steps_resync') {
            const nextCollabVersion = Number(payload.collab_version) || 0;
            if (payload.full_reset) {
              pendingStepBatchesRef.current = [];
            }
            if (payload.full_reset) {
              syncRealtimeDocument({
                nextContent: payload.content,
                nextLineSpacing: payload.line_spacing,
                nextRevision: payload.revision ?? revisionRef.current,
                nextLatestVersionId: payload.latest_version_id ?? docRef.current?.latest_version_id,
                nextCollabVersion,
                resetCollaboration: true,
              });
            } else {
              const applied = editorRef.current?.applyRemoteSteps?.({
                steps: payload.steps || [],
                clientIds: payload.client_ids || [],
              });
              if (!applied?.applied) {
                syncRealtimeDocument({
                  nextContent: payload.content,
                  nextLineSpacing: payload.line_spacing,
                  nextRevision: payload.revision ?? revisionRef.current,
                  nextLatestVersionId: payload.latest_version_id ?? docRef.current?.latest_version_id,
                  nextCollabVersion,
                  resetCollaboration: true,
                });
              } else {
                setCollabVersion(nextCollabVersion);
                collabVersionRef.current = nextCollabVersion;
              }
            }
            void loadDocumentConflicts();
            setRealtimeMessage('Realtime re-synced with the latest collaboration state.');
            return;
          }

          if (payload.type === 'conflict_created') {
            if (payload.conflict) {
              setDocumentConflicts((current) => upsertConflict(current, payload.conflict));
              setActiveConflictId((current) => current ?? payload.conflict.conflict_id);
              setRealtimeMessage('A collaboration conflict needs review.');
            }
            return;
          }

          if (payload.type === 'conflict_resolved') {
            setDocumentConflicts((current) => current.filter(
              (conflict) => conflict.conflict_id !== payload.conflict_id
            ));
            setActiveConflictId((current) => (
              current === payload.conflict_id ? null : current
            ));
            setRealtimeMessage('A collaboration conflict was resolved.');
            void loadDocumentConflicts();
            return;
          }

          if (payload.type === 'conflict_detected') {
            setConflictState({
              content: payload.content,
              line_spacing: payload.line_spacing,
              revision: payload.revision,
              latest_version_id: payload.latest_version_id,
              collab_version: payload.collab_version ?? collabVersionRef.current,
              message: payload.message,
            });
            return;
          }

          if (payload.type === 'error') {
            setRealtimeMessage(payload.message || 'Realtime collaboration hit an error.');
          }
        };

        nextSocket.onclose = (event = { code: 1006, reason: '' }) => {
          if (cancelled) {
            return;
          }
          socketRef.current = null;
          setPresence([]);

          if (event.code === 4401 || event.code === 4403) {
            setRealtimeStatus('offline');
            setRealtimeMessage(
              event.reason || 'Realtime authentication failed. Refresh the page to reconnect.'
            );
            return;
          }

          setRealtimeStatus('reconnecting');
          setRealtimeMessage(
            event.reason
              ? `Realtime disconnected (${event.code}: ${event.reason}). Trying to reconnect while local saves continue.`
              : 'Realtime disconnected. Trying to reconnect while local saves continue.'
          );
          reconnectHandle = window.setTimeout(() => {
            void connectRealtime({ reconnecting: true });
          }, 1_500);
          reconnectTimerRef.current = reconnectHandle;
        };

        nextSocket.onerror = () => {
          if (!cancelled) {
            setPresence([]);
            setRealtimeMessage('Realtime hit a network error.');
          }
        };
      } catch (nextError) {
        if (!cancelled) {
          setPresence([]);
          setCollabEnabled(false);
          if (collabVersionRef.current === 0) {
            setCollabVersion(0);
          }
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
  }, [clearPendingStepBatch, doc?.document_id, id, loadDocumentConflicts, reportOverlapConflict, syncRealtimeDocument, user?.id, user?.user_id]);

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

  if (collabVersion === null) {
    return <div className="editor-loading">Preparing collaboration…</div>;
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
            onSendableSteps={handleSendableSteps}
            onSelectionUpdate={handleSelectionUpdate}
            lineSpacing={lineSpacing}
            onLineSpacingChange={handleLineSpacingChange}
            collaborationEnabled={collabEnabled}
            collaborationVersion={collabVersion}
            collaborationResetKey={collabResetKey}
            conflictHighlights={documentConflicts
              .filter((conflict) => conflict.anchor_range)
              .map((conflict) => ({
                conflictId: conflict.conflict_id,
                range: conflict.anchor_range,
              }))}
            readOnly={isReadOnly}
            placeholder="Start writing…"
          />

          {activeDocumentConflict ? (
            <ConflictResolutionTray
              conflict={activeDocumentConflict}
              role={role}
              resolutionDraft={conflictResolutionDraft}
              onResolutionDraftChange={setConflictResolutionDraft}
              onUseCandidate={handleUseConflictCandidate}
              onResolveManual={handleResolveConflictManual}
              onAskAiMerge={handleAskAiMerge}
              onAcceptAiMerge={handleAcceptAiMerge}
              onRejectAiMerge={handleRejectAiMerge}
              onUseAiMergeAsDraft={handleUseAiMergeAsDraft}
              aiMergeState={conflictAiMerge}
              resolving={conflictResolveLoading}
            />
          ) : null}
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
          applyEditedDocumentSuggestion={applyEditedDocumentSuggestion}
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
