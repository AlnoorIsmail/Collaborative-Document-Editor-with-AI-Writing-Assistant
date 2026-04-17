import { forwardRef, useEffect, useImperativeHandle } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';

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

function Toolbar({ editor }) {
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
 *
 * Ref methods:
 *   getSelectedText() - returns the currently selected text
 */
const TiptapEditor = forwardRef(function TiptapEditor(
  { content, onChange, readOnly = false, placeholder = 'Start writing…', onSelectionUpdate },
  ref
) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder }),
    ],
    content,
    editable: !readOnly,
    onUpdate({ editor }) {
      onChange?.(editor.getHTML());
    },
    onSelectionUpdate({ editor }) {
      if (!onSelectionUpdate) return;

      const { from, to } = editor.state.selection;
      const text = from === to ? '' : editor.state.doc.textBetween(from, to, ' ');

      onSelectionUpdate({ text, from, to });
    },
  });

  // Expose imperative API via ref
  useImperativeHandle(ref, () => ({
    getSelectedText() {
      if (!editor) return '';
      const { from, to } = editor.state.selection;
      if (from === to) return '';
      return editor.state.doc.textBetween(from, to, ' ');
    },
    getHTML() {
      return editor?.getHTML() ?? '';
    },
    getText() {
      return editor?.getText() ?? '';
    },
    getSelection() {
      if (!editor) {
        return { text: '', from: 0, to: 0 };
      }

      const { from, to } = editor.state.selection;

      return {
        text: from === to ? '' : editor.state.doc.textBetween(from, to, ' '),
        from,
        to,
      };
    },
    setContent(nextContent) {
      if (!editor) return '';
      editor.commands.setContent(nextContent || '', false);
      return editor.getHTML();
    },
    replaceRange(from, to, text) {
      if (!editor) return '';
      editor.chain().focus().insertContentAt({ from, to }, text).run();
      return editor.getHTML();
    },
    focus() {
      editor?.commands.focus();
    },
  }), [editor]);

  // Sync editable state when readOnly prop changes
  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!readOnly);
  }, [editor, readOnly]);

  useEffect(() => {
    if (!editor || typeof content !== 'string') return;
    if (content === editor.getHTML()) return;
    editor.commands.setContent(content || '', false);
  }, [editor, content]);

  return (
    <div className={`editor-wrapper ${readOnly ? 'editor-readonly' : ''}`}>
      {!readOnly && <Toolbar editor={editor} />}
      <EditorContent editor={editor} className="editor-content" />
    </div>
  );
});

export default TiptapEditor;
