# 流式协议与前端适配说明

日期：2026-05-12

## 背景

本轮目标是把 conversational agent，尤其是 `consult_*` 路径，向“文本增量 + 工具调用事件 + 工具执行状态”的策略 A 流式体验靠拢。

此前 `/chat/stream` 主要返回：

- `start`
- `delta`
- `progress`
- `final`
- `error`
- `[DONE]`

其中 `delta` 只承载 assistant 文本增量，工具调用过程基本不作为一等事件暴露给前端。

## 后端协议改动

在保持原有事件兼容的基础上，新增 agent/tool 事件：

- `tool_call_delta`
  - 表示模型正在流式生成工具调用参数。
  - 字段：`index`、`id?`、`tool?`、`argumentsDelta?`

- `tool_call_ready`
  - 表示某个工具调用参数已拼装完成，可以执行。
  - 字段：`id`、`tool`、`args`

- `tool_execution_started`
  - 表示后端开始执行工具。
  - 字段：`id`、`tool`、`args`

- `tool_execution_completed`
  - 表示工具执行完成。
  - 字段：`id`、`tool`、`success`、`resultSummary?`

- `tool_execution_failed`
  - 表示工具执行异常。
  - 字段：`id`、`tool`、`error`

这些事件仍通过 SSE 的 `data: {...}\n\n` 形式发送，并带上 `run_id`。

### 事件触发范围（与实现对齐）

- **`tool_call_delta` / `tool_call_ready`**：仅在 **流式** 且走 **对话型 consult worker**（`consult_omni` 与各 `consult_*_expert`）的主模型循环时发出，对应 `callOpenAIWithToolsStream` 解析出的工具调用流。
- **`tool_execution_started` / `tool_execution_completed` / `tool_execution_failed`**：在该 worker 轮次内 **实际执行 MCP/local 工具** 时发出（`onAgentEvent` 挂上的路径即可收到），**不限于**上述 consult 专用分支；其它会进工具执行循环的 worker，在 `/chat/stream` 下仍可能只收到「执行态」类事件而收不到「参数流式拼装」类事件。

本文约定的是 **主业务路径** `/chat/stream` 上可能出现的类型；实现上若遇到未列出的 `type`，按「兼容性」一节忽略即可。

## LLM Client 改动

新增 `callOpenAIWithToolsStream(...)`，用于解析 Chat Completions 的流式响应：

- 读取 `choices[0].delta.content` 并触发文本增量回调。
- 读取 `choices[0].delta.tool_calls`。
- 按 `tool_calls[index]` 累积：
  - `id`
  - `function.name`
  - `function.arguments`
- 在流结束后解析完整 arguments JSON，形成内部 `ChatToolCall`。

接入位置：

- `agent/src/infra/llm/chat-completions.ts`
- `agent/src/app/runtime.ts`

## 前端适配

流式工具条与 `toolActivities` 已接在主对话页：**`frtend-tsx/src/pages/ai/AIAssistant.tsx`**。仓库另有 **`frtend-tsx/src/components/AIAssistant.tsx`**（或其它入口），若未调用 `sendMessageStream` / `onEvent`，则不会出现工具活动 UI；二者不要混为一谈。

前端 `sendMessageStream` 保持原有 `onDelta` / `onProgress` 能力，同时增加事件型消费：

- `onEvent(event)`
- 识别新增的工具事件类型。
- 将工具活动累积到临时 assistant message 的 `toolActivities` 上。

UI 展示策略：

- assistant 正文继续由 `delta` 实时更新。
- 工具活动以简洁状态展示在 streaming message 下方。
- 当前只显示最近几条工具活动，避免打断主回答阅读。

状态示例：

- `xxx_tool · 准备中`
- `xxx_tool · 执行中`
- `xxx_tool · 完成`
- `xxx_tool · 失败`

## 兼容性

现有前端仍可只消费：

- `delta`
- `progress`
- `final`
- `error`

新增工具事件不会破坏旧消费逻辑。未识别事件可忽略。

**说明**：`/chat/direct-stream-probe`、`/chat/pipeline-stream-probe` 及 `OPENAI_STREAM_DIAGNOSTICS` 等 **仅用于排障**，可能产生额外 SSE 载荷；产品侧前端 **不要依赖** 这些调试专用事件。排障请参阅 `agent/docs/openai-stream-diagnostics-20260513.md`、`agent/docs/direct-stream-probe-20260513.md`（见下文「诊断补充」）。

## 当前范围

本轮主要服务 conversational agent 的策略 A 改造，优先覆盖 `consult_*` 类链路。`asker`、报告生成、普通 `/chat` 等管线不在本轮范围内。

## 诊断补充（运维 / 开发排障用）

以下内容与 **产品线读者无关**；仅服务本地或线上排查延迟、SSE 粒度等问题。

2026-05-13 增加了 `OPENAI_STREAM_DIAGNOSTICS` 调试开关，用于判断上游模型 SSE chunk、parser 拆事件和正文 delta 产生时间之间的关系。详细启用方式、日志判读与拆除清单见：

- `agent/docs/openai-stream-diagnostics-20260513.md`

2026-05-13 同时增加了旁路直通探针，用于在不经过 conversational agent 主链路的情况下，对比供应商原始 SSE 的首字节、首 event、首正文 delta 和 delta 粒度。见：

- `agent/docs/direct-stream-probe-20260513.md`
