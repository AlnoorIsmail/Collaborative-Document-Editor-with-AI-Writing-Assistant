export function createEmptyAiState() {
  return {
    status: 'idle',
    output: '',
    editableOutput: '',
    error: '',
    interactionId: '',
    suggestionId: '',
    baselineText: '',
    baselineContent: '',
    selection: null,
    scope: 'document',
    partialOutputPreserved: false,
  };
}

function createAbortError() {
  const error = new Error('The request was cancelled.');
  error.name = 'AbortError';
  return error;
}

function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      signal?.removeEventListener?.('abort', handleAbort);
      resolve();
    }, ms);

    function handleAbort() {
      window.clearTimeout(timeoutId);
      reject(createAbortError());
    }

    if (signal?.aborted) {
      handleAbort();
      return;
    }

    signal?.addEventListener?.('abort', handleAbort, { once: true });
  });
}

export async function streamTextProgressively({ text, signal, onUpdate }) {
  const tokens = text.split(/(\s+)/).filter(Boolean);
  let output = '';

  for (const token of tokens) {
    if (signal?.aborted) {
      throw createAbortError();
    }

    output += token;
    onUpdate(output);
    await wait(token.trim() ? 28 : 12, signal);
  }

  return text;
}

export async function pollAiInteraction({ interactionId, request, signal }) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    if (signal?.aborted) {
      throw createAbortError();
    }

    const detail = await request(`/ai/interactions/${interactionId}`, { signal });

    if (detail.status === 'failed') {
      throw new Error('The backend AI interaction failed.');
    }

    if (detail.suggestion?.generated_output) {
      return detail;
    }

    await wait(250, signal);
  }

  throw new Error('The backend did not return an AI suggestion in time.');
}

function mapStatus(status) {
  if (status === 'completed') return 'ready';
  if (status === 'processing') return 'streaming';
  if (status === 'failed') return 'error';
  return status || 'idle';
}

export function mapAiHistoryEntry(interaction, detail = null) {
  return {
    id: interaction.interaction_id,
    feature: interaction.feature_type,
    instruction: 'Loaded from backend interaction history.',
    status: mapStatus(interaction.status),
    scope: detail?.scope_type || 'document',
    model: detail?.suggestion?.model_name || 'backend-ai',
    partialOutput: false,
    originalText: '',
    suggestionText: detail?.suggestion?.generated_output || '',
    createdAt: interaction.created_at,
    suggestionId: detail?.suggestion?.suggestion_id || '',
    stale: Boolean(detail?.suggestion?.stale),
  };
}
