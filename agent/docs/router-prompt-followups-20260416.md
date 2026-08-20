# Router Prompt Follow-ups

日期：2026-04-16

## 本次已处理

- `agent/skills/router/SKILL.md`
  - 已统一报告生成与咨询查询的主边界表达。
- `agent/src/domains/chat/router-tools.ts`
  - 已统一工具描述表达，并去掉底部重复追加描述。
- `agent/src/domains/chat/router-prompts.ts`
  - 已将 `ROUTER_SKILL_RUNTIME_SUPPLEMENT` 收缩为最小运行时上下文原则，不再重复业务边界。
- `agent/src/domains/chat/router-service.ts`
  - 已补充说明：一旦确认当前轮是在续接同一任务，可以结合最近上下文恢复多轮分散提供的缺失信息，而不是只看当前轮。

## 暂时未改，但仍可能影响 Router 效果的部分

### 0. 实体解析仍缺少统一的 normalization / expansion 管线

涉及文件：
- `agent/src/domains/chat/structured-lookup.ts`
- 各类 `resolveDriverLookup / resolveVehicleLookup / resolveUnitLookup / resolveRouteLookup / resolveIncidentLookup`

问题：
- 当前 lookup 更接近“单次字面匹配 + 少量兜底打分”，不像 ChatGPT 一类 agent 那样会在内部自动尝试等价表述。
- 因此会出现这类问题：
  - `527路` 能否命中 `527`
  - `线路(527)` 能否命中 `527`
  - 车牌里的空格、分隔符、大小写差异
  - 单位简称和全称
- 这类问题本质上不该继续堆到 Router prompt，而应该落在实体解析层。

建议方案：
- 抽一个统一的 entity resolution pipeline，分成 5 步：
  1. `extract`
  2. `normalize`
  3. `expand`
  4. `match`
  5. `select`
- 结构上采用“统一框架 + 实体策略”的方式，而不是给每条链路继续补 if/else。
- Router 只负责决定“查谁”；entity resolution pipeline 负责“怎么把用户说法转成能命中的实体”。

建议落地顺序：
1. 先抽公共 resolution framework
2. 优先接入 `route`
3. 再迁移 `vehicle / unit / driver / incident`

当前临时措施：
- 已先对 `route` 加一个小型临时 normalizer，把带“路/线路/括号”的常见编号表达优先归一化成不带“路”的编号，先止血当前 manual case。
- 当前临时规则仅覆盖这类线路编号表达：
  - `527路`
  - `线路527`
  - `线路(527)` / `线路（527）`
- 当前临时规则的目的只是解决“带路字样的编号命中不到纯编号”的问题，不等于正式的统一实体解析方案。
- 后续如果开始抽公共 `entity resolution pipeline`，这段临时代码应被迁移或替换，而不是继续在各实体 lookup 里扩散复制。

### 1. `renderPendingFurtherInfoPrompt`

文件：`agent/src/domains/chat/router-service.ts`

作用：
- 当上一轮进入澄清态时，把待补参数、候选项和恢复规则注入 Router system prompt。

为什么会影响：
- 它直接决定 Router 更倾向把当前轮识别为“继续补参”还是“已经切换成新任务”。
- 如果这里写得过于保守，可能导致本来可以恢复的报告请求被当成新咨询。
- 如果这里写得过于激进，也可能把新的咨询误恢复到旧报告链路。

后续建议：
- 继续保持它只负责“状态恢复判断与缺失槽位恢复”，不要再掺入业务对象边界。
- 如果后面还有误判，优先检查这里是否把“部分补充”“改口”“新问题”区分清楚。

### 2. `renderLatestStructuredReportPrompt`

文件：`agent/src/domains/chat/router-service.ts`

作用：
- 当最近一轮存在结构化报告或报告失败上下文时，把该上下文注入 Router system prompt。

为什么会影响：
- 它会强烈影响 Router 对“报告追问”与“重新生成报告”的区分。
- 当前逻辑是合理的，但如果写法过重，仍可能把新的报告请求压回咨询工具。

后续建议：
- 保持它只负责区分“追问上一轮报告”与“明确要求重生成/更新/重新出一份报告”。
- 允许它在确认是同一任务续接时，帮助恢复被拆散在多轮里的日期、分区、目标确认等短补充信息。
- 不要再在这里补充车辆/驾驶员/单位/线路的业务边界定义，避免再次和主 skill 冲突。

### 3. `clarificationGuide`

文件：`agent/src/domains/chat/router-service.ts`

作用：
- 告诉 Router 如何使用 `request_further_info`，以及澄清文案该放在哪。

为什么会影响：
- 它会影响 Router 在“先澄清”与“直接选一个咨询工具兜底”之间的倾向。
- 如果这部分不清楚，模型容易在信息不足时直接掉进 `consult_omni`。

后续建议：
- 这部分继续只保留工具使用规范，不要写业务对象判断。

### 4. `renderRuleMatchForPrompt` / `RULE_ROUTING_POLICY`

文件：`agent/src/domains/chat/router-prompts.ts`

作用：
- 把规则匹配结果和规则路由策略注入 Router system prompt。

为什么会影响：
- 当规则高分命中时，它会显著改变 Router 的优先级判断。
- 即便这次手动测试主要问题不是规则路由，这部分仍然会影响总体选择。

后续建议：
- 当前只保留了规则优先级和 guard 逻辑，没有再混入业务边界，先维持现状。
- 后续如果出现“高分规则把普通咨询吸走”或“高分规则没有被正确选中”，优先回查这里。

## 不属于提示词，但会影响观感的相邻运行时行为

### 1. Router 无 tool 时 fallback 到 `consult_omni`

文件：`agent/src/domains/chat/router-service.ts`

影响：
- 当 Router 因为提示词冲突而犹豫时，最终观感会被放大成“大量掉进 omni”。
- 这不是提示词本身，但会放大提示词问题。

### 2. Tool allow list 动态裁剪

文件：`agent/src/domains/chat/router-service.ts`

影响：
- 某些轮次可选工具集合本来就被 runtime 裁剪过。
- 这会改变模型“最安全选项”的分布，排查时不能只看 prompt。

## 后续排查顺序建议

1. 先看 `renderLatestStructuredReportPrompt`
2. 再看 `renderPendingFurtherInfoPrompt`
3. 再看 `clarificationGuide`
4. 最后回看 `RULE_MATCH_RESULTS` / `RULE_ROUTING_POLICY`

## 备注

- 后续如果继续做 Router 提示词收敛，建议坚持一个原则：
  - 业务边界只在 `router SKILL` 和 `router-tools.ts` 定义。
  - 运行时上下文负责解释当前轮与上一轮的关系，并在确认续接时恢复最近多轮里分散的缺失信息。
  - 规则提示只负责规则优先级，不再夹带业务边界。
