# Router Shortcut Removal 20260408

## 背景

本次调整的目标是移除 router 之外的三类 hard shortcut，把意图识别和分流判断重新收敛到 router：

- `forcedVehicleResume`
- `vehicleMetaQuery`
- `structured report follow-up`

问题本质不是正则本身是否足够精细，而是这些 shortcut 在 router 前或 router 旁路直接改道，导致当前轮最新意图没有完整交给 router 判定。

## 本次变更

### 1. 移除 shortcut 的实际执行路径

文件：[router-service.ts](/d:/BUS/agent/src/domains/chat/router-service.ts)

- 删除 `RouteRequestDeps` 中对 `isStructuredReportFollowUpQuery` 和 `buildStructuredReportFollowUpPrompt` 的依赖。
- 移除 `directToolCall` 之后的强制车辆报告续接逻辑，不再由 `shouldForceResumePendingVehicleReport(...)` 直接把当前轮改写为 `generate_vehicle_report`。
- 移除 vehicle meta query 的 bypass 执行路径，不再直接调用 `handleVehicleMetaQuery()`。
- structured report follow-up 的原硬分支已退出执行路径，当前轮不再在 router 前直接改为咨询 worker。

说明：

- 目前文件里还保留了少量 legacy 代码块作为历史对照，但它们不再参与实际路由。
- 当前生效逻辑已经改为由 router 正常走 tool selection。

### 2. 给 router 增加最近报告上下文注入

文件：[router-service.ts](/d:/BUS/agent/src/domains/chat/router-service.ts)

- 新增 `renderLatestStructuredReportPrompt(...)`。
- 在 router system prompt 中追加 `LATEST STRUCTURED REPORT CONTEXT`。
- 注入内容包括：
  - 最近结构化报告来源工具
  - 最近报告状态：`success / failed / none`
  - 最近 assistant 内容摘要
  - 最近 `report_follow_up.source_tool`

这段注入明确约束 router：

- 解释上一轮报告时优先走咨询工具
- 只有用户明确要求重生成/更新报告时才走 `generate_*_report`
- 用户换话题/换目标时忽略旧报告上下文
- 上一轮报告失败只作为上下文，不做硬拒绝或自动重试

### 3. 保留并继续依赖 pending clarification 上下文

文件：[router-service.ts](/d:/BUS/agent/src/domains/chat/router-service.ts)

本次没有删除 `PENDING FURTHER INFO CONTEXT`，而是继续把它作为唯一的 pending 恢复依据。

当前 router 仍然会先看到：

- `CLARIFICATION TOOL`
- `PENDING FURTHER INFO CONTEXT`
- `LATEST STRUCTURED REPORT CONTEXT`
- `[RULE_MATCH_RESULTS] / [RULE_ROUTING_POLICY]`

这意味着：

- 是否恢复 pending task，交给 router 根据当前轮判断
- 是否忽略 pending、转为新请求，也交给 router 判断

### 4. 用 router skill supplement 和 tool description 承接原职责

文件：[runtime.ts](/d:/BUS/agent/src/app/runtime.ts)

本次没有直接修改 `skills/router/SKILL.md`，而是在 runtime 中通过 `ROUTER_SKILL_RUNTIME_SUPPLEMENT` 对 router skill 做运行时补充。

补充的内容包括：

- pending clarification 只作上下文，不自动恢复
- latest report context 只作上下文，不自动分流
- 车队级车辆元数据/列表/统计优先视为查询意图

同时补强了 router 可见的工具描述：

- `consult_omni`
  - 明确承接车队级车辆元数据、车辆列表、车辆属性、车型、使用性质、分组统计、数量汇总、车牌查资料、车辆档案等请求
  - 明确承接“解释上一轮报告细节”的咨询类任务
- `generate_vehicle_report`
  - 明确排除“解释上一轮报告字段/指标/结论”的场景
  - 只有明确重生成/更新整份报告时才使用
- `consult_vehicle_expert`
  - 明确排除车队级车辆元数据、列表、统计、档案汇总等查询

## 职责承接映射

### 原 `forcedVehicleResume`

之前职责：

- 上一轮 pending 是车辆报告时，直接把当前轮解释成继续生成车辆报告

现在由以下提示词工程承接：

- router system 注入里的 `PENDING FURTHER INFO CONTEXT`
- runtime supplement 里的 pending rule

现在的行为原则：

- 当前轮明确补参才恢复
- 当前轮换话题则忽略 pending
- 当前轮仍不清楚则继续澄清

### 原 `vehicleMetaQuery`

之前职责：

- 靠关键词把车辆元数据/列表/统计问题提前抢走，直接送 `consult_omni`

现在由以下提示词工程承接：

- router skill runtime supplement 中的 `Vehicle Metadata Routing`
- `consult_omni` tool description
- `consult_vehicle_expert` tool description
- `generate_vehicle_report` tool description

现在的行为原则：

- 车队级车辆元数据、列表、统计默认由 router 判成查询意图
- 只有明确车辆本体故障/状态/维修/安全判断才优先 `consult_vehicle_expert`
- 只有明确报告请求才进入 `generate_vehicle_report`

### 原 `structured report follow-up`

之前职责：

- 识别“上一轮报告追问”，直接跳转到咨询 worker

现在由以下提示词工程承接：

- router system 注入里的 `LATEST STRUCTURED REPORT CONTEXT`
- runtime supplement 里的 latest report rule
- `consult_omni` / `consult_vehicle_expert` / `generate_vehicle_report` 的 tool description

现在的行为原则：

- 解释报告细节：咨询工具
- 明确重生成/更新报告：报告工具
- 话题切换：按当前轮正常重路由

## 验证

执行命令：

```bash
npx tsc -p d:\BUS\agent\tsconfig.json --noEmit
```

结果：

- 本次改动没有新增 router shortcut 相关的类型错误
- 当前仍有 4 条既有 TypeScript 报错，位于 [runtime.ts](/d:/BUS/agent/src/app/runtime.ts#L3150) 到 [runtime.ts](/d:/BUS/agent/src/app/runtime.ts#L3153)
- 这些报错是 session/title service 相关的 `db: unknown` 与 `D1DatabaseLike` 类型不匹配，和本次 shortcut 移除无关

## 遗留项

- `router-service.ts` 中还有少量 legacy helper / 注释块未完全物理删除；它们已经不在执行路径上，后续可单独再做一次纯清理提交。
- 本次选择通过 runtime supplement 补 router skill，而不是直接修改 `skills/router/SKILL.md`，这样可以把本次行为变更收口在运行时拼装层。
