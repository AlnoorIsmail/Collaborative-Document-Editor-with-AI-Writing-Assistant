import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiJSON, apiFetch } from '../api';
import Navbar from '../components/Navbar';
import TiptapEditor from '../components/TiptapEditor';
import ShareModal from '../components/ShareModal';

const AUTO_SAVE_DELAY = 1_500;

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
  const [showShare, setShowShare] = useState(false);
  const [error, setError] = useState('');

  const editorRef = useRef(null);
  const contentRef = useRef('');
  const titleRef = useRef('');
  const revisionRef = useRef(0);
  const isDirtyRef = useRef(false);
  const savePromiseRef = useRef(null);

  useEffect(() => {
    Promise.all([
      apiJSON(`/documents/${id}`),
      apiJSON('/auth/me'),
    ])
      .then(([docData, userData]) => {
        setDoc(docData);
        setUser(userData);
        setTitle(docData.title || '');

        const initialContent = docData.current_content || docData.content || '';
        setContent(initialContent);
        contentRef.current = initialContent;
        titleRef.current = docData.title || '';
        setRevision(docData.revision ?? 0);
        revisionRef.current = docData.revision ?? 0;
        isDirtyRef.current = false;
        setSaveStatus('saved');
        setError('');

        const ownerId = docData.owner_id || docData.owner_user_id;
        const userId = userData.id || userData.user_id;

        if (ownerId && userId && ownerId === userId) {
          setRole('owner');
        } else {
          const collab = (docData.collaborators || []).find(
            c => c.user_id === userId || c.email === userData.email
          );
          setRole(collab?.role || 'viewer');
        }
      })
      .catch(err => {
        if (err.status === 404) navigate('/');
        else setError(err.message);
      });
  }, [id, navigate]);

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
        current
          ? {
              ...current,
              current_content: contentToSave,
              revision: saved.revision,
              latest_version_id: saved.latest_version_id,
            }
          : current
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

  useEffect(() => {
    if (role === 'viewer' || !doc || saveStatus !== 'unsaved') {
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
    setContent(newContent);
    contentRef.current = newContent;
    isDirtyRef.current = true;
    setSaveStatus('unsaved');
  }

  async function handleTitleChange(newTitle) {
    titleRef.current = newTitle;
    setTitle(newTitle);
    try {
      await apiFetch(`/documents/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: newTitle }),
      });
    } catch {
      // non-critical, ignore
    }
  }

  function handleSaveNow() {
    saveContent({ force: true });
  }

  async function handleBack() {
    const saved = await saveContent({ force: true });
    if (saved) {
      navigate('/');
    }
  }

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
        onShare={() => setShowShare(true)}
        isOwner={role === 'owner'}
        isReadOnly={isReadOnly}
        onBack={handleBack}
        user={user}
      />

      {isReadOnly && (
        <div className="readonly-banner">
          You have view-only access to this document.
        </div>
      )}

      <TiptapEditor
        ref={editorRef}
        content={content}
        onChange={handleContentChange}
        readOnly={isReadOnly}
        placeholder="Start writing…"
      />

      {showShare && (
        <ShareModal
          docId={id}
          collaborators={doc.collaborators || []}
          onClose={() => setShowShare(false)}
          onUpdate={updated => setDoc(d => ({ ...d, collaborators: updated }))}
        />
      )}
    </div>
  );
}
