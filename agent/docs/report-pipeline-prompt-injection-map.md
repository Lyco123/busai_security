# 报告管线：提示词注入位置对应说明

更新时间：2026-06-09
适用代码：`agent/src/domains/chat/*`、`agent/src/app/runtime.ts`、`agent/skills/*`

本文说明当前 Agent 中哪些文本会进入 Router / Worker 的模型上下文，哪些机制虽然改变链路但不是提示词注入。重点用于定位“改了某段提示词后，影响的是路由、报告成品、咨询回答，还是只是短路/门控行为”。

## 一、总览

当前报告相关链路分三层：

1. **Chat Service**：创建会话 run、保存用户消息、生成 pre-router opening、尝试规则配置流程，然后进入 Router。
2. **Router**：匹配规则和工作场景，处理结构化报告短路、澄清恢复、最近报告追问，再选择 `generate_*_report` / `consult_*` / `rule_reply` / `request_further_info`。
3. **Worker**：加载对应 Skill 和运行时护栏，调用可用数据工具或使用预取 `report_source`，生成结构化 JSON 或咨询 Markdown。

结构化报告工具当前包括：

- `generate_driver_report`
- `generate_vehicle_report`
- `generate_unit_report`
- `generate_route_report`
- `generate_station_report`
- `generate_accident_investigation_report`

咨询专家当前包括：

- `consult_omni`
- `consult_driver_expert`
- `consult_vehicle_expert`
- `consult_unit_expert`
- `consult_route_expert`
- `consult_station_expert`
- `consult_incident_expert`

## 二、Router 注入点

### 1. Router system 主体

Router 的主 system message 在 `agent/src/domains/chat/router-service.ts` 中拼装，主要由以下部分组成：

| 注入内容 | 位置 | 作用 |
| --- | --- | --- |
| 当前服务器时间 | `server-time-context.ts` → `buildServerTimeSystemPrompt()` | 给 Router 提供“今天/当前时间”的解释边界 |
| Router Skill 正文 | `src/app/runtime.ts` 引入 `skills/router/SKILL.md`，通过 `getRouterSkill()` 传入 | 路由策略、工具边界、澄清/报告/咨询分流主规则 |
| 澄清工具说明 | `router-service.ts` 内联 `CLARIFICATION TOOL:` 段落 | 约束何时先写用户可见澄清、何时调用 `request_further_info`，以及 `resume_tool` / `resume_mode` 的含义 |
| 待补充状态 | `router-service.ts` → `renderPendingFurtherInfoPrompt()` | 注入 `PENDING FURTHER INFO CONTEXT`，用于恢复上一轮缺参/消歧流程，或判断用户已换话题 |
| 最近结构化报告上下文 | `router-service.ts` → `renderLatestStructuredReportPrompt()` | 注入 `LATEST STRUCTURED REPORT CONTEXT`，区分“报告追问走咨询专家”和“明确重生成走 generate” |
| 规则匹配结果 | `router-prompts.ts` → `renderRuleMatchForPrompt()` | 注入 `[RULE_MATCH_RESULTS]` 和 `[RULE_ROUTING_POLICY]`，影响是否允许/选择 `rule_reply` |
| 对话历史 | `context.ts` → `buildContextFromHistory()` | 影响指代消解、多轮延续、报告追问和澄清恢复 |
| 当前用户句 | `router-service.ts` 最后追加 `role: user` | 当前轮最终路由依据 |

拼装形态是单条 Router system message + 历史消息 + 当前用户消息。Router 模型调用在 `callOpenAIRouter()`，默认温度 `0.2`。

### 2. Router 工具 description

Router 的 Function Calling schema 在 `agent/src/domains/chat/router-tools.ts`。

这些 `description` 和 `parameters` 是强注入面，直接影响模型选择哪个工具：

- `generate_*_report` 使用统一 `REPORT_BOUNDARY`：只用于用户明确索取唯一对象的正式报告、画像报告或风险总结。
- `consult_*_expert` 使用统一 `CONSULT_MODE`：`direct` 用于简单事实/单点解释，`deep` 用于复杂归因、趋势对比、管理建议或报告追问。
- `generate_station_report`、`consult_station_expert` 已纳入主路由工具。
- `rule_reply` 只允许使用当前轮规则匹配结果里的 `rule_id`。
- `request_further_info` 用于持久化可恢复澄清状态，不承载用户可见澄清正文。

注意：`router-tools.ts` 注释说明当前工具描述有意保持紧凑；如果路由召回变化，先看 `agent/docs/router-optimization-20260518.md`，不要随意扩写。

### 3. Command Router 补充注入

`router-service.ts` 支持 `useCommandRouter`，主要用于 pipeline probe。第一轮可用命令式 Router：

- 追加 `buildCommandRouterInstruction(routerToolAllowList)` 到 Router system。
- 由 `callOpenAICommandRouter()` 输出命令文本。
- `parseCommandRouterToolCall()` 能解析时直接转为 tool call；解析失败回退普通 Function Router。

主业务 `/chat` 默认仍走 Function Router；probe 链路可开启 command router。

### 4. Router 纠错注入

Router 多轮最多 `MAX_ROUTER_TOOL_ITERATIONS = 3`。以下失败会以 `role: tool` 消息写回 Router，相当于注入一轮纠错提示：

| 场景 | 位置 | 影响 |
| --- | --- | --- |
| Router 调 `match_rules` | `router-service.ts` | 把预计算 `ruleMatchContext.toolResult` 写回模型，允许继续重选 |
| `rule_reply` 使用非当前命中规则 | `router-service.ts` | 写回 `rule_reply requires a rule_id...`，要求改选工具 |
| `rule_reply` 命中本轮被 `rule_exit` 屏蔽的规则 | `router-service.ts` | 写回 blocked rule 信息，避免重复进入同一规则 |
| 参数校验失败且 `retry_router` | `router-tool-validation.ts` + `router-service.ts` | 把校验文案作为 tool failure 写回，促使补参或换工具 |

参数校验失败但需要问用户时，不再重试 Router，而是直接返回用户可见澄清，并在 metadata 中写入 `pending_further_info`。

## 三、非提示词注入但会改变 Router 结果的机制

| 机制 | 位置 | 说明 |
| --- | --- | --- |
| 规则匹配预计算 | `runtime.ts` → `precomputeRuleMatchContext()` | Router 前先跑规则向量匹配，结果进入提示词；无规则命中时 `rule_reply` 会从 allow list 过滤掉 |
| 工作场景门控 | `router-service.ts` → `listWorkScenarios()` / `matchWorkScenarioService()` | 无场景或无候选时直接返回，不进入 Router LLM |
| 结构化报告短路 | `structured-lookup.ts` → `extractStructuredReportToolCall()`；`router-service.ts` 中各 `handle*ReportResolution()` | 对内部编码的报告请求或部分可直接解析请求，跳过常规 Router 选择，直接做 lookup + Worker |
| 实体别名解析 | `entity-alias-resolver.ts`；`router-service.ts` | 单位、线路会把别名映射到标准名，并把 alias hint 拼入 Worker prompt |
| 车牌归一化 | `vehicle-plate-normalizer.ts` | `generate_vehicle_report` 参数在执行前会归一化，不是模型提示词 |
| 报告专用模型环境 | `chat-service.ts` → `buildReportEnvOverride()` | `OPENAI_REPORT_BASE_URL` / `OPENAI_REPORT_API_KEY` / `OPENAI_REPORT_MODEL` 可覆盖报告 Worker 模型环境 |
| 输出格式化 | `output-formatter.ts` | 结构化 JSON 可按 `OUTPUT_FORMAT` 转 Markdown 展示，不改变模型生成时看到的提示词 |

## 四、结构化报告短路与预取模式

报告类工具在 Router 选中后，通常不是直接把 `buildWorkerPrompt()` 交给 Worker，而是先走解析/查源：

| 报告 | 解析/查源函数 | 成功后 Worker 模式 |
| --- | --- | --- |
| 驾驶员 | `resolveDriverLookup()` | `buildStructuredReportPrefetchedPrompt()` + `prefetchedSourceData` |
| 车辆 | `resolveVehicleLookup()` | `buildStructuredReportPrefetchedPrompt()` + `prefetchedSourceData` |
| 单位 | `resolveUnitLookup()` + `resolveUnitAlias()` | alias hint + `buildStructuredReportPrefetchedPrompt()` + `prefetchedSourceData` |
| 线路 | `resolveRouteLookup()` + `resolveRouteAlias()` | alias hint + `buildStructuredReportPrefetchedPrompt()` + `prefetchedSourceData` |
| 站场 | `resolveStationLookup()` | `buildStructuredReportPrefetchedPrompt()` + `prefetchedSourceData` |
| 事故 | `resolveIncidentLookup()` | `buildStructuredReportPrefetchedPrompt()` + `prefetchedSourceData` |

预取成功后 Worker 使用空 allow list 的 scoped provider，并设置 `prefetchedSourceData`。这会触发 Worker system 中的 `PREFETCHED REPORT MODE` 护栏：

- 当前轮已有完整 `report_source`
- 直接基于 `report_source` 输出最终结构化 JSON
- 禁止调用、模拟或重新解析工具
- 最终答案必须是单个 JSON object

预取失败或多候选时，`runStructuredLookupClarification()` 会调用一个“受控错误回复器”Router LLM，把结构化错误上下文改写成简短用户回复。这个错误回复器也有独立 system prompt，明确禁止调用工具、禁止生成报告、禁止泄露内部实现。

## 五、Worker 注入点

### 1. Worker system 主体

Worker system 在 `agent/src/domains/chat/worker-runner.ts` 中拼装：

| 注入内容 | 位置 | 作用 |
| --- | --- | --- |
| 当前服务器时间 | `server-time-context.ts` | 给 Worker 解释相对时间 |
| 可选 runtime prefix | `runtimeOptions.systemPromptPrefix` | deep COT / A-B 实验 / 专家注册表注入 |
| Worker Skill 正文 | `runtime.ts` → `WORKER_SKILLS` | 每个工具的主模板和行为规则 |
| 预取报告护栏 | `worker-runner.ts` → `prefetchedSourceGuardrail` | 禁止预取模式再调工具 |
| 对话可见输出护栏 | `worker-runner.ts` → `buildConversationalVisibleOutputGuardrail()` | 约束咨询类最终输出 |
| 可用工具护栏 | `worker-runner.ts` → `toolAvailabilityGuardrail` | 明确只能基于当前列出的工具回答，禁止虚构 MCP/工具/结果 |
| 字段对齐护栏 | `worker-runner.ts` → `fieldAlignmentGuardrail` | 要求 ID/编号/标准名补查和字段口径对齐 |
| 风险分语义护栏 | `worker-runner.ts` → `riskScoreSemanticsGuardrail` | 明确风险分越高风险越高 |
| 澄清工具护栏 | `worker-runner.ts` → `clarificationGuardrail` | 与 Router 的 `request_further_info` 使用方式对齐 |

然后追加历史消息和当前 Worker user prompt。

### 2. Worker Skill 来源

`runtime.ts` 的 `WORKER_SKILLS` 当前包括：

| Worker | Skill |
| --- | --- |
| `generate_driver_report` | `skills/structured/generate_driver_report/SKILL.md` |
| `generate_vehicle_report` | `skills/structured/generate_vehicle_report/SKILL.md` |
| `generate_unit_report` | `skills/structured/generate_unit_report/SKILL.md` |
| `generate_route_report` | `skills/structured/generate_route_report/SKILL.md` |
| `generate_station_report` | `skills/structured/generate_station_report/SKILL.md` |
| `generate_accident_investigation_report` | `skills/structured/generate_accident_investigation_report/SKILL.md` |
| `consult_omni` | `skills/conversational/omni/SKILL.md` |
| `consult_driver_expert` | `skills/conversational/driver_expert/SKILL.md` |
| `consult_vehicle_expert` | `skills/conversational/vehicle_expert/SKILL.md` |
| `consult_unit_expert` | `skills/conversational/unit_expert/SKILL.md` |
| `consult_route_expert` | `skills/conversational/route_expert/SKILL.md` |
| `consult_station_expert` | `skills/conversational/station_expert/SKILL.md` |
| `consult_incident_expert` | `skills/conversational/incident_expert/SKILL.md` |
| `rule_reply` | `skills/conversational/rule_reply/SKILL.md` |
| `rule_asker` | `skills/conversational/rule_asker/SKILL.md` |
| `rule_builder` | `skills/structured/rule_builder/SKILL.md` |

### 3. Worker user prompt 来源

`buildWorkerPrompt()` 负责把 Router tool call 转成 Worker user message。

结构化报告优先使用 `structured-report-data-sources.ts` 中的 `buildUnresolvedPrompt()`；预取成功时使用 `buildStructuredReportPrefetchedPrompt()`，其中包含 `report_source` JSON。

咨询类工具将 `query`、`context` 等参数拼成自然语言任务。单位/线路专家会额外注入 alias hint。

### 4. 报告数据源工具注入

`structured-report-data-sources.ts` 定义报告专用数据源工具：

| 报告 Worker | 报告源工具 |
| --- | --- |
| `generate_driver_report` | `get_driver_report_source` |
| `generate_vehicle_report` | `get_vehicle_report_source` |
| `generate_unit_report` | `get_unit_report_source` |
| `generate_route_report` | `get_route_report_source` |
| `generate_station_report` | `get_station_report_source` |
| `generate_accident_investigation_report` | `get_accident_report_source` |

这些工具通过 `router-service.ts` 的 `createStructuredReportToolProvider()` 包装为 scoped provider。Worker 只看到当前报告允许的 report source tool，而不是完整 MCP 列表。

普通咨询类 Worker 使用 `createToolProvider()`，它可能是 local / MCP / hybrid，并会在 metadata 中记录 `tool_provider_mode`、`available_tool_names`、`mcp_*`、`kb_*` 等信息。

### 5. 结构化报告运行时纠错

`structured-report-runtime.ts` 为每个结构化报告配置：

- `reportType`
- `noDataError`
- `formatMismatchError`
- `missingDataRetryLimit`，当前均为 2
- `maxDataToolCallsWithoutHit`，线路/站场/事故为 4，驾驶员/车辆/单位不限
- normalize 函数
- 完整性检查函数
- 模板 marker 检查函数

Worker 执行时有这些注入/终止点：

| 场景 | 行为 |
| --- | --- |
| 结构化报告未预取且未调数据工具 | 追加 `buildStructuredReportMissingDataPrompt(..., 'missing_read_call')` system message 后重试 |
| 数据工具调用失败 | 追加 `read_failed` system message 后重试 |
| 数据工具成功但无有效命中 | 追加 `no_data_hit` system message 后重试 |
| 超过缺数据重试上限 | 返回 `buildStructuredReportNoDataError()` 的 error JSON |
| JSON 解析失败或归一化后不完整 | 返回 `buildStructuredReportFormatMismatchError()` 的 error JSON |
| 达到无命中工具调用上限 | 返回 no-data error JSON |

## 六、Opening / Progress / Closing 注入

`worker-runner.ts` 现在有三类辅助自然语言阶段：

| 阶段 | 位置 | 说明 |
| --- | --- | --- |
| pre-router opening | `generatePreRouterOpening()`，由 `chat-service.ts` 在进入规则配置/Router 前调用 | 给用户先流一小段“正在处理”类开场；最终回答中会注入一条 assistant 历史提示，要求不要重复前言 |
| worker opening | `buildOpeningStepPrompt()` | 如果未被 `suppressOpeningText` 禁用，Worker 主流程前生成简短开场 |
| progress | `buildProgressStepPrompt()` | 流式模式下，预取数据或首次有效外部数据命中后发 `progress` 事件 |
| closing | `buildClosingStepPrompt()` | 部分工具最终内容后生成一句收尾；结构化 error JSON 不生成 closing |

`/chat` 和 `/chat/stream` 默认会先生成 pre-router opening，并把后续 Router 的 opening 禁用；pipeline probe 可通过参数控制。

## 七、专家 deep COT / Thinking

专家 deep COT 的 system prefix 来源：

- `consult_driver_expert`、`consult_vehicle_expert`：优先走 `ab-test/adapter.ts`，可能注入 `DRIVER_EXPERT_COT_SYSTEM_PROMPT` / `VEHICLE_EXPERT_COT_SYSTEM_PROMPT`。
- 其他专家：走 `experts/registry.ts`，当 `cot_mode=deep` 且注册项支持 deep COT 时注入 `deepCotSystemPrompt`。

另外，`worker-runner.ts` 会在专家 Worker 且 `OPENAI_EXPERT_THINKING_ENABLED` 启用时，把 `enableThinking` 传给 OpenAI wrapper。这是模型参数，不是文本提示词。

## 八、输出展示层

模型生成结构化报告时仍要求 JSON。最终给前端/用户看的内容由 `output-formatter.ts` 决定：

- `OUTPUT_FORMAT=json`：原样返回 JSON。
- 默认 `markdown`：结构化报告 JSON 转 Markdown；error JSON 转错误说明。

因此“前端看到 Markdown”不代表 Worker 没有按 JSON 生成。

## 九、快速定位

| 问题现象 | 优先检查 |
| --- | --- |
| 报告 vs 咨询分流错 | `router-tools.ts` 的工具 description、`skills/router/SKILL.md`、`LATEST STRUCTURED REPORT CONTEXT` |
| 报告追问被重生成 | `renderLatestStructuredReportPrompt()`、对应 `consult_*_expert` description |
| 需要澄清但直接执行 | `router-tool-validation.ts`、`CLARIFICATION TOOL`、`pending_further_info` metadata |
| 结构化报告没调数据工具 | `structured-report-data-sources.ts`、`prefetchedSourceGuardrail`、`requireDataQueryBeforeReply` |
| 报告有数据但输出 error JSON | `structured-report-runtime.ts` 的完整性/marker 检查和对应 normalizer |
| 站场报告/站场咨询异常 | `generate_station_report` / `consult_station_expert` 的 Router 工具、`station-report-normalizer.ts`、站场 MCP wrapper |
| 咨询类乱说工具或数据 | `toolAvailabilityGuardrail`、`fieldAlignmentGuardrail`、实际 `available_tool_names` metadata |
| 流式阶段文案重复 | pre-router opening、worker opening、`suppressOpeningText`、closing prompt |
