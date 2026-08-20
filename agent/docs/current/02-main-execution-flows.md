# Main Execution Flows

## Chat Request

```text
POST /api/agent/chat
  -> http-router resolves auth
  -> chat handler
  -> chat-service loads session/history
  -> optional rule/scenario precompute
  -> router-service decides tool
  -> worker-runner executes selected worker
  -> tools/LLM/KB/MCP as needed
  -> assistant message saved with metadata and sources
```

Primary files:

- `agent/src/app/http-router.ts`
- `agent/src/domains/chat/handlers.ts`
- `agent/src/domains/chat/chat-service.ts`
- `agent/src/domains/chat/router-service.ts`
- `agent/src/domains/chat/worker-runner.ts`

## Streaming Chat Request

```text
POST /api/agent/chat/stream
  -> same routing path as chat
  -> pre-router opening may emit first
  -> router returns worker output or stream
  -> chat-service converts deltas to SSE events
  -> final event includes message metadata and sources
```

Streaming concerns are separated:

- Business flow: `chat-service.ts`
- OpenAI stream parsing: `agent/src/infra/llm/stream.ts`
- SSE response helpers: `agent/src/infra/http/sse.ts`

## Router Decision Flow

```text
user prompt + history
  -> rule match/scenario context
  -> router skill + runtime supplements
  -> router tools schema
  -> model tool choice
  -> validation
  -> worker dispatch or clarification
```

The router should decide "which path", not generate long business answers itself. Tool validation handles missing required parameters, stale context recovery, and retry prompts.

## Consultation Flow

```text
router chooses consult_*
  -> expert registry identifies domain and runtime flags
  -> context builder adds latest report / pending clarification / COT prefix where configured
  -> worker-runner loads conversational skill
  -> worker may call tools
  -> Markdown answer returned or streamed
```

Consultation is for explanation, advice, interpretation, and follow-up. It does not create formal report artifacts.

## Structured Report Flow

```text
router chooses generate_*_report
  -> worker-runner loads structured skill
  -> structured report runtime config controls lookup, missing data retry, normalization, validation
  -> report source tools provide profile data
  -> model emits structured content
  -> normalizer validates and repairs expected shape
  -> response saved with report metadata and sources
```

Reports are domain-specific and stricter than consultation. Current report domains include driver, vehicle, unit, route, station, and accident investigation.

## KB Query Flow

```text
worker calls query_kb
  -> ToolProvider executes edge KB query tool
  -> kb-query-tool forwards to KB API
  -> retrieval service searches Qdrant and ClickHouse
  -> access filtering applies
  -> matching clauses return as tool result and message sources
```

For admin/document management, the front end uses Worker KB proxy endpoints, which forward `/api/agent/kb/*` to the retrieval service.

## Rule Flow

Rule handling has three related flows:

- Rule match before router, used as routing context.
- `rule_reply`, used when an existing rule should answer or ask for required parameters.
- Rule config/build flows, used by settings pages to create or edit rules.

Primary files:

- `agent/src/domains/rules/match-service.ts`
- `agent/src/domains/rules/rule-test-service.ts`
- `agent/src/domains/rules/rule-config/*`
- `agent/skills/conversational/rule_reply/SKILL.md`
- `agent/skills/structured/rule_builder/SKILL.md`

## Probe and Diagnostics Flow

Diagnostic endpoints separate upstream LLM streaming behavior from full agent behavior:

- Direct stream probe bypasses session, router, tools, and aggregation.
- Pipeline stream probe runs the normal pipeline with probe events.
- OpenAI stream diagnostics can log upstream chunks/events/deltas when enabled.
