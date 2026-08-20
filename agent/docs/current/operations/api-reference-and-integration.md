# API Reference and Integration

## API Root

Agent APIs are dispatched under the configured API prefix from `agent/src/core/constants.ts`. The Worker HTTP router handles API dispatch in `agent/src/app/http-router.ts`.

Common route groups:

- health
- auth
- chat
- sessions
- rules
- rule config
- scenarios
- aliases
- research/evaluation
- KB proxy
- AB test stats

## Important Endpoints

Representative endpoints in the current Worker:

- `GET /api/agent/health`
- `GET /api/agent/auth/me`
- `POST /api/agent/auth/login`
- `POST /api/agent/auth/logout`
- chat endpoints handled by `agent/src/domains/chat/handlers.ts`
- session endpoints handled by `agent/src/domains/sessions/handlers.ts`
- rules endpoints handled by `agent/src/domains/rules/handlers.ts`
- rule config endpoints handled by `agent/src/domains/rules/rule-config/http-handlers.ts`
- research endpoints handled by `agent/src/domains/research/handlers.ts`
- KB proxy endpoints under `/api/agent/kb/*`

Use the code handlers as source of truth if endpoint names drift from older documents.
For KB/RAG request and response contracts, use [知识库系统 API 接口文档](./知识库系统API接口文档.md).

## Existing Source Documents

- `agent/docs/Agent系统API接口文档.md`
- `agent/docs/api-docs/README.md`
- `agent/docs/api-docs/deployment.md`
- `agent/docs/current/operations/知识库系统API接口文档.md` for KB/RAG API contracts.
- `agent/retrieval/README.md` for KB service deployment and quick curl checks.

## Integration Notes

Frontend integration points include:

- `frtend-tsx/src/services/agentClient.ts`
- `frtend-tsx/src/services/knowledgeBaseClient.ts`
- `frtend-tsx/src/services/researchClient.ts`
- `frtend-tsx/src/pages/ai/**`
- `frtend-tsx/src/pages/research/**`
- `frtend-tsx/src/pages/settings/KnowledgeBase*.tsx`

## Gaps

- Current API documentation should be regenerated from handlers or contract tests.
- The older API PDF/Markdown docs may not reflect newer research and probe endpoints.
