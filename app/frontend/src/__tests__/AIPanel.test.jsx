import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AIPanel from '../components/AIPanel';

function renderAIPanel(overrides = {}) {
  const handleAccept = vi.fn();
  const handleReject = vi.fn();
  const handleCancel = vi.fn();

  function Wrapper() {
    const [aiForm, setAiForm] = useState({
      feature: 'rewrite',
      instruction: '',
    });
    const [aiState, setAiState] = useState({
      status: 'ready',
      output: 'Original AI suggestion',
      editableOutput: 'Original AI suggestion',
      error: '',
      interactionId: 'ai-1',
      suggestionId: 'sug-1',
      baselineText: 'Original paragraph',
      baselineContent: '<p>Original paragraph</p>',
      selection: { text: 'Original paragraph', from: 1, to: 18 },
      scope: 'selection',
      partialOutputPreserved: false,
      ...overrides.aiState,
    });

    return (
      <AIPanel
        role="owner"
        aiEnabled
        aiForm={{ ...aiForm, ...overrides.aiForm }}
        aiState={aiState}
        aiHistory={overrides.aiHistory || []}
        selectionState={overrides.selectionState || { text: 'Original paragraph', from: 1, to: 18 }}
        undoState={overrides.undoState || null}
        onFeatureChange={(feature) => setAiForm((current) => ({ ...current, feature }))}
        onInstructionChange={(instruction) =>
          setAiForm((current) => ({ ...current, instruction }))
        }
        onGenerateSuggestion={vi.fn()}
        onCancelSuggestion={handleCancel}
        onClearSuggestion={() => setAiState((current) => ({ ...current, editableOutput: '' }))}
        onSuggestionChange={(editableOutput) =>
          setAiState((current) => ({ ...current, editableOutput }))
        }
        onAcceptSuggestion={handleAccept}
        onRejectSuggestion={handleReject}
        onUndoSuggestion={vi.fn()}
      />
    );
  }

  render(<Wrapper />);

  return { handleAccept, handleReject, handleCancel };
}

describe('AIPanel', () => {
  it('lets the user edit and accept a suggestion', async () => {
    const user = userEvent.setup();
    const { handleAccept } = renderAIPanel();

    const suggestion = screen.getByTestId('editable-suggestion');
    await user.clear(suggestion);
    await user.type(suggestion, 'Edited by Afsah');
    await user.click(screen.getByTestId('accept-ai-button'));

    expect(suggestion).toHaveValue('Edited by Afsah');
    expect(handleAccept).toHaveBeenCalled();
  });

  it('allows rejecting a ready suggestion', async () => {
    const user = userEvent.setup();
    const { handleReject } = renderAIPanel();

    await user.click(screen.getByTestId('reject-ai-button'));

    expect(handleReject).toHaveBeenCalled();
  });

  it('shows partial streaming output and exposes the cancel button', async () => {
    const user = userEvent.setup();
    const { handleCancel } = renderAIPanel({
      aiState: {
        status: 'streaming',
        output: 'Partial stream',
        editableOutput: '',
        partialOutputPreserved: true,
      },
    });

    expect(screen.getByTestId('editable-suggestion')).toHaveValue('Partial stream');
    expect(
      screen.getByText(/Partial output was preserved so you can still inspect or edit it/i),
    ).toBeInTheDocument();

    await user.click(screen.getByTestId('cancel-ai-button'));

    expect(handleCancel).toHaveBeenCalled();
  });
});
