import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiJSON, apiFetch } from '../api';
import Navbar from '../components/Navbar';
import TiptapEditor from '../components/TiptapEditor';
import ShareModal from '../components/ShareModal';

const AUTO_SAVE_INTERVAL = 30_000; // 30 seconds

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [doc, setDoc] = useState(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState('owner'); // 'owner' | 'editor' | 'viewer'
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saveStatus, setSaveStatus] = useState('saved'); // 'saved' | 'saving' | 'unsaved'
  const [showShare, setShowShare] = useState(false);
  const [error, setError] = useState('');

  const editorRef = useRef(null);
  const contentRef = useRef('');
  const titleRef = useRef('');
  const isDirtyRef = useRef(false);

  // Load document and current user
  useEffect(() => {
    Promise.all([
      apiJSON(`/documents/${id}`),
      apiJSON('/auth/me'),
    ])
      .then(([docData, userData]) => {
        setDoc(docData);
        setUser(userData);
        setTitle(docData.title || '');
        setContent(docData.content || '');
        contentRef.current = docData.content || '';
        titleRef.current = docData.title || '';

        // Determine role
        if (docData.owner_id && userData.id && docData.owner_id === userData.id) {
          setRole('owner');
        } else {
          const collab = (docData.collaborators || []).find(
            c => c.user_id === userData.id || c.email === userData.email
          );
          setRole(collab?.role || 'viewer');
        }
      })
      .catch(err => {
        if (err.status === 404) navigate('/');
        else setError(err.message);
      });
  }, [id, navigate]);

  // Auto-save every 30 seconds
  const saveContent = useCallback(async () => {
    if (!isDirtyRef.current) return;
    setSaveStatus('saving');
    try {
      await apiFetch(`/documents/${id}/content`, {
        method: 'PATCH',
        body: JSON.stringify({ content: contentRef.current }),
      });
      isDirtyRef.current = false;
      setSaveStatus('saved');
    } catch {
      setSaveStatus('unsaved');
    }
  }, [id]);

  useEffect(() => {
    const timer = setInterval(saveContent, AUTO_SAVE_INTERVAL);
    return () => clearInterval(timer);
  }, [saveContent]);

  // Save on page unload if dirty
  useEffect(() => {
    function handleUnload() {
      if (isDirtyRef.current) {
        navigator.sendBeacon(
          `/v1/documents/${id}/content`,
          JSON.stringify({ content: contentRef.current })
        );
      }
    }
    window.addEventListener('beforeunload', handleUnload);
    return () => window.removeEventListener('beforeunload', handleUnload);
  }, [id]);

  function handleContentChange(newContent) {
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
    saveContent();
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
        onBack={() => navigate('/')}
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
