# `runtime.ts` 当前结构快照

更新时间：2026-04-13
目标文件：`agent/src/app/runtime.ts`
当前规模：709 行

## 一句话结论

`runtime.ts` 已经收敛为 Cloudflare Worker 入口和 service composition root。`query_data` 执行层、OpenAI chat/router/stream wrappers、HTTP/API dispatch 和 SSE 文本传输胶水已从 runtime 或 chat service 中迁出。

## 本轮完成

1. HTTP/API dispatch 拆分到 `agent/src/app/http-router.ts`

   迁出内容：
   - `handleRequest`
   - `handleAPIRequest`
   - OPTIONS / API prefix / CORS / cookie append
   - auth login/logout/me
   - KB proxy dispatch
   - research/rule-config/rules/scenarios/sessions/chat API 分发
   - researcher feature 权限判断和 owner scope 解析

   `runtime.ts` 现在只创建 `handleRequest` 并在 Worker `fetch` 中调用。

2. 网络文本传输拆分到 `agent/src/infra/http/sse.ts`

   迁出内容：
   - SSE `data: ...\n\n` 编码
   - `[DONE]` 结束帧
   - `text/event-stream` 响应头

   `chat-service` 只负责业务流转，SSE 写入细节交给 `infra/http/sse.ts`。

3. `query_data` 相关拆分到 `agent/src/tools/query-data.ts`

   迁出内容：
   - `DATA_SCHEMAS`
   - `QueryDataArgs` / action / entity 类型
   - `executeQueryData`
   - `pickFields` / `getNestedValue` / `setNestedValue`
   - `QUERY_DATA_READ_ACTIONS`
   - `normalizeQueryDataAction`
   - `hasQueryDataHit`
   - `buildQueryDataSignature`
   - `isReadNoHitResult`
   - `isNotFoundLikeError`

   现在 `runtime.ts` 只在 `createToolProvider` 中注入 `executeQueryData`，后续生产环境如果不要 `query_data`，主要删除 tool provider 接线和 worker runner 相关依赖即可。

4. OpenAI wrappers 拆分到 `agent/src/infra/llm/chat-completions.ts`

   迁出内容：
   - `callOpenAI`
   - `callOpenAIWithTools`
   - `callOpenAIStreamWithTools`
   - `callOpenAIRouter`
   - `callOpenAIStream`
   - OpenAI message/tool-call formatting
   - OpenAI 响应解析和错误处理

   `runtime.ts` 保留很薄的接线逻辑：为 worker tool calls 收窄 `ToolName` 类型，为 router 注入 `buildRouterTools`、`isRouterToolName` 和 `createId`。

## 已经迁出的职责

- Chat API 入口：`agent/src/domains/chat/handlers.ts`
- Chat service：`agent/src/domains/chat/chat-service.ts`
- Router service：`agent/src/domains/chat/router-service.ts`
- Worker runner：`agent/src/domains/chat/worker-runner.ts`
- Router runtime supplement / rule match prompt：`agent/src/domains/chat/router-prompts.ts`
- Router tool schema / descriptions：`agent/src/domains/chat/router-tools.ts`
- Router tool validation / clarification prompts：`agent/src/domains/chat/router-tool-validation.ts`
- Omni KB context prompt：`agent/src/domains/chat/omni-kb-context.ts`
- Driver / vehicle expert prompt：`agent/src/domains/chat/vehicle-expert-prompts.ts`
- Chat history / tool summary context helpers：`agent/src/domains/chat/context.ts`
- Structured report runtime config：`agent/src/domains/chat/structured-report-runtime.ts`
- Structured lookup：`agent/src/domains/chat/structured-lookup.ts`
- Research API handler / service：`agent/src/domains/research/*`
- Rules API handler：`agent/src/domains/rules/handlers.ts`
- Rules repository：`agent/src/domains/rules/repository.ts`
- Rules match / embedding service：`agent/src/domains/rules/match-service.ts`
- Rule test service：`agent/src/domains/rules/rule-test-service.ts`
- Rule tool adapter：`agent/src/domains/rules/tool-adapter.ts`
- Rule config HTTP handler / service / draft repository：`agent/src/domains/rules/rule-config/*`
- Scenarios API handler / repository / match service：`agent/src/domains/scenarios/*`
- Sessions API handler：`agent/src/domains/sessions/handlers.ts`
- Sessions repository：`agent/src/domains/sessions/repository.ts`
- Sessions title service：`agent/src/domains/sessions/title-service.ts`
- Sessions routing context：`agent/src/domains/sessions/routing-context.ts`
- AB test adapter / service / metadata / types：`agent/src/domains/ab-test/*`
- ToolProvider / scoped / MCP / hybrid provider：`agent/src/tools/provider.ts`
- `query_data` tool executor：`agent/src/tools/query-data.ts`
- `query_kb` tool client：`agent/src/infra/kb-query-tool.ts`
- KB HTTP proxy：`agent/src/infra/kb-proxy.ts`
- OpenAI chat/router/stream wrappers：`agent/src/infra/llm/chat-completions.ts`
- HTTP/API router：`agent/src/app/http-router.ts`
- SSE 文本传输 helper：`agent/src/infra/http/sse.ts`
- Auth session store / auth context resolve：`agent/src/infra/auth/session-store.ts`
- Cookie helpers / response cookie append：`agent/src/infra/auth/cookies.ts`
- HTTP response / CORS / shared MCP / shared text/json/guard helpers：`agent/src/infra/*`、`agent/src/shared/*`

## 当前仍留在 `runtime.ts` 的部分

| 区块 | 说明 |
| --- | --- |
| imports / 类型 / 常量 / skill wiring | 组合根基础区，包含 env/type、worker skill map、router allow list、模型与阈值常量 |
| `createToolProvider` 注入包装 | 把 `query_data`、rules adapter、`query_kb`、MCP client 注入 tool provider |
| rule-config 开关 + `executeRuleTest` 包装 | 状态机开关、调用 `rule-test-service` 的薄包装 |
| rule routing precompute + worker helper predicates | rule reply 参数提取、match 预计算、OpenAI tool schema adapter、router tool name 判断 |
| Worker fetch 入口 | Cloudflare Worker `fetch` export |
| service composition root | worker runner、AB adapter、session repository/title、router、rule config、chat service、HTTP router 接线 |
| 基础小工具 | `createId` |

## 下一步建议

1. 保留 service composition root

   组合根现在仍有存在价值。除非要引入依赖注入工厂或测试专用 bootstrap，否则不建议继续把它拆散。

2. 可选：继续细拆 `http-router.ts`

   如果后续还要压缩 HTTP router，可以优先把 auth login/logout/me 拆成 `infra/auth/http-handlers.ts`，再把 research/rules/sessions/chat dispatch 表驱动化。

3. 如果生产环境确定不要 `query_data`

   优先移除：
   - `agent/src/tools/query-data.ts`
   - `createToolProvider` 中的 `executeQueryData`
   - worker runner 依赖中的 `QUERY_DATA_READ_ACTIONS`、`normalizeQueryDataAction`、`hasQueryDataHit`、`buildQueryDataSignature`、`isReadNoHitResult`、`isNotFoundLikeError`
   - ToolProvider 中 `query_data` 的 schema / executor 分支

## 验证

- `npx tsc --noEmit`
- `npm run check:text`
