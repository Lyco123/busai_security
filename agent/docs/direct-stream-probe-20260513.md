# Direct Stream Probe

Date: 2026-05-13

## Purpose

This probe is for diagnosing two questions without adding high-frequency Worker logs:

1. Why the first visible token appears late.
2. Why the streaming experience feels coarser than direct provider streaming.

## Endpoints

```text
POST /api/agent/chat/direct-stream-probe
POST /api/agent/chat/pipeline-stream-probe
```

Request body:

```json
{
  "content": "Your prompt here",
  "routerMode": "command"
}
```

`routerMode` is only used by `pipeline-stream-probe`. Supported values are
`command` and `function`; omitted values default to `command`.

`direct-stream-probe` behavior:

- Calls the configured OpenAI-compatible chat completion endpoint with `stream: true`.
- Uses `OPENAI_WORKER_MODEL`, then `OPENAI_MODEL`, then the runtime default model.
- Sends the provider response body back to the browser directly as `text/event-stream`.
- Does not create sessions, save messages, invoke router logic, or call tools.

`pipeline-stream-probe` behavior:

- Runs the normal agent routing and worker pipeline with `isStream: true`.
- Emits the same assistant delta, progress, and tool events used by the chat stream.
- Does not create sessions, save user messages, save assistant messages, generate titles, or complete queued runs.
- Allows the probe page to compare provider baseline versus the full agent pipeline without modifying the production assistant page.

## Frontend Monitor

Admin users can open:

```text
/research/stream-probe
```

The page has three modes:

- `Direct model`: calls `direct-stream-probe`.
- `Agent pipeline`: calls `pipeline-stream-probe`.
- `Compare routers`: calls `pipeline-stream-probe` twice, first with
  `routerMode=command`, then with `routerMode=function`. The two requests are
  intentionally serial so router timing is not distorted by probe-created
  concurrent model calls.

Both modes record timing in the browser:

- first response byte
- first complete SSE event
- first visible text delta
- chunk count
- SSE event count
- text delta count
- streamed text size
- first 80 text delta samples
- delta gap samples

Pipeline mode also records:

- progress event count
- tool event count
- first 160 pipeline event samples
- tool call arguments and tool execution result summaries when those events are
  emitted. `resultSummary.result_count` is included when the tool result uses a
  `result` array or object envelope, so empty-list and non-empty-list results
  are distinguishable in exported probe snapshots.
- probe stage samples emitted only by the probe path:
  - `pipeline_started`
  - `pre_router_opening_emitted`
  - `route_request_started`
  - `rule_match_started`
  - `rule_match_done`
  - `router_call_started`
  - `router_call_done`
  - `worker_selected`
  - `worker_started`
  - `main_iteration_started`
  - `main_first_delta`
  - `main_iteration_done`
  - `route_request_done`

Router temperature is intentionally shared between command and function router
probe paths through the backend router temperature constant. This keeps timing
and route-choice comparisons from being distorted by different sampling
temperatures.

This keeps the Worker hot path minimal while still showing whether latency comes from:

- upstream first-byte delay
- provider events arriving before visible text
- coarse text delta granularity

## How To Read It

### Case A: First byte is late

- `First byte` is already large.
- The provider or upstream network path is the dominant delay.

### Case B: Events arrive before text

- `First byte` and `First event` are close.
- `First text` is much later.
- The provider is sending early SSE events that do not yet contain visible content.

### Case C: Streaming feels chunky

- `Text deltas` is low for a long answer.
- Delta sample lengths are large, or gap samples are wide.
- The provider stream itself is already coarse before the conversational agent pipeline is involved.

## Scope

Direct mode is intentionally not equivalent to the full conversational pipeline.

Direct mode does not measure:

- router selection
- opening/progress generation
- tool call detection
- tool execution
- agent-side content aggregation
- frontend assistant message rendering

Use it as the provider-side baseline. Compare it against the normal `/chat/stream` path to separate upstream streaming quality from agent pipeline behavior.

Pipeline mode is closer to `/chat/stream`, but it still avoids production side effects:

- no session persistence
- no queued run lifecycle
- no title generation
- no final message write
- no production SSE protocol changes; stage events are passed only through `pipeline-stream-probe`

Production `/chat/stream` now emits a low-cost static opening before router work begins, then suppresses worker-generated stage text to avoid duplicate opening content. Pipeline mode mirrors that behavior so the probe reflects the visible production timing without session side effects.

This keeps the probe removable as one module: delete the two endpoints, the frontend page/client methods, and this document.
