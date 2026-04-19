import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
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
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state';
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

function clampSelectionPosition(editor, from, to = from) {
  return normalizeSelectionRange(editor?.state?.doc, from, to);
}

function normalizeSelectionRange(doc, from, to = from) {
  const docSize = doc?.content?.size ?? 0;
  if (!doc || docSize <= 0) {
    return { from: 0, to: 0 };
  }

  const numericFrom = Number(from);
  const numericTo = Number(to);
  const safeFrom = Math.max(
    0,
    Math.min(Number.isFinite(numericFrom) ? numericFrom : 0, docSize)
  );
  const safeTo = Math.max(
    0,
    Math.min(Number.isFinite(numericTo) ? numericTo : safeFrom, docSize)
  );

  try {
    if (safeFrom === safeTo) {
      const cursor = TextSelection.near(doc.resolve(safeFrom), 1);
      return { from: cursor.from, to: cursor.to };
    }

    const selection = TextSelection.between(
      doc.resolve(Math.min(safeFrom, safeTo)),
      doc.resolve(Math.max(safeFrom, safeTo))
    );
    return {
      from: Math.min(selection.from, selection.to),
      to: Math.max(selection.from, selection.to),
    };
  } catch {
    const fallbackFrom = Math.max(1, Math.min(safeFrom || 1, docSize));
    const fallbackTo = Math.max(fallbackFrom, Math.min(safeTo || fallbackFrom, docSize));
    return { from: fallbackFrom, to: fallbackTo };
  }
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
          const normalizedRange = normalizeSelectionRange(
            transaction.doc,
            awareness.from,
            awareness.to
          );
          const safeFrom = normalizedRange.from;
          const safeTo = normalizedRange.to;
          const color = awareness.color || '#4f46e5';

          if (safeFrom === safeTo) {
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

function buildSendableStepPayload(editor, lineSpacing, batchMetadata) {
  const pending = sendableSteps(editor.state);
  if (!pending || pending.steps.length === 0) {
    return null;
  }

  return {
    batchId: batchMetadata?.batchId ?? makeBatchId(),
    version: pending.version,
    clientId: String(pending.clientID),
    steps: pending.steps.map((step) => step.toJSON()),
    content: editor.getHTML(),
    lineSpacing,
    affectedRange: batchMetadata?.affectedRange ?? {
      start: editor.state.selection.from,
      end: editor.state.selection.to,
    },
    candidateContentSnapshot: batchMetadata?.candidateContentSnapshot ?? '',
    exactTextSnapshot: batchMetadata?.exactTextSnapshot ?? '',
    prefixContext: batchMetadata?.prefixContext ?? '',
    suffixContext: batchMetadata?.suffixContext ?? '',
  };
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
  const editorSurfaceRef = useRef(null);
  const remoteCaretUpdateFrameRef = useRef(null);
  const lastEmittedContentRef = useRef(content || '');
  const highlightSignatureRef = useRef('');
  const awarenessSignatureRef = useRef('');
  const [remoteCaretOverlays, setRemoteCaretOverlays] = useState([]);

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
    editorProps: {
      attributes: {
        spellcheck: 'false',
        autocorrect: 'off',
        autocapitalize: 'off',
        translate: 'no',
        'data-gramm': 'false',
        'data-gramm_editor': 'false',
        'data-enable-grammarly': 'false',
      },
    },
    onTransaction({ editor, transaction }) {
      const isRemote = applyingRemoteRef.current;
      const pending = collaborationEnabled ? sendableSteps(editor.state) : null;
      const batchMetadata = !isRemote ? buildStepBatchMetadata(transaction) : null;
      if (transaction.docChanged || isRemote) {
        const nextHtml = editor.getHTML();
        lastEmittedContentRef.current = nextHtml;
        changeHandlerRef.current?.(nextHtml, {
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
            const payload = buildSendableStepPayload(editor, lineSpacingRef.current, batchMetadata);
            if (payload) {
              sendableStepsHandlerRef.current?.(payload);
            }
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
        const normalizedSelection = normalizeSelectionRange(editor.state.doc, from, to);
        const text = normalizedSelection.from === normalizedSelection.to
          ? ''
          : editor.state.doc.textBetween(
            normalizedSelection.from,
            normalizedSelection.to,
            ' '
          );
        selectionHandlerRef.current({
          text,
          from: normalizedSelection.from,
          to: normalizedSelection.to,
          direction: anchor <= head ? 'forward' : 'backward',
        });
      }
    },
  }, [collaborationEnabled, collaborationResetKey]);

  const updateRemoteCaretOverlays = useCallback(() => {
    if (!editor || !editorSurfaceRef.current) {
      setRemoteCaretOverlays([]);
      return;
    }

    const shellRect = editorSurfaceRef.current.getBoundingClientRect();
    const overlays = (remoteAwarenessRef.current || [])
      .filter((entry) => Number.isFinite(entry?.from) && Number.isFinite(entry?.to))
      .map((entry) => {
        const normalizedSelection = normalizeSelectionRange(
          editor.state.doc,
          entry.from,
          entry.to
        );

        if (normalizedSelection.from !== normalizedSelection.to) {
          return null;
        }

        try {
          const coords = editor.view.coordsAtPos(normalizedSelection.from);
          const left = coords.left - shellRect.left;
          const top = coords.top - shellRect.top;

          if (!Number.isFinite(left) || !Number.isFinite(top)) {
            return null;
          }

          if (
            left < -32
            || left > shellRect.width + 32
            || top < -32
            || top > shellRect.height + 32
          ) {
            return null;
          }

          return {
            sessionId: entry.sessionId,
            label: entry.label || 'Collaborator',
            color: entry.color || '#4f46e5',
            left,
            top,
          };
        } catch {
          return null;
        }
      })
      .filter(Boolean);

    setRemoteCaretOverlays(overlays);
  }, [editor]);

  const scheduleRemoteCaretOverlayUpdate = useCallback(() => {
    if (typeof window === 'undefined') {
      updateRemoteCaretOverlays();
      return;
    }

    if (remoteCaretUpdateFrameRef.current !== null) {
      window.cancelAnimationFrame(remoteCaretUpdateFrameRef.current);
    }

    remoteCaretUpdateFrameRef.current = window.requestAnimationFrame(() => {
      remoteCaretUpdateFrameRef.current = null;
      updateRemoteCaretOverlays();
    });
  }, [updateRemoteCaretOverlays]);

  // Expose imperative API via ref
  useImperativeHandle(ref, () => ({
    getSelectionData() {
      if (!editor) {
        return { text: '', from: 0, to: 0 };
      }
      const normalizedSelection = normalizeSelectionRange(
        editor.state.doc,
        editor.state.selection.from,
        editor.state.selection.to
      );
      const text = normalizedSelection.from === normalizedSelection.to
        ? ''
        : editor.state.doc.textBetween(
          normalizedSelection.from,
          normalizedSelection.to,
          ' '
        );
      return {
        text,
        from: normalizedSelection.from,
        to: normalizedSelection.to,
      };
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
    getViewState() {
      if (!editor) {
        return {
          hasFocus: false,
          selection: { from: 1, to: 1 },
        };
      }

      const { from, to } = editor.state.selection;
      return {
        hasFocus: Boolean(editor.isFocused || editor.view.hasFocus()),
        selection: { from, to },
      };
    },
    restoreViewState(snapshot) {
      if (!editor || !snapshot?.hasFocus) {
        return false;
      }

      const nextSelection = clampSelectionPosition(
        editor,
        snapshot.selection?.from,
        snapshot.selection?.to
      );
      editor.commands.focus();
      editor.commands.setTextSelection(nextSelection);
      return true;
    },
    setSelection({ from, to = from }) {
      if (!editor) {
        return false;
      }

      return editor.commands.setTextSelection(clampSelectionPosition(editor, from, to));
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
      const previousSelection = {
        from: editor.state.selection.from,
        to: editor.state.selection.to,
      };
      const hadFocus = Boolean(editor.isFocused || editor.view.hasFocus());
      applyingRemoteRef.current = true;
      const transaction = receiveTransaction(editor.state, parsedSteps, clientIds);
      const selectionWasCollapsed = previousSelection.from === previousSelection.to;
      const nextSelection = hadFocus
        ? normalizeSelectionRange(
          transaction.doc,
          transaction.mapping.map(previousSelection.from, selectionWasCollapsed ? 1 : -1),
          transaction.mapping.map(previousSelection.to, 1)
        )
        : null;
      editor.view.dispatch(transaction);
      if (nextSelection) {
        editor.commands.setTextSelection(
          selectionWasCollapsed
            ? { from: nextSelection.from, to: nextSelection.from }
            : nextSelection
        );
      }
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
    getPendingStepBatch() {
      if (!editor || !collaborationEnabled) {
        return null;
      }
      return buildSendableStepPayload(editor, lineSpacingRef.current, null);
    },
    hasPendingCollaborationSteps() {
      if (!editor || !collaborationEnabled) {
        return false;
      }
      const pending = sendableSteps(editor.state);
      return Boolean(pending?.steps?.length);
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
      lastEmittedContentRef.current = content;
      return;
    }

    if (content === lastEmittedContentRef.current) {
      return;
    }

    lastEmittedContentRef.current = content || '';
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
      .map((entry) => {
        const normalizedSelection = normalizeSelectionRange(
          editor.state.doc,
          entry.from,
          entry.to
        );
        return {
          sessionId: entry.sessionId,
          from: normalizedSelection.from,
          to: normalizedSelection.to,
          color: entry.color,
          label: entry.label,
        };
      });
    const signature = JSON.stringify(awareness);
    if (signature === awarenessSignatureRef.current) {
      return;
    }
    awarenessSignatureRef.current = signature;
    editor.view.dispatch(editor.state.tr.setMeta(REMOTE_AWARENESS_KEY, awareness));
  }, [editor, remoteAwareness]);

  useEffect(() => {
    if (!editor) {
      return;
    }
    scheduleRemoteCaretOverlayUpdate();
  }, [editor, remoteAwareness, scheduleRemoteCaretOverlayUpdate]);

  useEffect(() => {
    if (!editor) {
      return undefined;
    }

    const scrollElement = editorSurfaceRef.current?.querySelector('.editor-content');
    const handleScroll = () => scheduleRemoteCaretOverlayUpdate();
    const handleResize = () => scheduleRemoteCaretOverlayUpdate();
    const handleTransaction = () => scheduleRemoteCaretOverlayUpdate();

    scrollElement?.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize);
    editor.on('transaction', handleTransaction);
    scheduleRemoteCaretOverlayUpdate();

    return () => {
      scrollElement?.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
      editor.off('transaction', handleTransaction);
      if (remoteCaretUpdateFrameRef.current !== null) {
        window.cancelAnimationFrame(remoteCaretUpdateFrameRef.current);
        remoteCaretUpdateFrameRef.current = null;
      }
    };
  }, [editor, scheduleRemoteCaretOverlayUpdate]);

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
      <div className="editor-content-shell" ref={editorSurfaceRef}>
        <EditorContent editor={editor} className="editor-content" />
        <div className="editor-remote-awareness-overlay" aria-hidden="true">
          {remoteCaretOverlays.map((overlay) => (
            <div
              key={overlay.sessionId || `${overlay.label}-${overlay.left}-${overlay.top}`}
              className="editor-remote-caret"
              data-session-id={String(overlay.sessionId || '')}
              style={{
                left: `${overlay.left}px`,
                top: `${overlay.top}px`,
                '--remote-awareness-color': overlay.color,
              }}
            >
              <span className="editor-remote-caret-label">{overlay.label}</span>
              <span className="editor-remote-caret-line" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

export default TiptapEditor;
