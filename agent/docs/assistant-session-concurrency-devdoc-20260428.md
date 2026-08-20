# Assistant Session Concurrency DevDoc

## 背景

Assistant 会话在连续发送、多标签页、脚本直调或流式/非流式混用时，不能只依赖前端禁发来保证顺序。后端需要在 `session` 维度建立运行态，确保同一会话不会同时执行多个有效请求，并且旧请求不会覆盖新请求结果。

本文档记录当前现状、问题、方案，以及本次提交中的落地范围。

## 现状

### 前端现状

- 测试前端已经有一个轻量补丁：同一 `session` 发送中再次发送时，只保留一个可覆盖的 pending slot。
- 该补丁只覆盖单页面交互，不能防住多标签页、多客户端或直接调用接口。
- 前端接口协议没有变，仍然调用现有 `/chat` 和 `/chat/stream`。

### 后端改造前现状

- `/chat` 和 `/chat/stream` 原本收到请求后直接读取会话历史并执行。
- 没有统一的 `run_id`。
- 没有 active run / pending run 状态。
- 没有 session 级 single-flight。
- 没有旧 run 提交保护。

## 问题

### 前端控制不能兜底

只靠前端会漏掉这些场景：

- 同一用户打开多个标签页同时发送；
- 多客户端同时操作同一个 `session`；
- 自动化脚本或调试工具直接请求后端；
- `/chat` 与 `/chat/stream` 混用。

这些情况下，后端仍可能同时执行多个同 session 请求。

### 并发执行会污染会话状态

如果同一 `session` 同时跑多个请求，可能出现：

- 多个请求读取到不一致的历史；
- assistant 回复乱序落库；
- 旧请求晚返回后覆盖新请求 preview；
- 流式输出与最终消息不一致；
- 用户后发的补充没有成为真正的最终语义。

### 缺少 run 生命周期

系统需要明确表达：

- 哪个请求正在执行；
- 哪个请求排队等待；
- 哪个请求被新请求替代；
- 哪个 run 有权写入 assistant 最终消息；
- 哪个 run 超时或失败。

## 方案

### 目标

1. 同一 `session` 任意时刻只允许一个 `running` run。
2. 同一 `session` 最多保留一个 `queued` run，后来的 queued 覆盖旧的 queued。
3. `/chat` 和 `/chat/stream` 保持接口兼容，前端无需强制修改。
4. 只有仍处于有效 `running` 状态的 run 才能提交 assistant 最终消息和更新会话 preview。
5. 保留 run 历史，方便排障和后续扩展取消、重试、观测。

### 数据结构

新增 `session_runs` 表：

- `id`
- `session_id`
- `status`
- `mode`
- `request_content`
- `request_metadata`
- `response_json`
- `error_message`
- `superseded_by_run_id`
- `cancel_requested`
- `lease_owner`
- `lease_expires_at`
- `created_at`
- `started_at`
- `finished_at`

关键索引：

- `session_id`
- `status`
- `created_at`
- `session_id WHERE status = 'running'` 唯一约束
- `session_id WHERE status = 'queued'` 唯一约束

这两个唯一约束分别保证同一会话只有一个 active run 和一个 pending latest run。

### 请求流程

1. 请求进入 `/chat` 或 `/chat/stream`。
2. 后端创建一个 `queued` run。
3. 创建新 queued run 前，会将同一 session 里已有的 queued run 标记为 `cancelled`，实现 latest-only pending。
4. run 尝试争抢执行权。
5. 如果当前 session 没有有效 `running` run，则该 run 切换为 `running` 并开始执行。
6. 如果已有 `running` run，则当前 run 保持 queued 并短轮询等待。
7. 等待超时则标记为 `failed`。
8. 执行完成后，仍处于 `running` 的 run 才允许提交 assistant 消息、更新 preview，并写入 `completed`。

### 流式处理

`/chat/stream` 保持 SSE 协议兼容，同时在事件 payload 中增加 `run_id`：

- `start`
- `delta`
- `final`
- `error`

旧前端如果忽略 `run_id` 仍可继续消费；新前端可以用 `run_id` 做更严格的流式过滤。

### 失效提交保护

在写入 assistant 最终消息和更新 preview 前，后端会再次检查 run 是否仍为 `running`。

如果 run 已经因为超时、替代或其他原因失效，则不会继续提交最终消息，避免旧请求污染新结果。

## 本次落地范围

本次提交已实现：

- 新增迁移：`agent/migrations/0014_session_runs.sql`
- 新增仓储：`agent/src/domains/chat/session-run-repository.ts`
- `/chat` 接入 session run 管理
- `/chat/stream` 接入 session run 管理
- 同一 session 只有一个 `running` run
- 同一 session 只有一个 `queued` run
- 新 queued 覆盖旧 queued
- run lease 过期后可被标记为 failed
- assistant 最终消息提交前检查 run 是否仍有效
- 删除 session 时清理对应 `session_runs`
- SSE 事件增加 `run_id`

## 当前限制

- 当前实现没有显式取消接口。
- `cancel_requested` 字段已预留，但模型流和工具调用还没有周期性检查取消标记。
- queued run 采用短轮询等待，不是独立后台任务调度器。
- `/chat` 仍保持同步响应语义；如果同 session 当前已有长 run，请求会等待一段时间。
- run 历史已落表，但还没有管理端查询接口。

## 后续建议

1. 增加 `POST /sessions/:sessionId/runs/:runId/cancel`。
2. 在模型流、工具调用、长查询中检查 `cancel_requested`。
3. 增加 active run 查询接口，方便前端展示更准确状态。
4. 为 `session_runs` 增加清理策略，避免历史无限增长。
5. 为并发发送场景补集成测试，覆盖 `/chat`、`/chat/stream` 和混用场景。

## 验证

本次实现通过：

```bash
npx tsc -p agent/tsconfig.json --noEmit
```
