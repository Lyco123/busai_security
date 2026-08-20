# Agent 多步执行与自然开场/退场话术实现说明

## 1. 背景

当前 agent 原本以“先执行工具，后统一输出”为主。对于以下场景，用户体验不够自然：

- 查数后再生成最终文本
- 生成结构化或半结构化报告

目标是升级为轻量多步执行框架，让 agent 能够：

- 在需要查数或生成报告时，先输出一句自然的开场说明
- 执行工具和数据检索
- 输出正式正文
- 在报告类任务末尾，再输出一句自然的退场补充说明

约束如下：

- 只显示 agent 真实输出，不显示 runtime 伪造过程文案
- 不新增独立开场白 skill 或补充说明 skill
- 运行时允许多次模型调用，但不引入复杂 planner
- 前端只展示 assistant 实际输出，不暴露工具调用细节

## 2. 方案框架

本次采用“轻量多步执行编排”，而不是引入独立技能体系。

整体流程：

1. `Task Classification`
   - 判断是否为普通对话、查数问答、报告生成
2. `Opening Step`
   - 查数类和报告类任务先生成一句短开场
3. `Execution Step`
   - 执行 worker、工具调用、实体确认、数据获取
4. `Final Answer Step`
   - 基于工具结果生成正式正文
5. `Closing Step`
   - 仅报告类任务追加一句自然 follow-up

这套流程中，开场和退场是运行时步骤，不是独立业务 skill。

## 3. 本次实现范围

本次实现聚焦于把已有 opening/closing 阶段能力真正接入主链路，并让前端能正确显示结果。

已完成：

- 后端流式链路支持先发送 opening，再执行工具，再继续发送正文
- 非流式链路能把 opening、正文、closing 合并为最终 assistant 内容
- 路由层支持把 opening/closing 文本在不同 worker 路径中上传和透传
- 前端支持渲染“自然语言前缀 + 报告 JSON/结构化内容 + 自然语言后缀”
- 保持现有 SSE 事件类型不变，继续只使用 agent 真实 `delta`

未做：

- 未新增 runtime 状态事件，如 `status`、`tool_start`、`tool_done`
- 未新增独立开场白 skill 或退场说明 skill
- 未引入复杂 planner、任务图或通用执行计划系统

## 4. 实际改动

### 4.1 Runtime 接线

文件：

- `agent/src/app/runtime.ts`

调整内容：

- 把 `callOpenAI` 注入 `createWorkerRunner(...)`
- 让 `runWorkerWithOmniKbContext(...)` 的返回值支持：
  - `leadingContent`
  - `trailingContent`
  - `sources`

作用：

- 运行时能消费 worker opening/closing 阶段生成的真实文本
- 主链路可以继续保留当前 worker/router 架构，只在外层增加多阶段编排能力

### 4.2 Chat Service 改造

文件：

- `agent/src/domains/chat/chat-service.ts`

调整内容：

- 在非流式请求里，把 `leadingContent + 正文 + trailingContent` 合并为最终 assistant 消息
- 在流式请求里新增统一的 `appendAssistantDelta(...)`
- `routeRequest(...)` 支持接收 `onAssistantDelta`
- opening 在 worker 开始执行前即可通过普通 `delta` 发给前端
- 正文完成后，如存在 `trailingContent`，继续追加到同一条 assistant 消息

作用：

- 同一条 assistant 回复现在可以分阶段到达
- 用户能先看到一句自然开场，再等待正文继续流出
- 报告类任务末尾能自然出现补充说明

### 4.3 Router 接线

文件：

- `agent/src/domains/chat/router-service.ts`

调整内容：

- `RouteRequestOptions` 增加 `onAssistantDelta?: (delta: string) => void`
- 不同 worker 执行分支的返回值统一支持：
  - `leadingContent`
  - `trailingContent`
- 增加 `sharedRuntimeOptions`，把 `onAssistantDelta` 继续透传到 worker runtime
- `consult_omni`、`consult_vehicle_expert`、结构化报告路径、通用 worker 路径都统一支持 opening/closing 文本上传

作用：

- opening/closing 不再只存在于 worker 内部，而是能一路上传到 chat-service
- 不同路由场景下的行为保持一致

### 4.4 Frontend 适配

文件：

- `frtend-tsx/src/pages/ai/AIAssistant.tsx`

调整内容：

- 新增 `resolveJsonEnvelope(...)`
  - 支持从“自然语言前缀 + JSON + 自然语言后缀”的消息中提取结构化 payload
- `resolveReportPayload(...)` 返回：
  - `payload`
  - `tool`
  - `leadingText`
  - `trailingText`
- `resolveStructuredPayload(...)` 同样支持包裹式 JSON
- 渲染报告时使用统一 `reportWrapper(...)`
  - 先显示开场文字
  - 再显示报告卡片或结构化内容
  - 再显示退场说明

作用：

- 报告类消息即使前后夹带自然语言，也不会破坏现有报告卡片渲染
- 不需要新增系统过程消息 UI
- 前端仍然只展示 assistant 的真实输出

## 5. 当前行为说明

### 5.1 普通闲聊

- 仍按原有方式直接输出正文
- 不强制进入 opening 或 closing

### 5.2 查数问答

- 先出现一句简短开场说明
- 执行工具和数据查询
- 再输出最终答案
- 默认不追加退场说明

### 5.3 报告生成

- 先出现一句简短开场说明
- 执行 worker 和工具调用
- 输出报告正文或报告卡片
- 末尾再补一句 follow-up 退场说明

## 6. 设计取舍

本次明确采用以下策略：

- 先拆“步骤”，不拆“技能”
- 不增加 runtime 假文案，只转发模型真实输出
- 不新增额外 SSE 事件协议
- 不在前端展示工具名、调用链或中间状态

这样做的原因：

- 复杂度最低
- 保持现有架构稳定
- 用户能明显感知“先回应，再处理，再给结果”
- 避免把系统做成暴露 CoT 的形态

## 7. 验证结果

已完成验证：

- `agent`：`npx tsc --noEmit -p tsconfig.json`
- `frtend-tsx`：`npm run build`

结果：

- 后端类型检查通过
- 前端构建通过
- 前端构建存在既有的 Vite chunk warning，但不影响本次功能

## 8. 已知限制

- opening/closing 文本的稳定性仍依赖当前 worker 内的阶段 prompt
- 普通查询是否触发 opening，仍取决于任务分类和 worker 路径
- 目前没有独立的产品化配置层来统一管理 opening/closing 话术
- 未引入更细粒度的“执行中状态”展示，这是有意保持只显示 agent 真实输出

## 9. 后续建议

如果下一阶段继续演进，建议按以下顺序推进：

1. 稳定 opening/closing 阶段 prompt
2. 增加针对普通查询、查数问答、报告生成的回归用例
3. 为 opening/closing 补充埋点，评估触发率和文案质量
4. 只有在稳定性或运营配置需求明显出现时，再考虑把 opening/closing 技能化

## 10. 本次提交涉及文件

- `agent/src/app/runtime.ts`
- `agent/src/domains/chat/chat-service.ts`
- `agent/src/domains/chat/router-service.ts`
- `frtend-tsx/src/pages/ai/AIAssistant.tsx`
- `agent/docs/agent-multistep-opening-closing-20260405.md`
