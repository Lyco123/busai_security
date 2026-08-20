export async function processOpenAIStream(
  stream: ReadableStream,
  onDelta: (delta: string) => void,
  onReasoningDelta?: (delta: { delta: string; field: 'reasoning' | 'reasoning_content' }) => void
): Promise<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let fullContent = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed === '' || trimmed === 'data: [DONE]') continue;
        if (trimmed.startsWith('data: ')) {
          try {
            const json = JSON.parse(trimmed.slice(6));
            const streamDelta = json.choices?.[0]?.delta;
            const delta = streamDelta?.content;
            if (delta) {
              fullContent += delta;
              onDelta(delta);
            }
            const reasoningDelta =
              typeof streamDelta?.reasoning_content === 'string' && streamDelta.reasoning_content
                ? { field: 'reasoning_content' as const, delta: streamDelta.reasoning_content }
                : typeof streamDelta?.reasoning === 'string' && streamDelta.reasoning
                  ? { field: 'reasoning' as const, delta: streamDelta.reasoning }
                  : null;
            if (reasoningDelta) {
              onReasoningDelta?.(reasoningDelta);
            }
          } catch (error) {
            console.error('Error parsing stream line:', line, error);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
  return fullContent;
}
