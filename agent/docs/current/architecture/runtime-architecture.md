# Runtime Architecture

## Responsibility

The runtime is the service composition layer for the Worker. It is responsible for wiring dependencies, not for owning business logic.

Current entry point:

- `agent/src/app/runtime.ts`

Important delegated modules:

- HTTP dispatch: `agent/src/app/http-router.ts`
- Chat turn handling: `agent/src/domains/chat/chat-service.ts`
- Router loop: `agent/src/domains/chat/router-service.ts`
- Worker execution: `agent/src/domains/chat/worker-runner.ts`
- Tool provider: `agent/src/tools/provider.ts`
- OpenAI-compatible wrappers: `agent/src/infra/llm/*`
- KB proxy/query: `agent/src/infra/kb-proxy.ts`, `agent/src/infra/kb-query-tool.ts`

## Current Shape

```text
runtime.ts
  imports skills
  creates repositories/services
  creates ToolProvider
  creates worker runner
  creates router service
  creates chat service
  creates HTTP handler
  exports Worker fetch
```

`runtime.ts` should remain a composition root unless there is a clear reason to introduce another bootstrap layer.

## Boundaries Already Split Out

The old all-in-one runtime has already been reduced. The following concerns now live outside `runtime.ts`:

- HTTP routing and auth dispatch.
- Chat request lifecycle.
- Router prompt construction and router tool validation.
- Worker execution and stream/non-stream handling.
- Query data tool implementation.
- KB query tool and KB proxy.
- OpenAI chat/router/stream wrappers.
- Session repository and title generation.
- Rule, scenario, research, alias, and AB-test domain services.

## Runtime-Owned Wiring

The runtime still owns:

- Skill import map.
- Worker tool names and skill assignment.
- Env type shape.
- Dependency injection into services.
- Model wrapper selection.
- Tool provider construction.
- Rule/scenario/session/research service wiring.
- Worker `fetch` export.

This is acceptable for the current scale. Further extraction should target large behavior blocks, not split the composition root into scattered factories.

## Environment Inputs

Important env vars include:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_ROUTER_MODEL`
- `OPENAI_WORKER_MODEL`
- `OPENAI_REPORT_BASE_URL`
- `OPENAI_REPORT_API_KEY`
- `OPENAI_REPORT_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `EMBEDDING_MODEL`
- `OPENAI_STREAM_DIAGNOSTICS`
- `CORS_ALLOWED_ORIGINS`
- `KB_API_BASE_URL`
- `KB_API_TIMEOUT_MS`
- `KB_DEFAULT_ID`
- `KB_TOOL_ENABLED`
- `KB_TENANT_ID`
- `MCP_SERVER_URL`
- `CF_ACCESS_CLIENT_ID`
- `CF_ACCESS_CLIENT_SECRET`
- `MCP_ACCESS_TOKEN`

## Historical Sources

- `agent/docs/runtime.md`
- `agent/docs/agent_devdoc.md`
- `agent/docs/weekly_reports/260408/md/agent开发周报260408.md`

## Gaps

- `runtime.md` is a dated snapshot and should not be treated as complete after newer station/expert/KB additions.
- Env var ownership is still implicit in code; a generated env reference would reduce drift.
- There is no architecture diagram artifact checked in; this document uses text diagrams only.
