# Code Map

## App Layer

- `agent/src/app/runtime.ts`: composition root and Worker export.
- `agent/src/app/http-router.ts`: HTTP/API router.
- `agent/src/app/deps.ts`: shared dependency types/helpers where present.

## Core

- `agent/src/core/constants.ts`: API constants.
- `agent/src/core/types.ts`: core shared types.

## Chat Domain

- `chat-service.ts`: chat turn lifecycle.
- `handlers.ts`: HTTP handlers for chat.
- `router-service.ts`: router loop and dispatch.
- `router-prompts.ts`: router runtime prompt pieces.
- `router-tools.ts`: router tool definitions.
- `router-tool-validation.ts`: router tool call validation.
- `worker-runner.ts`: worker execution.
- `structured-report-runtime.ts`: report runtime config.
- `structured-report-data-sources.ts`: report data sources.
- `structured-report-normalizers.ts`: shared report normalization.
- `structured-lookup.ts`: entity lookup and report lookup helpers.
- `context.ts`, `turn-context.ts`, `clarification-state.ts`: context and clarification helpers.
- `omni-kb-context.ts`: KB context helper for omni-style answers.

## Experts

- `agent/src/domains/experts/registry.ts`
- `agent/src/domains/experts/context-builder.ts`

## Tools and Infra

- `agent/src/tools/provider.ts`: local/MCP/KB tool provider.
- `agent/src/tools/query-data.ts`: local query data implementation.
- `agent/src/infra/kb-query-tool.ts`: edge-side KB tool client.
- `agent/src/infra/kb-proxy.ts`: KB HTTP proxy.
- `agent/src/infra/llm/*`: LLM wrappers.
- `agent/src/infra/http/*`: response, CORS, SSE helpers.
- `agent/src/infra/auth/*`: auth session and cookie helpers.

## Domains

- `domains/rules/**`: rules, matching, config, tests.
- `domains/scenarios/**`: work scenario matching.
- `domains/sessions/**`: sessions and routing context.
- `domains/research/**`: research/eval issue tracking.
- `domains/aliases/**`: entity aliases.
- `domains/ab-test/**`: AB experiment support.

## Retrieval Service

- `agent/retrieval/src/index.ts`: API entry.
- `agent/retrieval/src/services/kb-service.ts`: KB service operations.
- `agent/retrieval/src/services/job-worker.ts`: indexing worker.
- `agent/retrieval/src/services/document-parser.ts`: document parsing.
- `agent/retrieval/src/services/qdrant.ts`: vector search.
- `agent/retrieval/src/db/repository.ts`: ClickHouse repository.
- `agent/retrieval/sql/schema.sql`: schema.

## Frontend Integration

- `frtend-tsx/src/services/agentClient.ts`
- `frtend-tsx/src/services/knowledgeBaseClient.ts`
- `frtend-tsx/src/services/researchClient.ts`
- `frtend-tsx/src/pages/ai/**`
- `frtend-tsx/src/pages/research/**`
- `frtend-tsx/src/pages/settings/KnowledgeBase*.tsx`
