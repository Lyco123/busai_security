# Report Source Architecture

## 背景

结构化报告管线之前把共享 `prefetchedSourceData` 直接整包塞进 prompt，并且在 prefetched mode 下还会把这份数据伪装成 tool result 回灌给模型。

这会带来三个问题：

1. prompt 注入内容过重，模型会看到很多模板并不需要的 raw 字段。
2. 一旦共享注入层理解错字段，全体报告都会一起偏。
3. prefetched mode 的 synthetic tool replay 会掩盖真实问题，模型即使错误发起 tool call 也不会立刻暴露。

## 设计目标

这次重构的目标是：

1. 每条报告的 prompt 只注入模板真正需要的 source 数据。
2. runtime 仍然保留完整 canonical source，供 normalizer、appendix 和 metadata 使用。
3. prefetched mode 下不再伪造工具调用结果。
4. 用 contract test 和 CI 固化这套约束。

## 分层模型

现在报告链路分成两层 source：

### 1. Runtime source

这是 router 预取后的完整 canonical source。

用途：

- worker runtime 的 `prefetchedSourceData`
- normalizer 输入
- appendix 原始证据
- metadata / source trace

特点：

- 可以保留 canonical appendix
- 不允许保留 raw MCP envelope
- 管理类报告统一保留 `basic / performance_dashboard / interventions / appendix`

### 2. Prompt source

这是从 runtime source 再裁剪出来的 slim source。

用途：

- 只用于 prompt 中的 `report_source`

特点：

- 只保留模板生成真正需要的字段
- 不保留 raw MCP envelope
- 不保留整包 MCP `result/main/quotaScoreSubList/quotaScoreTrend`

## Canonical source contract

### 管理类报告

`driver / vehicle / unit / route` 统一走：

- `basic`
- `performance_dashboard`
- `interventions.recommendations`
- `appendix.raw_data.source_window`
- `appendix.raw_data.main`
- `appendix.raw_data.ranking_snapshot`
- `appendix.raw_data.alerts_counts`
- `appendix.raw_data.suggestion_counts`
- `appendix.raw_data.quota_summary`
- `appendix.raw_data.quota_items`
- `appendix.raw_data.trend_summary`
- `appendix.raw_data.high_risk_objects`
- `appendix.raw_data.high_risk_rows`
- `appendix.raw_data.risk_objects`
- `appendix.raw_data.suggestions`

其中：

- `quota_items` 是树的扁平证据表
- `quota_summary` 是正文/看板常用的紧凑摘要
- `main` 负责总分、状态、排名、日期等主记录字段

### 事故调查报告

事故报告的 prompt source 保留：

- `basic`
- `section_1_event_and_response`
- `section_2_investigation`
- `section_3_cause_and_nature`
- `section_4_rectification_plan`
- `trigger_analysis`
- `appendix`

这里同样不再把 MCP envelope 直接注入 prompt。

## Prefetched mode 规则

prefetched mode 现在的规则是：

1. router 负责 resolve 实体并预取 runtime source。
2. prompt 中只注入 slim prompt source。
3. worker 必须只基于 `report_source` 输出最终 JSON。
4. 如果 worker 在 prefetched mode 下仍然发起 tool call：
   - 不再伪造 tool result
   - 直接追加系统纠正消息
   - 超过重试阈值后按 format mismatch 失败返回

这条规则的意义是：

- 问题会在真实边界处暴露
- 不会再因为 synthetic replay 把坏行为隐藏掉

## 关键文件

- `agent/src/domains/chat/structured-report-data-sources.ts`
  - prompt source builder
  - prefetched prompt builder
- `agent/src/domains/chat/router-service.ts`
  - resolved report flow 统一走 slim prompt source 注入
- `agent/src/domains/chat/worker-runner.ts`
  - prefetched mode 不再 synthetic replay
- `agent/src/shared/route-profile-mcp.ts`
  - route source 不再泄漏 raw payload 顶层字段

## 测试与 CI

现在有两层 contract test：

### 1. `test:report-source-contract`

检查 canonical runtime source：

- source adapter 不能泄漏 raw MCP 顶层字段
- `quota_summary` 必须能回溯到树叶子
- `quota_items` 必须保留树 identity
- 关键业务规则不能退化

### 2. `test:report-prompt-source-contract`

检查 slim prompt source：

- prompt source 必须声明 canonical contract version
- prompt 中不能出现 raw MCP marker
- prompt source 必须保留模板真正需要的字段

CI 现在会在 `check-text` workflow 里先跑这两组 contract test，再跑文本检查。

## 后续维护原则

后面如果新增报告类型或扩展 source，遵循下面的顺序：

1. 先定义 runtime source contract。
2. 再定义 prompt source 的最小字段集。
3. normalizer 只消费 canonical source，不回读 raw MCP envelope。
4. 新字段先加 contract test，再接入 router / adapter。

不要再做的事：

1. 不要把 raw MCP payload 整包塞进 prompt。
2. 不要在 prefetched mode 下模拟工具结果。
3. 不要在 normalizer 里依赖 raw envelope 的偶然字段。

## 结论

这套架构的核心不是“少传一点字段”，而是明确边界：

- router 负责 resolve 和预取
- source adapter 负责 canonical 化
- prompt 只拿 slim source
- runtime 保留完整 canonical source
- worker 不再假装调过工具

这样共享层即使继续演进，也更容易被 contract test 和 CI 约束住，不会再把同一种偏差同时扩散到所有报告管线。
