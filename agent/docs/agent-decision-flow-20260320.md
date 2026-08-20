# Agent 当前决策链路说明

更新时间：2026-06-09
适用代码：`agent/src/app/runtime.ts`、`agent/src/domains/chat/*`

本文描述当前代码下，Agent 从 `/chat` 或 `/chat/stream` 请求进入，到 session run、pre-router opening、规则配置、Router、Worker、Tool Provider，再到最终消息落库与前端展示的实际执行链路。

这份文档是代码行为说明，不是产品设计稿。用途是排障、回归和定位“到底是哪一层改变了结果”。

## 1. 总体链路

当前链路可以拆成 9 层：

1. HTTP/API 入口层
2. Chat Service / Session Run 队列层
3. Pre-router opening 阶段
4. Rule Config 流程优先层
5. Router 前置门控与上下文准备层
6. Structured Lookup / Direct Tool Call 短路层
7. Router LLM 决策层
8. Worker 执行层
9. Tool Provider / MCP / KB / Local Tool 数据层与输出格式化层

最常见的非流式顺序：

`/chat` -> `handleChat` -> 创建 queued run -> wait/start run -> 保存 user message -> pre-router opening -> tryHandleRuleConfig -> routeRequest -> runWorkerWithTools -> formatStructuredOutput -> 保存 assistant message -> session title 异步生成`

最常见的流式顺序：

`/chat/stream` -> 创建 queued run -> SSE start -> 保存 user message -> pre-router opening delta -> tryHandleRuleConfig 或 routeRequest -> Router/Worker 阶段事件与 delta/progress/tool events -> formatStructuredOutput -> 保存 assistant message -> SSE final -> [DONE]`

并不是所有请求都会进入 Router LLM。当前主要短路包括：

- Rule Config 当前会话正在配置规则
- Direct structured report tool call
- 结构化报告 lookup 已能直接解析并预取数据
- 结构化 lookup 失败后直接走受控澄清回复
- Work Scenario 无配置或无候选时直接返回
- Router 无 tool call 时 fallback 到 `consult_omni`

## 2. HTTP/API 入口

入口由 `agent/src/app/http-router.ts` 接管，`runtime.ts` 只作为 Cloudflare Worker composition root。

Chat 相关 handler 位于 `agent/src/domains/chat/handlers.ts`，核心业务在 `chat-service.ts`。

主要入口：

- `POST /chat`
- `POST /chat/stream`
- pipeline/direct probe 入口
- report summary 入口

`runtime.ts` 负责装配：

- `createChatService()`
- `createRouteRequestHandler()`
- `createWorkerRunner()`
- `createToolProvider()`
- 规则、场景、session、research 等服务依赖

## 3. Session Run 队列

`chat-service.ts` 使用 `session-run-repository.ts` 为同一会话创建 run 队列。

关键行为：

1. `createQueuedRun()` 创建 run，模式为 `chat` 或 `stream`。
2. `waitForRunStart()` 轮询获取 run lease。
3. lease 时间 `RUN_LEASE_MS = 15 * 60 * 1000`。
4. 获取 run 超时 `RUN_ACQUIRE_TIMEOUT_MS = 110 * 1000`。
5. 如果 run 不再 active，返回 inactive run reply 或抛错。
6. 成功完成后 `completeRun()`，失败后 `failRun()`。

这层用于串行化同一 session 的请求，避免多轮并发互相污染历史和 pending 状态。

## 4. Chat Service 会话层

核心文件：`agent/src/domains/chat/chat-service.ts`

非流式 `executeChatTurn()` 的主要步骤：

1. 保存用户消息。
2. 更新 session preview。
3. 创建 `turnContext`。
4. 调用 `generatePreRouterOpening()` 生成短开场。
5. 调用 `tryHandleRuleConfig()`。
6. 若规则配置未接管，调用 `routeRequest()`。
7. 合并 leading/base/trailing content。
8. 使用 `formatStructuredOutput()` 格式化结构化报告展示内容。
9. 保存 assistant message。
10. 更新 session preview。
11. 异步触发 session title 生成。

流式 `handleChatStream()` 的差异：

- 通过 SSE 发送 `start`、`delta`、`progress`、agent tool events、`final`、`error`、`[DONE]`。
- pre-router opening 和 Worker 主回答都可向前端推 delta。
- Worker 工具事件会透传为 `tool_call_delta`、`tool_call_ready`、`tool_execution_started`、`tool_execution_completed`、`tool_execution_failed`。

## 5. Pre-router Opening

`generatePreRouterOpening()` 位于 `worker-runner.ts`，由 Chat Service 在进入 Rule Config 或 Router 前调用。

作用：

- 在慢链路前给用户先展示一句简短处理状态。
- 该阶段不决定工具、不查询业务数据。
- 生成成功后 metadata 写入 `opening_emitted_at` 和 `opening_stage: pre_router`。

后续调用 `routeRequest()` 时通常传 `suppressOpeningText: true`，避免 Worker 再生成重复 opening。

## 6. Rule Config 优先层

Chat Service 在进入 Router 前先调用：

- `tryHandleRuleConfig(env, sessionId, content, isStream, historyMessages)`

如果当前 session 正在规则配置流程中，这一层会直接接管，不进入 Router LLM。

相关 Worker / Skill：

- `rule_asker`
- `rule_builder`
- `rule_reply`

`rule_asker` 在 Worker 层有强制要求：每轮回复前必须先调用 `get_rule_draft` 和 `update_rule_draft`，即使没有改动也要 `noop: true`。

## 7. Router 前置准备

核心文件：`agent/src/domains/chat/router-service.ts`

`routeRequest()` 进入后先做这些事：

1. 合并流式回调和 suppress 选项为 `sharedRuntimeOptions`。
2. 预计算规则匹配：`precomputeRuleMatchContext()`。
3. 渲染规则提示：`renderRuleMatchForPrompt()`。
4. 读取 work scenarios：`listWorkScenarios()`。
5. 场景匹配：`matchWorkScenarioService()`。
6. 读取最近 assistant routing context：`getLatestAssistantRoutingContext()`。
7. 提取 pending further info、最近结构化报告成功/失败 source。
8. 尝试解析 direct structured tool call。

如果无 work scenario 配置，直接返回：

- `No work scenarios configured yet; cannot process this request.`

如果没有候选场景，直接返回：

- `No available work scenario candidates at this time.`

这两个返回不经过 Router LLM。

## 8. 规则匹配与 rule_reply

规则匹配由 `runtime.ts` 的 `precomputeRuleMatchContext()` 调用 `executeMatchRulesService()`。

当前参数：

- `RULE_MATCH_TOP_K = 5`
- `RULE_MATCH_MIN_SCORE = 0.3`
- `RULE_MATCH_THRESHOLD = 0.7`

规则匹配结果会：

- 进入 Router system prompt 的 `[RULE_MATCH_RESULTS]`
- 写入 metadata 的 `rule_match`
- 在无命中时从 Router allow list 移除 `rule_reply`
- 为 work scenario match 复用 query embedding

Router 选择 `rule_reply` 后还会校验：

- `rule_id` 必须来自当前轮匹配结果。
- 如果上一次 `rule_reply` 触发 `rule_exit`，同一轮会把该 rule id 加入 blockedRuleId，避免重复进入。

如果 `rule_reply` Worker 返回 `metadata.rule_exit`，Router 会把 `rule_exit_triggered` 作为 tool failure 写回 Router 消息，继续重选工具。

## 9. Structured Lookup / Direct Tool Call

结构化报告工具当前包括：

- `generate_driver_report`
- `generate_vehicle_report`
- `generate_unit_report`
- `generate_route_report`
- `generate_station_report`
- `generate_accident_investigation_report`

Direct tool call 由 `structured-lookup.ts` 的 `extractStructuredReportToolCall()` 解析，常用于内部编码请求和 report summary。

Router 选中报告工具后，通常进入对应 resolution：

| 工具 | Resolution |
| --- | --- |
| `generate_driver_report` | `handleDriverReportResolution()` |
| `generate_vehicle_report` | `handleVehicleReportResolution()` |
| `generate_unit_report` | `handleUnitReportResolution()` |
| `generate_route_report` | `handleRouteReportResolution()` |
| `generate_station_report` | `handleStationReportResolution()` |
| `generate_accident_investigation_report` | `handleIncidentReportResolution()` |

成功解析并拿到画像/事故源数据时：

1. 构造 `buildStructuredReportPrefetchedPrompt()`。
2. 设置 `prefetchedSourceData`。
3. 使用空 allow list 的 scoped provider，禁止 Worker 再调工具。
4. 调用对应 `generate_*_report` Worker。
5. metadata 写入 `*_lookup`、`scenario.shortcut=true`、`rule_match`。

解析失败、多候选或缺参时：

1. 构造 lookup metadata 和 `pending_further_info`。
2. 调用 `runStructuredLookupClarification()`。
3. 该函数使用受控错误回复器 LLM，生成简短用户回复，不继续生成报告。

单位和线路 resolution 会额外做别名解析：

- `resolveUnitAlias()` / `resolveUnitAliasInText()`
- `resolveRouteAlias()` / `resolveRouteAliasInText()`
- `applyEntityAliasHintToPrompt()`

车辆报告会做车牌归一化：

- `normalizeVehiclePlateArg()`

## 10. Router LLM 决策层

如果前置短路没有接管，Router 会构造消息：

1. system：服务器时间 + Router Skill + 澄清说明 + pending further info + latest structured report context + rule match prompt
2. history：`buildContextFromHistory(historyMessages)`
3. user：当前用户输入

Router allow list 来自 `ROUTER_TOOL_ALLOW_LIST`：

- `generate_driver_report`
- `generate_vehicle_report`
- `generate_unit_report`
- `generate_route_report`
- `generate_station_report`
- `generate_accident_investigation_report`
- `consult_omni`
- `consult_driver_expert`
- `consult_vehicle_expert`
- `consult_unit_expert`
- `consult_route_expert`
- `consult_station_expert`
- `consult_incident_expert`
- `rule_reply`
- `request_further_info`

如果规则匹配无命中，`rule_reply` 会从 allow list 中移除。

Router 迭代上限：

- `MAX_ROUTER_TOOL_ITERATIONS = 3`

Router 输出处理：

- 无 tool call：fallback 到 `consult_omni`。
- `match_rules`：写回预计算规则结果并继续。
- `request_further_info`：保存 pending state，返回用户可见澄清。
- 非 routable tool：返回 `Blocked tool call.`。
- 参数校验失败：根据 `router-tool-validation.ts` 决定重试 Router 或直接澄清用户。
- 报告工具：进入 structured lookup / prefetched report。
- 咨询工具：进入对应专家 Worker。
- 规则工具：进入 `rule_reply` / rule flow。

## 11. Command Router Probe

pipeline probe 可启用 command router：

- `handlePipelineStreamProbe()` 中 `useCommandRouter: options.routerMode !== 'function'`
- Router 第一轮追加 `buildCommandRouterInstruction()`
- 调用 `callOpenAICommandRouter()`
- `parseCommandRouterToolCall()` 成功则转为 tool call
- 失败则 fallback 到 Function Router

这是诊断/探针链路，不是主 `/chat` 默认路径。

## 12. Worker 执行层

核心文件：`agent/src/domains/chat/worker-runner.ts`

`runWorkerWithTools()` 的主要步骤：

1. 获取 Tool Provider：传入的 scoped provider 或默认 `createToolProvider(env)`。
2. 判断是否为结构化预取模式：结构化报告 + `prefetchedSourceData`。
3. 预取模式下不列工具；否则 `provider.listTools()`。
4. 构造 Worker system：服务器时间 + runtime prefix + Skill + 各类护栏。
5. 追加历史消息和当前 Worker user prompt。
6. 可选生成 worker opening。
7. 循环调用模型和工具，最多 `MAX_TOOL_ITERATIONS = 5`。
8. 结构化报告做数据调用检查、JSON 解析、normalize、完整性检查。
9. 可选生成 closing。
10. 返回 content、metadata、sources、leadingContent、trailingContent。

Worker 模型选择：

- 默认 `OPENAI_WORKER_MODEL || OPENAI_MODEL || DEFAULT_MODEL`
- `DEFAULT_MODEL = gpt-4o-mini`
- 报告 summary 或报告链路可通过 `OPENAI_REPORT_BASE_URL` / `OPENAI_REPORT_API_KEY` / `OPENAI_REPORT_MODEL` 覆盖环境

专家 Worker 在 `OPENAI_EXPERT_THINKING_ENABLED` 开启时会传 `enableThinking`。

## 13. Worker Skill 与工具类型

`runtime.ts` 的 `WORKER_SKILLS` 当前包括：

- 结构化报告：驾驶员、车辆、单位、线路、站场、事故调查
- 咨询专家：omni、驾驶员、车辆、单位、线路、站场、事故
- 规则：`rule_reply`、`rule_asker`、`rule_builder`

结构化报告 Worker：

- 默认要求调报告源工具取真实数据。
- 如果已有 `prefetchedSourceData`，禁用工具调用。
- 最终输出必须是结构化 JSON。

咨询 Worker：

- 可流式调用工具。
- 会看到当前可用工具列表和工具使用护栏。
- 最终输出自然语言 Markdown。

## 14. Tool Provider / MCP / KB

`runtime.ts` 的 `createToolProvider()` 调用 `tools/provider.ts`，注入：

- rule tools：`get_rule`、`get_rule_draft`、`update_rule_draft`、`submit_rule_turn`、`rule_exit`
- pending 工具：`request_further_info`
- KB 工具：`executeQueryKb`
- MCP client：`listMcpToolsForAgent()`、`callMcpToolForAgent()`

Provider 可能是：

- `local`
- `mcp`
- `hybrid`
- `scoped`

Worker metadata 会记录：

- `tool_provider_mode`
- `available_tool_names`
- `mcp_configured`
- `mcp_visible`
- `mcp_tool_names`
- `tool_provider_allow_list`
- `kb_tool_enabled`
- `kb_api_configured`
- `kb_default_id`

结构化报告常用 scoped provider，只暴露当前报告允许的 `get_*_report_source` 工具。

## 15. 结构化报告运行时

核心文件：

- `structured-report-data-sources.ts`
- `structured-report-runtime.ts`
- 各 normalizer：`driver-report-normalizer.ts`、`vehicle-report-normalizer.ts`、`unit-report-normalizer.ts`、`route-report-normalizer.ts`、`station-report-normalizer.ts`、`structured-report-normalizers.ts`

报告源工具：

- `get_driver_report_source`
- `get_vehicle_report_source`
- `get_unit_report_source`
- `get_route_report_source`
- `get_station_report_source`
- `get_accident_report_source`

结构化报告 runtime config 当前统一：

- 缺数据重试上限：2
- 线路/站场/事故无命中工具调用上限：4
- 归一化后必须通过完整性检查和模板 marker 检查

失败返回：

- no data error JSON
- format mismatch error JSON

这些 error JSON 之后可能被 `output-formatter.ts` 转成用户可见 Markdown 错误说明。

## 16. 输出格式化与落库

Worker 返回后，Chat Service 会调用：

- `formatStructuredOutput(content, metadata, env)`

行为：

- `OUTPUT_FORMAT=json`：结构化报告原样 JSON。
- 默认 `markdown`：结构化报告 JSON 转 Markdown。
- error JSON 转为错误说明。
- 非结构化报告不处理。

随后保存 assistant message：

- `content`
- `sources`
- `metadata`
- `tools`
- `status`

并更新 session preview。

## 17. Report Summary 入口

`chat-service.ts` 的 `handleReportSummary()` 会：

1. 根据 payload 构造内部 structured report tool call。
2. 使用 `encodeInternalWorkerToolCall()`。
3. 调用 `routeRequest()`，传 `suppressStageText: true` 和 `reportEnvOverride`。
4. 格式化结构化输出。

这条链路主要用于直接生成报告摘要，不走普通聊天历史。

## 18. Probe 链路

当前有两类 probe：

- `handleDirectStreamProbe()`：直接打开底层 probe stream。
- `handlePipelineStreamProbe()`：完整跑 pre-router opening、routeRequest、Router/Worker，并输出 `probe_stage`。

Pipeline probe 可选择 command/function router，用于定位阶段耗时、首 token、工具事件和 fallback。

## 19. 常见定位口径

| 现象 | 重点看 |
| --- | --- |
| 为什么没进 Router | Rule Config、work scenario 门控、direct structured tool call、structured lookup shortcut |
| 为什么报告请求变咨询 | `router-tools.ts` 的 `REPORT_BOUNDARY`、Router Skill、latest report context |
| 为什么咨询追问又生成报告 | `renderLatestStructuredReportPrompt()`、`consult_*_expert` description、历史消息 |
| 为什么没有 rule_reply | 规则匹配是否成功、allow list 是否过滤、rule_id 是否在当前 matches 中 |
| 为什么报告没调 MCP | 是否 prefetched mode、scoped provider allow list、`prefetched_source_tools_disabled` metadata |
| 为什么报告有 JSON 但前端是 Markdown | `OUTPUT_FORMAT` 和 `output-formatter.ts` |
| 为什么流式有多段状态文案 | pre-router opening、progress、worker opening、closing、suppress flags |
| 为什么工具列表和实际 MCP 不一致 | `tool_provider_mode`、`mcp_configured`、`mcp_visible`、`available_tool_names` metadata |
