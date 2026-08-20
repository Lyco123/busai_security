# 非报告管线：提示词注入位置对应说明

更新时间：2026-06-09
适用代码：`agent/src/domains/chat/*`、`agent/src/domains/rules/*`、`agent/src/domains/experts/*`、`agent/skills/conversational/*`

本文说明当前 Agent 中 **除 `generate_*_report` 报告成品链路以外** 的提示词注入位置。范围包括通用咨询、专家咨询、规则回复、规则配置、知识库增强、工具护栏、澄清恢复、opening/progress/closing 等。

报告成品链路请看：`agent/docs/report-pipeline-prompt-injection-map.md`。

## 一、非报告链路范围

本文覆盖的 Worker 工具：

- `consult_omni`
- `consult_driver_expert`
- `consult_vehicle_expert`
- `consult_unit_expert`
- `consult_route_expert`
- `consult_station_expert`
- `consult_incident_expert`
- `rule_reply`
- `rule_asker`
- `rule_builder`

本文不覆盖报告成品 Worker：

- `generate_driver_report`
- `generate_vehicle_report`
- `generate_unit_report`
- `generate_route_report`
- `generate_station_report`
- `generate_accident_investigation_report`

但 Router 仍然会同时看到报告与非报告工具，因此非报告分流仍受 Router Skill、Router 工具描述、最近报告上下文等影响。

## 二、Router 侧注入点

Router system message 在 `agent/src/domains/chat/router-service.ts` 中拼装。非报告链路同样共享这些注入：

| 注入内容 | 位置 | 对非报告链路的影响 |
| --- | --- | --- |
| 当前服务器时间 | `server-time-context.ts` → `buildServerTimeSystemPrompt()` | 解释“今天/最近/本月”等相对时间 |
| Router Skill 正文 | `skills/router/SKILL.md`，由 `runtime.ts` 引入 | 决定咨询、规则、澄清、报告追问、换话题的主分流规则 |
| 澄清工具说明 | `router-service.ts` 内联 `CLARIFICATION TOOL:` | 约束 `request_further_info` 的使用方式 |
| 待补充状态 | `renderPendingFurtherInfoPrompt()` | 恢复上一轮缺参、消歧或判断用户换话题 |
| 最近结构化报告上下文 | `renderLatestStructuredReportPrompt()` | 影响“报告追问”是否转入 `consult_*_expert` |
| 规则匹配结果 | `router-prompts.ts` → `renderRuleMatchForPrompt()` | 影响是否选择 `rule_reply` |
| 对话历史 | `context.ts` → `buildContextFromHistory()` | 影响指代消解和多轮延续 |
| 当前用户句 | `role: user` | 当前轮最终路由依据 |

### Router 工具描述

`agent/src/domains/chat/router-tools.ts` 中的 description 是非报告分流的关键注入面：

| 工具 | 描述边界 |
| --- | --- |
| `consult_omni` | 通用咨询、跨主题总结、制度流程说明、车队级列表/统计/档案汇总，以及没有专门专家承接的非报告型问题 |
| `consult_driver_expert` | 驾驶员风险、画像、安全状态、指标成因、趋势、对比、整改建议或报告追问 |
| `consult_vehicle_expert` | 车辆风险、画像、健康/安全状态、异常原因、能耗、维保整改、运营判断、对比或报告追问 |
| `consult_unit_expert` | 单位风险、画像、安全状态、管理效果、趋势、下级风险来源、整改建议或报告追问 |
| `consult_route_expert` | 线路风险、画像、风险构成、黑点路段、运行特征、波动、管理动作、对比或报告追问 |
| `consult_station_expert` | 站场风险、画像、安全状态、交通/三防/消防风险、整改建议、管理闭环或报告追问 |
| `consult_incident_expert` | 单起事故经过、基础信息、证据、原因、责任性质、整改措施、处理进度或报告追问 |
| `rule_reply` | 执行当前轮已明确选定的已保存规则，必须提供当前规则匹配结果中的 `rule_id` |
| `request_further_info` | 持久化可恢复澄清状态，不承载用户可见澄清正文 |

所有专家咨询工具都有 `cot_mode`：

- `direct`：简单事实、基础信息、单点解释
- `deep`：复杂归因、趋势/对比、综合分析、管理建议或报告追问

### Router 纠错注入

Router 最多迭代 `MAX_ROUTER_TOOL_ITERATIONS = 3`。这些场景会以 tool failure 写回 Router：

- `match_rules`：把预计算规则结果写回。
- `rule_reply` 的 `rule_id` 不在当前命中规则中：要求改选工具。
- `rule_reply` 命中本轮被 `rule_exit` 屏蔽的规则：要求不要重复调用。
- `router-tool-validation.ts` 返回 `retry_router`：把参数校验文案作为 tool failure 写回。

如果 Router 没有调用任何工具，当前实现 fallback 到 `consult_omni`。

## 三、非提示词但影响非报告分流的机制

| 机制 | 位置 | 说明 |
| --- | --- | --- |
| 工作场景门控 | `router-service.ts` → `listWorkScenarios()` / `matchWorkScenarioService()` | 无场景或无候选时直接返回，不进入 Router LLM |
| 规则匹配预计算 | `runtime.ts` → `precomputeRuleMatchContext()` | 结果进入 Router prompt；无命中时 `rule_reply` 从 allow list 移除 |
| active rule / rule config 接管 | `chat-service.ts` → `tryHandleRuleConfig()` | 当前 session 在规则配置流程时，不进入 Router |
| `rule_exit` fallback | `router-service.ts` | `rule_reply` Worker 可通过 metadata 触发退出当前规则并回到 Router |
| 单位/线路别名提示 | `entity-alias-resolver.ts` + `applyEntityAliasHintToPrompt()` | 单位、线路专家咨询会收到 alias hint |
| KB gate | `omni-kb-context.ts` → `decideKbRetrieval()` | 根据政策/制度关键词决定是否检索并注入 KB 片段 |
| Tool Provider 可见性 | `tools/provider.ts` + Worker metadata | 当前可用工具列表会影响 Worker 行为，但工具是否存在由 provider 决定 |

## 四、Worker 通用 system 注入

非报告 Worker 的 system message 在 `worker-runner.ts` 中拼装：

| 注入内容 | 位置 | 作用 |
| --- | --- | --- |
| 当前服务器时间 | `server-time-context.ts` | 解释相对时间 |
| runtime prefix | `runtimeOptions.systemPromptPrefix` | deep COT、KB 增强、实验前缀等 |
| Worker Skill 正文 | `runtime.ts` → `WORKER_SKILLS` | 每个非报告工具的主规则 |
| 对话可见输出护栏 | `buildConversationalVisibleOutputGuardrail()` | 约束咨询回答最终形态 |
| 可用工具护栏 | `toolAvailabilityGuardrail` | 只能基于当前工具列表回答，禁止虚构 MCP、工具调用和业务数据 |
| 字段对齐护栏 | `fieldAlignmentGuardrail` | 要求名称/ID/编号/标准键对齐，必要时补查 |
| 风险分语义护栏 | `riskScoreSemanticsGuardrail` | 风险类分数越高代表风险越高 |
| 澄清工具护栏 | `clarificationGuardrail` | 约束 Worker 内 `request_further_info` |

然后追加历史消息和当前 Worker user prompt。

非报告 Worker 如果是流式咨询工具，会使用 `callOpenAIWithToolsStream()`，并透传：

- `reasoning_delta`
- `tool_call_delta`
- `tool_call_ready`
- `tool_execution_started`
- `tool_execution_completed`
- `tool_execution_failed`

## 五、咨询专家注入点

### Skill 正文

| Worker | Skill |
| --- | --- |
| `consult_omni` | `skills/conversational/omni/SKILL.md` |
| `consult_driver_expert` | `skills/conversational/driver_expert/SKILL.md` |
| `consult_vehicle_expert` | `skills/conversational/vehicle_expert/SKILL.md` |
| `consult_unit_expert` | `skills/conversational/unit_expert/SKILL.md` |
| `consult_route_expert` | `skills/conversational/route_expert/SKILL.md` |
| `consult_station_expert` | `skills/conversational/station_expert/SKILL.md` |
| `consult_incident_expert` | `skills/conversational/incident_expert/SKILL.md` |

### Worker user prompt

`buildWorkerPrompt()` 将 Router tool call 参数转成 Worker user message。

咨询类主要输入：

- `query`
- `context`
- `cot_mode`

单位和线路专家在 `router-service.ts` 中会先调用：

- `resolveUnitAliasInText()`
- `resolveRouteAliasInText()`

然后通过 `applyEntityAliasHintToPrompt()` 把别名解析提示注入 Worker user prompt。

### deep COT system prefix

`runtime.ts` 的 `resolveWorkerRuntimeOptions()` 根据 `cot_mode` 决定是否注入 `systemPromptPrefix`：

| 专家 | deep COT 来源 |
| --- | --- |
| 驾驶员 | `ab-test/adapter.ts` 或 `DRIVER_EXPERT_COT_SYSTEM_PROMPT` |
| 车辆 | `ab-test/adapter.ts` 或 `VEHICLE_EXPERT_COT_SYSTEM_PROMPT` |
| 单位 | `experts/registry.ts` → `UNIT_EXPERT_COT_SYSTEM_PROMPT` |
| 线路 | `experts/registry.ts` → `ROUTE_EXPERT_COT_SYSTEM_PROMPT` |
| 站场 | `experts/registry.ts` 内联站场 deep COT prompt |
| 事故 | `experts/registry.ts` → `INCIDENT_EXPERT_COT_SYSTEM_PROMPT` |

这些前缀要求模型在内部做更充分分析，但最终只输出结论、依据、建议和数据缺口，不暴露隐藏推理过程。

### Expert runtime metadata

`experts/context-builder.ts` 的 `buildExpertRuntimeContext()` 会为 `consult_omni` 和所有 consult 专家调用 `buildOmniKbRuntimeOptions()`，并写入：

- `expert_runtime.domain`
- `expert_runtime.task_type`
- `expert_runtime.worker_tool`
- `expert_runtime.context_flags`
- `expert_runtime.history_message_count`

这些 metadata 不直接影响模型，除非同时产生了 `systemPromptPrefix`。

## 六、知识库增强注入

知识库增强在 `agent/src/domains/chat/omni-kb-context.ts`。

适用范围：

- `consult_omni`
- 所有 `taskType=consult` 的专家 Worker

流程：

1. `decideKbRetrieval(query)` 根据政策/制度/条款/通知/办法等关键词判断是否检索。
2. 命中时调用 `KB_API_BASE_URL/v1/retrieve`。
3. 默认 `topK = 8`，展示注入片段时取前 4 条。
4. `formatKbContextSnippet()` 生成 KB 上下文。
5. 该上下文作为 `systemPromptPrefix` 注入 Worker system。

KB 注入文本包含：

- “你可以参考以下知识库检索结果”
- “不要逐段照抄给用户”
- “如果明显无关就忽略”
- “若使用，请尽量点明来源文档或条款位置”
- 当前用户问题
- 片段来源文档、标题路径/字段路径、相关度、内容

metadata 中记录：

- `omni_kb_debug.configured`
- `omni_kb_debug.attempted`
- `omni_kb_debug.injected`
- `omni_kb_debug.hit_count`
- `omni_kb_debug.gate.reason`
- `omni_kb_debug.gate.matched_terms`
- `omni_kb_debug.hits`

## 七、规则回复链路

### Router 选择 `rule_reply`

`rule_reply` 只能在当前轮规则匹配结果支持时进入。Router prompt 里有：

- `[RULE_ROUTING_POLICY]`
- `[RULE_MATCH_RESULTS]`

规则匹配结果来自 `precomputeRuleMatchContext()`，匹配失败或无命中时 `rule_reply` 不可用。

### Worker 注入

`rule_reply` 的 Skill：

- `skills/conversational/rule_reply/SKILL.md`

Worker system 仍会叠加通用护栏：

- 当前时间
- 可用工具护栏
- 字段对齐护栏
- 澄清工具护栏

Router 会自动补 `user_query`，并校验 `rule_id`。

### `rule_exit`

`rule_reply` Worker 可调用 `rule_exit`。如果返回 metadata 中有 `rule_exit`：

1. Router 把当前 `rule_id` 加入本轮 blockedRuleId。
2. 将 `rule_exit_triggered` 写回 Router tool message。
3. Router 继续下一轮选择，避免重复调用同一规则。

## 八、规则配置链路

规则配置优先于 Router，由 `chat-service.ts` 调用 `tryHandleRuleConfig()`。

### V2 状态机路径

默认 `RULE_CONFIG_STATE_MACHINE_V2` 不为 `false` 时启用。

入口：

- `rules/rule-config/service.ts` → `tryHandleRuleConfigV2()`

处理：

- 如果无 draft、draft 已取消或已保存，返回 `null`，继续 Router。
- 用户输入取消词时清除 draft。
- 用户确认保存时调用 `saveRuleConfigSessionV2()`。
- 普通编辑轮次调用 `runRuleAskerProposal()`。

`runRuleAskerProposal()` 的 system prompt：

- 使用 `skills/conversational/rule_asker/SKILL.md`
- 追加 `CRITICAL:` 段落
- 明确这是 proposal worker，不是用户可见 assistant
- 必须先调用 `get_rule_draft`
- 必须再调用 `submit_rule_turn` 且只调用一次
- 不得直接回复用户

可用工具被 scoped provider 限制为：

- `get_rule_draft`
- `submit_rule_turn`

如果模型未按要求调用工具，会追加 system 纠错：

`You must call get_rule_draft first and then submit_rule_turn exactly once. Do not answer the user directly.`

### 规则编译

保存或确认时会调用 rule builder：

- `compileRuleConfigSession()`
- `compileRuleDraft()`

system prompt：

- `skills/structured/rule_builder/SKILL.md`

user prompt 包含：

- `draft_mode`
- `latest_user_request`
- `refresh_hints`
- `rule_draft`
- `conversation_context`

调用参数：

- `responseFormat: 'json_object'`
- `temperature: 0.2`
- 模型：`OPENAI_WORKER_MODEL || OPENAI_MODEL || DEFAULT_MODEL`

### 旧规则配置路径

当 `RULE_CONFIG_STATE_MACHINE_V2=false` 时，`tryHandleRuleConfig()` 会：

1. 构造 `buildRuleAskerPrompt()`。
2. 调用 `runWorkerWithTools(env, 'rule_asker', ...)`。
3. Worker 层对 `rule_asker` 追加强制要求：每轮回复前必须调用 `get_rule_draft` 和 `update_rule_draft`，即使没有改动也要 `noop: true`。

## 九、Tool Provider 与工具可见性注入

非报告 Worker 默认使用 `createToolProvider(env)`，可能暴露：

- MCP 工具
- KB 工具
- 规则工具
- `request_further_info`

Worker system 中的 `toolAvailabilityGuardrail` 会把当前 `provider.listTools()` 的结果注入为“当前可用工具”。

这段注入要求：

- 只能基于当前列出的工具回答工具/MCP 接入问题。
- 不要虚构工具执行、示例入参、示例结果或业务数据。
- 只有真实发起过工具调用，才能说“我查了”或“我调用了”。
- 优先使用最具体、最匹配的工具。
- 不要直接输出原始 JSON，除非用户明确要求。
- 多步查询中用前一步结果里的 ID、编号、标准名继续查询。
- 多候选可补查时同轮补查，仍无法区分才澄清。

metadata 会记录：

- `tool_provider_mode`
- `available_tool_names`
- `mcp_configured`
- `mcp_visible`
- `mcp_list_failed`
- `mcp_tool_names`
- `tool_provider_allow_list`
- `kb_tool_enabled`
- `kb_api_configured`

## 十、澄清注入

Router 与 Worker 都可使用 `request_further_info`。

Router 侧要求：

- 当前轮无法继续时，先把用户可见澄清写在 assistant content。
- 再调用 `request_further_info` 持久化 pending 状态。
- 不要在工具参数里重复澄清正文。
- `resume_tool` 是下一轮应继续执行的工具。
- 报告参数用 `resume_mode=fill_args`；对话型工具可用 `append_user_reply`。

Worker 侧要求：

- 如果已拿到可继续查询的 ID、编号或标准名称，优先继续查。
- 只有缺少用户才能判断的信息时再澄清。
- 对结构化参数使用 `fill_args`，对对话型工具可用 `append_user_reply`。

pending 状态之后会通过 `renderPendingFurtherInfoPrompt()` 注入 Router。

## 十一、Opening / Progress / Closing

非报告链路同样可能出现阶段文案：

| 阶段 | 位置 | 说明 |
| --- | --- | --- |
| pre-router opening | `worker-runner.ts` → `generatePreRouterOpening()` | Chat Service 进入 Rule Config / Router 前生成 |
| worker opening | `buildOpeningStepPrompt()` | Worker 主流程前生成，可被 `suppressOpeningText` 禁用 |
| progress | `buildProgressStepPrompt()` | 工具拿到有效数据时发 progress 事件 |
| closing | `buildClosingStepPrompt()` | 部分 Worker 最终回答后生成一句收尾 |

`/chat` 和 `/chat/stream` 默认先生成 pre-router opening，并把后续 Router/Worker opening 禁用，避免重复。

## 十二、快速定位

| 现象 | 优先检查 |
| --- | --- |
| 普通咨询被路由到报告 | `router-tools.ts` 的 `REPORT_BOUNDARY`、对应 `consult_*` description、Router Skill |
| 报告追问没有进入专家咨询 | `renderLatestStructuredReportPrompt()`、`consult_*_expert` description、历史消息 |
| 专家没有使用 deep COT | Router 是否传了 `cot_mode=deep`、`resolveWorkerRuntimeOptions()`、`experts/registry.ts` |
| 制度/规定问题没有 KB 上下文 | `omni-kb-context.ts` 的 gate、`KB_API_BASE_URL`、`omni_kb_debug` metadata |
| 咨询类虚构工具或数据 | `toolAvailabilityGuardrail`、`available_tool_names`、实际 tool calls |
| 规则没有触发 `rule_reply` | `rule_match` metadata、`RULE_MATCH_RESULTS`、Router allow list |
| `rule_reply` 反复进同一规则 | `rule_exit` metadata、blockedRuleId、`skipRuleId` |
| 规则配置不走 Router | 当前 session 是否存在 rule draft、`RULE_CONFIG_STATE_MACHINE_V2` |
| 规则配置模型直接回复而不提交 proposal | `runRuleAskerProposal()` 的 scoped tools 和 system 纠错 |
| 多轮澄清恢复错 | `pending_further_info` metadata、`renderPendingFurtherInfoPrompt()`、历史消息 |
