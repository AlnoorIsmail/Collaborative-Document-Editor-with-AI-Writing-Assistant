import { fireEvent, render, waitFor } from '@testing-library/react';
import { createRef } from 'react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import TiptapEditor from '../components/TiptapEditor';

function getEditorElement(container) {
  const editor = container.querySelector('.ProseMirror');
  if (!editor) {
    throw new Error('Expected ProseMirror editor element.');
  }
  return editor;
}

beforeAll(() => {
  const emptyDOMRect = {
    x: 0,
    y: 0,
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    width: 0,
    height: 0,
    toJSON: () => ({}),
  };

  if (!Range.prototype.getBoundingClientRect) {
    Range.prototype.getBoundingClientRect = () => emptyDOMRect;
  }
  if (!Range.prototype.getClientRects) {
    Range.prototype.getClientRects = () => [];
  }
  if (!HTMLElement.prototype.getBoundingClientRect) {
    HTMLElement.prototype.getBoundingClientRect = () => emptyDOMRect;
  }
  if (!HTMLElement.prototype.getClientRects) {
    HTMLElement.prototype.getClientRects = () => [];
  }
  if (!HTMLElement.prototype.scrollIntoView) {
    HTMLElement.prototype.scrollIntoView = () => {};
  }
  if (!document.elementFromPoint) {
    document.elementFromPoint = () => document.body;
  }
});

describe('TiptapEditor', () => {
  it('applies the provided line spacing and surfaces toolbar changes', async () => {
    const onLineSpacingChange = vi.fn();
    const { container, getByLabelText } = render(
      <TiptapEditor
        content="<p>Draft body</p>"
        lineSpacing={1.5}
        onLineSpacingChange={onLineSpacingChange}
      />
    );

    await waitFor(() => {
      expect(
        container.querySelector('.editor-wrapper')?.style.getPropertyValue('--editor-line-spacing')
      ).toBe('1.5');
    });

    fireEvent.change(getByLabelText('Line spacing'), {
      target: { value: '2' },
    });

    expect(onLineSpacingChange).toHaveBeenCalledWith(2);
  });

  it('keeps Enter as a paragraph break and Shift+Enter as a soft line break', async () => {
    const ref = createRef();
    const { unmount } = render(
      <TiptapEditor
        ref={ref}
        content=""
      />
    );

    await waitFor(() => {
      expect(ref.current).toBeTruthy();
    });

    ref.current.replaceRange({ from: 1, to: 1, text: 'Hello' });
    ref.current.setSelection({ from: 6 });
    ref.current.insertParagraphBreak();
    ref.current.replaceRange({ from: 8, to: 8, text: 'World' });

    await waitFor(() => {
      expect(ref.current.getHTML()).toContain('<p>Hello</p><p>World</p>');
    });

    unmount();

    const hardBreakRef = createRef();
    const hardBreakRender = render(
      <TiptapEditor
        ref={hardBreakRef}
        content=""
      />
    );

    await waitFor(() => {
      expect(hardBreakRef.current).toBeTruthy();
    });

    hardBreakRef.current.replaceRange({ from: 1, to: 1, text: 'Hello' });
    hardBreakRef.current.setSelection({ from: 6 });
    hardBreakRef.current.insertHardBreak();
    hardBreakRef.current.replaceRange({ from: 7, to: 7, text: 'World' });

    await waitFor(() => {
      expect(hardBreakRef.current.getHTML()).toContain('<p>Hello<br>World</p>');
    });
  });
});
