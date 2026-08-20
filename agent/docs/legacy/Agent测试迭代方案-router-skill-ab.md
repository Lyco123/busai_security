# Agent 测试迭代方案

> 说明：原有《Agent测试迭代方案》基于旧的 Router 路由盲测方案编写，内容包含 `force_rule vs router_decide` 对比、`rule_state` 会话黏连等历史机制，已不再适用于当前实现。旧版全文已归档到 `agent/docs/legacy/Agent测试迭代方案.md`。

## 当前有效结论

- 旧 Router 路由 A/B 已结束，现网基线路由固定为 `router_decide`
- 当前线上 A/B 为“Router skill 注入 A/B”，实验分组为 `X / Y`
- `router_decide` 命中 `rule_reply` 后，不再通过 `rule_state` 强制续走规则回复管线
- A/B 统计仅统计 `router_skill_prompt_split` 实验数据，旧实验数据不再计入当前面板

## 当前应参考的文档

- 车辆专家拆分实验方案：`agent/docs/legacy/车辆专家拆分AB测试方案.md`
- Agent API 与统计口径：`agent/docs/Agent系统API接口文档.md`

## 当前测试重点

### 1. Router skill 注入 A/B

- `X` 组：注入基线路由 skill，仅暴露现有基础候选工具
- `Y` 组：注入增强路由 skill，并额外暴露 `consult_vehicle_expert`
- 两组都不再使用“车辆域识别后再二次分流”的逻辑，最终由 Router 直接决定调用哪个 worker
- 重点观察指标：
  - `turns`
  - `omni_selected`
  - `vehicle_expert_selected`
  - `rule_reply_selected`
  - `report_selected`
  - `other_selected`

### 1.1 测试前清场

- 如需清除历史 A/B 统计，请在 `agent/` 目录执行：`node ./scripts/reset-ab-test-stats.mjs --include-legacy`
- 如需同时清除当前实验数据，可执行：`node ./scripts/reset-ab-test-stats.mjs --experiment router_skill_prompt_split --include-legacy`
- 后续切换新实验时，只需调整当前实验配置和指标定义，无需再改统计面板结构

### 2. Router 行为验证

- 高分规则命中是强信号，但不是独立实验维度
- 需要验证 Router 提示词、规则命中、`rule_exit` 回退与最终工具选择是否一致
- 不再验证 `force_rule` 与 `router_decide` 的模式对比

### 3. Rule Reply 链路验证

- 验证单轮 `rule_reply` 是否正确响应
- 验证 `rule_exit` 后是否回到 Router 重新决策
- 不再验证基于 `rule_state` 的会话级规则黏连
