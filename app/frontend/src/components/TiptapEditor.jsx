import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { Extension } from '@tiptap/core';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import {
  collab as prosemirrorCollab,
  getVersion,
  receiveTransaction,
  sendableSteps,
} from '@tiptap/pm/collab';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import { Step } from '@tiptap/pm/transform';

const LINE_SPACING_OPTIONS = [
  { value: 1, label: 'Single' },
  { value: 1.15, label: '1.15' },
  { value: 1.5, label: '1.5' },
  { value: 2, label: 'Double' },
];

const CONFLICT_HIGHLIGHTS_KEY = new PluginKey('conflict-highlights');
const REMOTE_AWARENESS_KEY = new PluginKey('remote-awareness');
const ANCHOR_CONTEXT_WINDOW = 24;

const EditorKeymap = Extension.create({
  name: 'editorKeymap',
  addKeyboardShortcuts() {
    return {
      'Shift-Enter': () => this.editor.commands.setHardBreak(),
    };
  },
});

function clampLineSpacing(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 1.15;
  }
  return Math.min(3, Math.max(1, numeric));
}

function makeBatchId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function sliceDocText(doc, start, end) {
  const safeStart = Math.max(0, Math.min(start, doc.content.size));
  const safeEnd = Math.max(safeStart, Math.min(end, doc.content.size));
  return doc.textBetween(safeStart, safeEnd, ' ');
}

function buildStepBatchMetadata(transaction) {
  if (!transaction.docChanged || transaction.steps.length === 0) {
    return null;
  }

  let oldStart = Number.POSITIVE_INFINITY;
  let oldEnd = 0;
  let newStart = Number.POSITIVE_INFINITY;
  let newEnd = 0;

  transaction.steps.forEach((step) => {
    step.getMap().forEach((rangeOldStart, rangeOldEnd, rangeNewStart, rangeNewEnd) => {
      oldStart = Math.min(oldStart, rangeOldStart);
      oldEnd = Math.max(oldEnd, rangeOldEnd);
      newStart = Math.min(newStart, rangeNewStart);
      newEnd = Math.max(newEnd, rangeNewEnd);
    });
  });

  const fallbackPosition = transaction.selection?.from ?? 0;
  const normalizedOldStart = Number.isFinite(oldStart) ? oldStart : fallbackPosition;
  const normalizedOldEnd = Number.isFinite(oldStart) ? Math.max(oldEnd, normalizedOldStart) : fallbackPosition;
  const normalizedNewStart = Number.isFinite(newStart) ? newStart : fallbackPosition;
  const normalizedNewEnd = Number.isFinite(newStart) ? Math.max(newEnd, normalizedNewStart) : fallbackPosition;

  const docBefore = transaction.docs?.[0] ?? transaction.before;
  const docAfter = transaction.doc;

  const exactTextSnapshot = docBefore
    ? sliceDocText(docBefore, normalizedOldStart, normalizedOldEnd)
    : '';
  const prefixContext = docBefore
    ? sliceDocText(
        docBefore,
        Math.max(0, normalizedOldStart - ANCHOR_CONTEXT_WINDOW),
        normalizedOldStart
      )
    : '';
  const suffixContext = docBefore
    ? sliceDocText(
        docBefore,
        normalizedOldEnd,
        normalizedOldEnd + ANCHOR_CONTEXT_WINDOW
      )
    : '';

  return {
    batchId: makeBatchId(),
    affectedRange: {
      start: normalizedOldStart,
      end: normalizedOldEnd,
    },
    candidateContentSnapshot: sliceDocText(docAfter, normalizedNewStart, normalizedNewEnd),
    exactTextSnapshot,
    prefixContext,
    suffixContext,
  };
}

function createConflictHighlightPlugin() {
  return new Plugin({
    key: CONFLICT_HIGHLIGHTS_KEY,
    state: {
      init() {
        return DecorationSet.empty;
      },
      apply(transaction, decorationSet) {
        const nextHighlights = transaction.getMeta(CONFLICT_HIGHLIGHTS_KEY);
        if (!nextHighlights) {
          return decorationSet.map(transaction.mapping, transaction.doc);
        }

        const decorations = [];
        for (const highlight of nextHighlights) {
          const start = Math.max(0, Math.min(highlight.start, transaction.doc.content.size));
          const end = Math.max(start, Math.min(highlight.end, transaction.doc.content.size));
          decorations.push(
            Decoration.inline(start, Math.max(end, start + 1), {
              class: 'editor-conflict-highlight',
              'data-conflict-id': String(highlight.conflictId),
            })
          );
          decorations.push(
            Decoration.widget(start, () => {
              const marker = document.createElement('span');
              marker.className = 'editor-conflict-marker';
              marker.dataset.conflictId = String(highlight.conflictId);
              marker.title = 'Unresolved collaboration conflict';
              return marker;
            })
          );
        }
        return DecorationSet.create(transaction.doc, decorations);
      },
    },
    props: {
      decorations(state) {
        return this.getState(state);
      },
    },
  });
}

function createRemoteAwarenessPlugin() {
  return new Plugin({
    key: REMOTE_AWARENESS_KEY,
    state: {
      init() {
        return DecorationSet.empty;
      },
      apply(transaction, decorationSet) {
        const nextAwareness = transaction.getMeta(REMOTE_AWARENESS_KEY);
        if (!nextAwareness) {
          return decorationSet.map(transaction.mapping, transaction.doc);
        }

        const decorations = [];
        for (const awareness of nextAwareness) {
          const safeFrom = Math.max(0, Math.min(awareness.from, transaction.doc.content.size));
          const safeTo = Math.max(safeFrom, Math.min(awareness.to, transaction.doc.content.size));
          const color = awareness.color || '#4f46e5';
          const label = awareness.label || 'Collaborator';

          if (safeFrom === safeTo) {
            decorations.push(
              Decoration.widget(safeFrom, () => {
                const caret = document.createElement('span');
                caret.className = 'editor-remote-caret';
                caret.style.setProperty('--remote-awareness-color', color);
                caret.dataset.sessionId = String(awareness.sessionId || '');

                const labelBadge = document.createElement('span');
                labelBadge.className = 'editor-remote-caret-label';
                labelBadge.textContent = label;

                const line = document.createElement('span');
                line.className = 'editor-remote-caret-line';

                caret.append(labelBadge, line);
                return caret;
              }, { side: 1 })
            );
            continue;
          }

          decorations.push(
            Decoration.inline(safeFrom, safeTo, {
              class: 'editor-remote-selection',
              style: `--remote-awareness-color: ${color};`,
              'data-session-id': String(awareness.sessionId || ''),
            })
          );
        }

        return DecorationSet.create(transaction.doc, decorations);
      },
    },
    props: {
      decorations(state) {
        return this.getState(state);
      },
    },
  });
}

function createCollaborationExtension({ enabled, version }) {
  return Extension.create({
    name: 'collaborationBridge',
    addProseMirrorPlugins() {
      return enabled ? [prosemirrorCollab({ version })] : [];
    },
  });
}

function createConflictHighlightExtension() {
  return Extension.create({
    name: 'conflictHighlightBridge',
    addProseMirrorPlugins() {
      return [createConflictHighlightPlugin()];
    },
  });
}

function createRemoteAwarenessExtension() {
  return Extension.create({
    name: 'remoteAwarenessBridge',
    addProseMirrorPlugins() {
      return [createRemoteAwarenessPlugin()];
    },
  });
}

// Toolbar button component
function ToolbarButton({ onClick, active, disabled, title, children }) {
  return (
    <button
      type="button"
      className={`toolbar-btn ${active ? 'toolbar-btn-active' : ''}`}
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
    >
      {children}
    </button>
  );
}

function Toolbar({ editor, lineSpacing, onLineSpacingChange }) {
  if (!editor) return null;

  return (
    <div className="editor-toolbar">
      <div className="toolbar-group">
        {[1, 2, 3].map(level => (
          <ToolbarButton
            key={level}
            onClick={() => editor.chain().focus().toggleHeading({ level }).run()}
            active={editor.isActive('heading', { level })}
            disabled={!editor.can().toggleHeading({ level })}
            title={`Heading ${level}`}
          >
            H{level}
          </ToolbarButton>
        ))}
      </div>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          active={editor.isActive('bold')}
          disabled={!editor.can().toggleBold()}
          title="Bold"
        >
          <strong>B</strong>
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          active={editor.isActive('italic')}
          disabled={!editor.can().toggleItalic()}
          title="Italic"
        >
          <em>I</em>
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleCode().run()}
          active={editor.isActive('code')}
          disabled={!editor.can().toggleCode()}
          title="Inline code"
        >
          {'<>'}
        </ToolbarButton>
      </div>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          active={editor.isActive('bulletList')}
          title="Bullet list"
        >
          &#8226;&#8212;
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          active={editor.isActive('orderedList')}
          title="Ordered list"
        >
          1&#8212;
        </ToolbarButton>
      </div>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          active={editor.isActive('codeBlock')}
          title="Code block"
        >
          &#128187;
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          active={editor.isActive('blockquote')}
          title="Blockquote"
        >
          &#10077;
        </ToolbarButton>
      </div>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        <label className="toolbar-line-spacing" htmlFor="line-spacing-select">
          <span className="toolbar-line-spacing-label">Line spacing</span>
          <select
            id="line-spacing-select"
            className="toolbar-line-spacing-select"
            value={lineSpacing}
            onChange={(event) => onLineSpacingChange?.(Number(event.target.value))}
            aria-label="Line spacing"
          >
            {LINE_SPACING_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="toolbar-divider" />

      <div className="toolbar-group">
        <ToolbarButton
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          title="Undo"
        >
          &#8617;
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          title="Redo"
        >
          &#8618;
        </ToolbarButton>
      </div>
    </div>
  );
}

/**
 * TiptapEditor
 *
 * Props:
 *   content      - HTML string initial content
 *   onChange     - called with new HTML on every change
 *   readOnly     - boolean, disables editing
 *   placeholder  - placeholder text
 *   onSelectionUpdate - ({ text, from, to }) => void, called when selection changes
 *   lineSpacing  - unitless line spacing value persisted with the document
 *   onLineSpacingChange - (nextLineSpacing) => void
 *   collaborationEnabled - enable ProseMirror step-based collaboration
 *   collaborationVersion - initial collaboration version for the current collaboration snapshot
 *   collaborationResetKey - forces a collab editor re-initialization after a full snapshot reset
 *   onSendableSteps - called with locally pending ProseMirror steps that should be sent
 *   conflictHighlights - unresolved conflicts with re-anchored ranges for inline markers
 *   remoteAwareness - remote cursor and selection decorations for active collaborators
 *
 * Ref methods:
 *   getSelectionData() - returns the current selected text and range
 *   replaceRange({ from, to, text }) - replaces a specific editor range
 *   setSelection({ from, to }) - sets the current editor selection
 *   insertParagraphBreak() - inserts a new paragraph at the current selection
 *   insertHardBreak() - inserts a soft line break at the current selection
 *   applyRemoteSteps({ steps, clientIds }) - applies remote ProseMirror steps
 *   getCollaborationVersion() - returns the current collaboration version
 */
const TiptapEditor = forwardRef(function TiptapEditor(
  {
    content,
    onChange,
    readOnly = false,
    placeholder = 'Start writing…',
    onSelectionUpdate,
    lineSpacing = 1.15,
    onLineSpacingChange,
    collaborationEnabled = false,
    collaborationVersion = 0,
    collaborationResetKey = 0,
    onSendableSteps,
    conflictHighlights = [],
    remoteAwareness = [],
  },
  ref
) {
  const normalizedLineSpacing = clampLineSpacing(lineSpacing);
  const applyingRemoteRef = useRef(false);
  const lastSentSignatureRef = useRef('');
  const lineSpacingRef = useRef(normalizedLineSpacing);
  const changeHandlerRef = useRef(onChange);
  const sendableStepsHandlerRef = useRef(onSendableSteps);
  const selectionHandlerRef = useRef(onSelectionUpdate);
  const conflictHighlightsRef = useRef(conflictHighlights);
  const remoteAwarenessRef = useRef(remoteAwareness);
  const highlightSignatureRef = useRef('');
  const awarenessSignatureRef = useRef('');

  useEffect(() => {
    lineSpacingRef.current = normalizedLineSpacing;
  }, [normalizedLineSpacing]);

  useEffect(() => {
    changeHandlerRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    sendableStepsHandlerRef.current = onSendableSteps;
  }, [onSendableSteps]);

  useEffect(() => {
    selectionHandlerRef.current = onSelectionUpdate;
  }, [onSelectionUpdate]);

  useEffect(() => {
    conflictHighlightsRef.current = conflictHighlights;
  }, [conflictHighlights]);

  useEffect(() => {
    remoteAwarenessRef.current = remoteAwareness;
  }, [remoteAwareness]);

  const editor = useEditor({
    extensions: [
      createCollaborationExtension({
        enabled: collaborationEnabled,
        version: collaborationVersion,
      }),
      createConflictHighlightExtension(),
      createRemoteAwarenessExtension(),
      StarterKit,
      Placeholder.configure({ placeholder }),
      EditorKeymap,
    ],
    content,
    editable: !readOnly,
    onTransaction({ editor, transaction }) {
      const isRemote = applyingRemoteRef.current;
      const pending = collaborationEnabled ? sendableSteps(editor.state) : null;
      const batchMetadata = !isRemote ? buildStepBatchMetadata(transaction) : null;
      if (transaction.docChanged || isRemote) {
        changeHandlerRef.current?.(editor.getHTML(), {
          isRemote,
          hasPendingCollaborationSteps: Boolean(pending?.steps?.length),
          collaborationVersion: collaborationEnabled ? getVersion(editor.state) : collaborationVersion,
        });
      }

      if (collaborationEnabled) {
        if (!pending || pending.steps.length === 0) {
          lastSentSignatureRef.current = '';
        } else {
          const signature = `${pending.version}:${pending.steps.length}:${editor.getHTML().length}`;
          if (signature !== lastSentSignatureRef.current) {
            lastSentSignatureRef.current = signature;
            sendableStepsHandlerRef.current?.({
              batchId: batchMetadata?.batchId ?? makeBatchId(),
              version: pending.version,
              clientId: String(pending.clientID),
              steps: pending.steps.map((step) => step.toJSON()),
              content: editor.getHTML(),
              lineSpacing: lineSpacingRef.current,
              affectedRange: batchMetadata?.affectedRange ?? {
                start: editor.state.selection.from,
                end: editor.state.selection.to,
              },
              candidateContentSnapshot: batchMetadata?.candidateContentSnapshot ?? '',
              exactTextSnapshot: batchMetadata?.exactTextSnapshot ?? '',
              prefixContext: batchMetadata?.prefixContext ?? '',
              suffixContext: batchMetadata?.suffixContext ?? '',
            });
          }
        }
      }

      if (isRemote) {
        applyingRemoteRef.current = false;
      }
    },
    onSelectionUpdate({ editor }) {
      if (selectionHandlerRef.current) {
        const {
          from,
          to,
          anchor,
          head,
        } = editor.state.selection;
        const text = from === to ? '' : editor.state.doc.textBetween(from, to, ' ');
        selectionHandlerRef.current({
          text,
          from,
          to,
          direction: anchor <= head ? 'forward' : 'backward',
        });
      }
    },
  }, [collaborationEnabled, collaborationResetKey]);

  // Expose imperative API via ref
  useImperativeHandle(ref, () => ({
    getSelectionData() {
      if (!editor) {
        return { text: '', from: 0, to: 0 };
      }
      const { from, to } = editor.state.selection;
      const text = from === to ? '' : editor.state.doc.textBetween(from, to, ' ');
      return { text, from, to };
    },
    getHTML() {
      return editor?.getHTML() ?? '';
    },
    replaceRange({ from, to, text }) {
      if (!editor) {
        return { applied: false, html: '' };
      }

      const didApply = editor
        .chain()
        .focus()
        .insertContentAt({ from, to }, text)
        .run();

      return {
        applied: didApply,
        html: editor.getHTML(),
      };
    },
    focus() {
      editor?.commands.focus();
    },
    setSelection({ from, to = from }) {
      if (!editor) {
        return false;
      }

      return editor.commands.setTextSelection({ from, to });
    },
    insertParagraphBreak() {
      if (!editor) {
        return false;
      }

      return editor.chain().focus().splitBlock().run();
    },
    insertHardBreak() {
      if (!editor) {
        return false;
      }

      return editor.chain().focus().setHardBreak().run();
    },
    applyRemoteSteps({ steps, clientIds }) {
      if (!editor || !collaborationEnabled) {
        return {
          applied: false,
          html: editor?.getHTML() ?? '',
          version: collaborationEnabled ? 0 : collaborationVersion,
        };
      }

      const parsedSteps = steps.map((step) => Step.fromJSON(editor.schema, step));
      applyingRemoteRef.current = true;
      const transaction = receiveTransaction(editor.state, parsedSteps, clientIds);
      editor.view.dispatch(transaction);
      return {
        applied: true,
        html: editor.getHTML(),
        version: getVersion(editor.state),
      };
    },
    getCollaborationVersion() {
      if (!editor || !collaborationEnabled) {
        return collaborationVersion;
      }
      return getVersion(editor.state);
    },
    setConflictHighlights(nextHighlights) {
      if (!editor) {
        return false;
      }
      editor.view.dispatch(
        editor.state.tr.setMeta(
          CONFLICT_HIGHLIGHTS_KEY,
          Array.isArray(nextHighlights) ? nextHighlights : []
        )
      );
      return true;
    },
  }), [editor, collaborationEnabled, collaborationVersion]);

  useEffect(() => {
    lastSentSignatureRef.current = '';
  }, [collaborationEnabled, collaborationResetKey]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!readOnly);
  }, [editor, readOnly]);

  useEffect(() => {
    if (!editor) return;

    const currentContent = editor.getHTML();
    if (content === currentContent) {
      return;
    }

    editor.commands.setContent(content || '', false);
  }, [content, editor]);

  useEffect(() => {
    if (!editor) {
      return;
    }

    const highlights = (conflictHighlightsRef.current || [])
      .filter((conflict) => conflict?.range)
      .map((conflict) => ({
        conflictId: conflict.conflictId,
        start: conflict.range.start,
        end: conflict.range.end,
      }));
    const signature = JSON.stringify(highlights);
    if (signature === highlightSignatureRef.current) {
      return;
    }
    highlightSignatureRef.current = signature;
    editor.view.dispatch(editor.state.tr.setMeta(CONFLICT_HIGHLIGHTS_KEY, highlights));
  }, [editor, conflictHighlights]);

  useEffect(() => {
    if (!editor) {
      return;
    }

    const awareness = (remoteAwarenessRef.current || [])
      .filter((entry) => Number.isFinite(entry?.from) && Number.isFinite(entry?.to))
      .map((entry) => ({
        sessionId: entry.sessionId,
        from: entry.from,
        to: entry.to,
        color: entry.color,
        label: entry.label,
      }));
    const signature = JSON.stringify(awareness);
    if (signature === awarenessSignatureRef.current) {
      return;
    }
    awarenessSignatureRef.current = signature;
    editor.view.dispatch(editor.state.tr.setMeta(REMOTE_AWARENESS_KEY, awareness));
  }, [editor, remoteAwareness]);

  return (
    <div
      className={`editor-wrapper ${readOnly ? 'editor-readonly' : ''}`}
      style={{
        '--editor-line-spacing': normalizedLineSpacing,
        '--editor-block-gap': `${Math.max(0.5, normalizedLineSpacing * 0.5)}rem`,
      }}
    >
      {!readOnly && (
        <Toolbar
          editor={editor}
          lineSpacing={normalizedLineSpacing}
          onLineSpacingChange={onLineSpacingChange}
        />
      )}
      <EditorContent editor={editor} className="editor-content" />
    </div>
  );
});

export default TiptapEditor;
