# Streaming and Output Protocol

## Scope

Streaming covers the user-visible chat stream and diagnostic probes. It does not mean every pipeline emits model token deltas.

## Chat Stream Shape

Normal streaming chat uses SSE:

```text
start
delta*
final
[DONE]
```

The stream may contain:

- pre-router opening text
- worker model deltas
- chunked non-stream content
- trailing/closing text
- final message metadata and sources

Primary files:

- `agent/src/domains/chat/chat-service.ts`
- `agent/src/infra/llm/stream.ts`
- `agent/src/infra/http/sse.ts`
- `agent/src/infra/llm/chat-completions.ts`

## Opening and Closing

The worker runner supports lightweight staged wording:

- pre-router opening
- consult/report opening
- report closing or trailing content

This is interaction polish around the main worker output. It should not hide routing or data errors.

## Diagnostic Probes

Diagnostic routes separate upstream LLM behavior from full agent behavior:

- Direct stream probe bypasses session/router/tools.
- Pipeline stream probe exercises the normal agent path with probe events.
- `OPENAI_STREAM_DIAGNOSTICS` can log upstream chunk/event/delta behavior.

Historical docs:

- `agent/docs/streaming-protocol-frontend-adaptation-20260512.md`
- `agent/docs/direct-stream-probe-20260513.md`
- `agent/docs/openai-stream-diagnostics-20260513.md`
- `agent/docs/streaming-unaffected-pipelines-plan-20260512.md`

## Known Non-Streaming or Partially Streaming Areas

Some flows may return non-stream content that is chunked for display, or may not participate in token streaming:

- report summary APIs
- direct structured report generation
- some rule config flows
- KB retrieval service itself
- OCR/index worker

## Gaps

- There is no single machine-readable event schema file for the frontend stream contract.
- Probe output interpretation still relies on docs and manual comparison.
