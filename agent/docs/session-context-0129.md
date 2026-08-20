# Session Context (Router)

This project now injects **session-only context** into the Router so each turn can see recent history and which tool generated the last outputs.

## What gets sent to the Router
- `system`: router skill prompt
- `system`: recent tool calls summary (tool + key args + profile + time)
- recent `user` / `assistant` messages (last 12, ordered)
- current user input

## Tool-aware compression
- For `generate_*` outputs, we **do not** send the full JSON.
- The Router sees a short summary like: `[tool=generate_driver_report] ...`
- This avoids token bloat while still keeping the “who did what” signal.

## Key parameters
- `CONTEXT_WINDOW_MESSAGES = 12`
- `TOOL_SUMMARY_LIMIT = 6`
- `TOOL_OUTPUT_PREVIEW_CHARS = 220`
- `MESSAGE_PREVIEW_CHARS = 600`

These constants live in `agent/src/index.ts` and can be tuned later.
