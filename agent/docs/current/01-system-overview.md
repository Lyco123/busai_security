# Agent System Overview

## Current Scope

The agent system is a Cloudflare Workers based TypeScript service under `agent/`. It powers chat, routed expert consultation, structured report generation, rule configuration, research/evaluation pages, MCP tool access, and KB/RAG retrieval integration.

The current implementation is not a single monolithic agent. It is a routed runtime:

```text
HTTP request
  -> auth and API router
  -> chat service
  -> router service
  -> worker runner
  -> tool provider
  -> local tools / MCP / KB / LLM
  -> message, sources, metadata, stream or JSON response
```

## Main Runtime Modules

- `agent/src/app/runtime.ts`: composition root. Imports skills, wires services, tools, model wrappers, repositories, and HTTP router.
- `agent/src/app/http-router.ts`: API dispatch, auth endpoints, KB proxy dispatch, chat/research/rules/sessions routing.
- `agent/src/domains/chat/chat-service.ts`: chat turn lifecycle, session persistence, stream/non-stream handling.
- `agent/src/domains/chat/router-service.ts`: router loop, tool decision, validation, clarification, worker dispatch.
- `agent/src/domains/chat/worker-runner.ts`: skill execution, worker LLM calls, tool calls, opening/closing, structured report handling.
- `agent/src/tools/provider.ts`: tool registry and execution bridge for local tools, MCP, and KB tool exposure.
- `agent/src/infra/llm/*`: OpenAI-compatible chat, router, stream, embedding wrappers.
- `agent/src/infra/kb-query-tool.ts` and `agent/src/infra/kb-proxy.ts`: edge-side KB query tool and HTTP proxy.
- `agent/retrieval/`: standalone KB retrieval service with ClickHouse, Qdrant, file ingestion, OCR option, and worker indexing.

## Agent Capabilities

The current skill set is split into router, conversational workers, and structured workers.

Router:

- `agent/skills/router/SKILL.md`

Conversational workers:

- `consult_omni`
- `consult_driver_expert`
- `consult_vehicle_expert`
- `consult_unit_expert`
- `consult_route_expert`
- `consult_station_expert`
- `consult_incident_expert`
- `rule_asker`
- `rule_reply`

Structured workers:

- `generate_driver_report`
- `generate_vehicle_report`
- `generate_unit_report`
- `generate_route_report`
- `generate_station_report`
- `generate_accident_investigation_report`
- `rule_builder`

## Domain Coverage

The current expert registry covers six domains:

- driver
- vehicle
- unit
- route
- station
- incident

Each domain has a consult path and a report path where applicable. Older documents may mention five domains because station was added later.

## Data and Tool Surfaces

The worker can use several data surfaces:

- Structured profile/report sources through local data and MCP-oriented helpers.
- Rule tools for rule matching, rule replies, and rule configuration.
- KB retrieval through the `query_kb` tool when enabled.
- MCP tools through `MCP_SERVER_URL` and related credentials.
- Session history, latest structured report context, and pending clarification state.

## Documentation Coverage

This directory is the current documentation entry point. Older documents remain useful as source material but should not be treated as the complete current state.

Covered by this set:

- Current runtime shape and code map.
- Router and prompt ownership.
- Expert registry and context builder.
- KB/RAG architecture and permissions.
- MCP tooling boundary.
- Report generation pipeline.
- Streaming and probe mechanisms.
- API/deployment/testing handoff.

Still intentionally marked as gaps:

- A fully formal entity resolution pipeline is not yet documented as implemented because code remains partly domain-specific.
- Production-grade observability and alerting are not fully specified.
- Some historical documents have encoding issues and should be normalized separately if they remain part of the official archive.
