# OpenAI 上游流式诊断说明

日期：2026-05-13

## 目的

本诊断用于判断 conversational streaming 体验不顺时，问题位于哪一层：

1. 上游模型本来就晚到或大块返回。
2. 后端 SSE parser 未及时拆分事件。
3. 文本 delta 已经及时产生，问题另在下游展示层。

本轮只增加后端诊断，不修改业务协议。

## 环境变量

`agent/wrangler.toml` 已配置：

```toml
OPENAI_STREAM_DIAGNOSTICS = "false"
```

默认关闭。仅在排查流式问题时改为：

```toml
OPENAI_STREAM_DIAGNOSTICS = "true"
```

部署或本地 `wrangler dev` 重启后生效。

## 日志类型

开启后，后端会输出以下日志：

### 1. `upstream-chunk`

表示后端刚收到一段上游模型响应字节。

字段：

- `ts`
- `bytes`

用途：

- 判断模型首包是否迟到。
- 判断上游是否本身按大 chunk 返回。

### 2. `upstream-event`

表示后端 SSE parser 已从 buffer 中拆出一条上游 SSE event。

字段：

- `ts`
- `boundary`
  - `lf`
  - `crlf`
- `length`
- `preview`

用途：

- 判断 parser 是否在 chunk 到达后及时拆事件。
- 判断上游实际使用 `\n\n` 还是 `\r\n\r\n` 事件边界。

### 3. `text-delta`

表示 parser 已识别出 `delta.content`，并准备交给后续转发层。

字段：

- `ts`
- `length`
- `preview`

用途：

- 判断正文 token 是否已经及时在后端产生。
- 若该日志已经密集出现，而前端仍像一次性输出，则问题大概率不在上游 parser。

## 典型判读

### 情况 A：上游本来就慢

表现：

- `upstream-chunk` 间隔本身很大。

结论：

- 模型服务首包慢，或上游本身以大 chunk 输出。

### 情况 B：parser 有问题

表现：

- `upstream-chunk` 已经多次出现。
- `upstream-event` 明显滞后，甚至到流结束才集中出现。

结论：

- 后端事件边界或 buffer 拆分逻辑有问题。

### 情况 C：parser 已正常

表现：

- `upstream-chunk`
- `upstream-event`
- `text-delta`

三者时间接近，且持续出现。

结论：

- 后端上游解析已正常。
- 若 UI 仍显得不够流，继续排查前端渲染、浏览器网络层或供应商 delta 粒度。

## 当前实现位置

- 诊断开关定义：
  - `agent/src/infra/llm/chat-completions.ts`
  - `agent/src/app/runtime.ts`
- Wrangler 默认配置：
  - `agent/wrangler.toml`

## 拆除说明

该诊断属于临时排障能力。确认不再需要后，按以下顺序拆除：

1. 从 `agent/wrangler.toml` 删除：
   - `OPENAI_STREAM_DIAGNOSTICS`
2. 从 `agent/src/app/runtime.ts` 的 `Env` 删除：
   - `OPENAI_STREAM_DIAGNOSTICS?: string`
3. 从 `agent/src/infra/llm/chat-completions.ts` 删除：
   - `OpenAIChatEnvLike.OPENAI_STREAM_DIAGNOSTICS`
   - `isOpenAIStreamDiagnosticsEnabled`
   - `previewDiagnosticText`
   - `emitOpenAIStreamDiagnostic`
   - `upstream-chunk`
   - `upstream-event`
   - `text-delta`
     相关调用点
4. 删除本说明文档。
5. 重新运行：
   - `npx tsc --noEmit`
   - `npm run build:tsx`

这样可以避免只删环境变量、但遗留代码分支或文档失效。
