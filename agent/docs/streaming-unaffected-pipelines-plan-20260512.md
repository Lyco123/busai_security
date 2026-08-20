# 未改动管线与后续计划

日期：2026-05-12

## 本轮未改动的管线

### 1. `rule_asker` / 规则配置 V2

当前默认启用规则配置状态机 V2。该链路不是“模型直接生成用户可见回复”，而是：

1. 模型产出结构化 proposal。
2. 后端状态机应用 proposal。
3. 后端模板渲染 assistant message。

因此它仍然可能表现为“等待较久后一次性输出”。本轮未改动。

### 2. `generate_*_report` 报告生成

包括：

- `generate_driver_report`
- `generate_vehicle_report`
- `generate_unit_report`
- `generate_route_report`
- `generate_accident_investigation_report`

报告链路仍以结构化数据获取、校验、归一化和格式化为主，不做 token-by-token 输出承诺。本轮未改动。

### 3. 非流式 `/chat`

`POST /chat` 仍保持非流式响应语义。本轮只增强 `/chat/stream` 的事件能力。

### 4. 报告摘要接口

`/reports/summary` 仍保持现有同步返回行为。本轮未改动。

### 5. 旧前端 assistant 页面

根目录 `src/pages/assistant/AssistantPage.tsx` 仍使用非流式 `sendMessage`。本轮前端适配目标是 `frtend-tsx` 下的新助手页面。

### 6. 检索、OCR、知识库等外围服务

retrieval、OCR、KB proxy 等服务不在本轮改造范围内。

## 后续计划

### 阶段 1：稳定 conversational 策略 A

目标：

- 验证 `consult_*` 在真实工具调用场景下的事件顺序。
- 补充异常场景：
  - 工具参数 JSON 不完整
  - 工具执行失败
  - 模型混合输出文本和工具调用
  - 用户中断 run
- 根据 UI 反馈调整工具活动展示密度。

### 阶段 2：扩大自然语言 worker 覆盖

候选：

- `rule_reply`
- 非 V2 的 `rule_asker`
- 其他 conversational worker

原则：

- 最终面向用户的自然语言阶段优先做 token streaming。
- 工具调用过程通过事件流暴露，但默认 UI 保持简洁。

### 阶段 3：单独设计 `rule_asker` V2

可选方案：

- 保持状态机模板回复，只增加阶段状态事件。
- 在 proposal 应用后，再增加一轮用户可见自然语言生成，并对这轮做 token streaming。

建议优先评估第二种，因为它更接近顶级产品的自然交互体验。

### 阶段 4：报告生成链路流式化

报告类不建议直接照搬 conversational streaming。更合理的是：

- 数据获取阶段：事件化展示进度。
- 结构化报告生成阶段：保持校验和归一化。
- 用户可见摘要/解读阶段：可增加 token streaming。

这样能兼顾报告正确性和响应体感。

## 风险点

- 工具事件暴露过多会增加 UI 噪音。
- 模型在同一轮中先输出文本再转工具调用时，需要避免误导用户。
- 对外协议扩展后，应补充自动化回归，避免前端只处理 `delta/final` 的旧逻辑被破坏。
