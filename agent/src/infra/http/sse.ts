export interface SseWriter {
  send: (payload: unknown) => void;
  done: () => void;
}

export function createSseWriter(controller: ReadableStreamDefaultController<Uint8Array>): SseWriter {
  const encoder = new TextEncoder();
  return {
    send(payload) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
    },
    done() {
      controller.enqueue(encoder.encode('data: [DONE]\n\n'));
    },
  };
}

export function sseResponse(stream: ReadableStream): Response {
  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  });
}
