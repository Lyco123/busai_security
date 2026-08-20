# MCP 新增统计接口 Fixture 回归测试手册（2026-05-24）

日期：2026-05-24  
测试对象：新增 MCP 统计接口相关 fixture 回归用例。  
执行方式：优先使用自动化脚本；必要时用 Playwright 手动复核。  
测试目标：最少增加 3 个 fixture case，分别覆盖驾驶员不良行为、线路岗前检查、单位事故统计，确保系统路由到正确工具，并且回答中的核心统计来自工具结果。

---

## 1. 测试范围

本手册覆盖新增 fixture 的设计、落库位置、执行方式和判定口径。

最少新增 3 条回归用例：

| ID | 覆盖点 | 目标 MCP 工具 |
| --- | --- | --- |
| NS-DRV-001 | 驾驶员不良行为总数与排名 | `get_mcp_ods_odsJituanBsEmployee_getBehaviorStat` |
| NS-RTE-001 | 线路岗前检查统计 | `get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount` |
| NS-ORG-001 | 单位事故总数和事故描述 | `get_mcp_ods_odsJituanBsEmployee_getOrganAccident` |

---

## 2. 前置条件

- 测试脚本能读取新增 fixture 文件。
- AI 可在非正式报告问题中调用 MCP 查询工具，而不是强制进入 `generate_*_report`。

若上述条件未完成，本回归用例应标记为 `BLOCKED`，不能标记为通过。

---

## 3. 建议文件位置

新增 fixture 文件建议放在：

```text
agent/fixtures/mcp-new-stats-quality-cases-20260524.json
```

若复用现有 `assistant-reliability-cases.json`，需在用例 `category` 中标记：

```text
mcp_new_stats_quality
```

---

## 4. Fixture 字段规范

每条 case 至少包含：

```json
{
  "id": "NS-DRV-001",
  "category": "mcp_new_stats_quality",
  "title": "驾驶员不良行为统计必须来自 MCP",
  "turns": [
    "查一下任宇邦在 20251231 往前 30 天的不良驾驶行为总数和线路排名，直接给我统计结论，不要生成正式报告。"
  ],
  "expect": {
    "tool_in": ["consult_driver_expert", "consult_omni"],
    "mcp_tool_in": ["get_mcp_ods_odsJituanBsEmployee_getBehaviorStat"],
    "tool_not_in": ["generate_driver_report"],
    "must_include_any": ["任宇邦"],
    "must_not_include_any": ["无法确认但", "预计", "推测"],
    "grounded_fields": ["eventName", "eventNum", "ranking"]
  }
}
```

说明：

- `tool_in` 校验外层 `metadata.tool`，可允许专家工具或通用工具。
- `mcp_tool_in` 校验内部 MCP 工具调用，必须命中目标新增接口。
- `tool_not_in` 防止误进入正式报告生成链路。
- `grounded_fields` 用于人工或脚本核对回答是否引用了工具返回字段。

---

## 5. 最小用例设计

### NS-DRV-001 驾驶员不良行为统计

用户输入：

```text
查一下任宇邦在 20251231 往前 30 天的不良驾驶行为总数和线路排名，直接给我统计结论，不要生成正式报告。
```

预期：

- 外层工具允许 `consult_driver_expert` 或 `consult_omni`。
- 内部必须调用 `get_mcp_ods_odsJituanBsEmployee_getBehaviorStat`。
- 不得调用 `generate_driver_report`。
- 回答必须引用工具返回的行为名称、行为次数和排名。
- 不得出现未由工具返回支撑的“环比”“原因”“严重程度”等判断。

建议 expect：

```json
{
  "tool_in": ["consult_driver_expert", "consult_omni"],
  "tool_not_in": ["generate_driver_report"],
  "mcp_tool_in": ["get_mcp_ods_odsJituanBsEmployee_getBehaviorStat"],
  "grounded_fields": ["eventName", "eventNum", "ranking"]
}
```

### NS-RTE-001 线路岗前检查统计

用户输入：

```text
527路 20251231 的岗前检查情况怎么样？给出应测、实测、合格、不合格和完成率，不要生成正式线路报告。
```

预期：

- 外层工具允许 `consult_route_expert` 或 `consult_omni`。
- 内部必须调用 `get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount`。
- 不得调用 `generate_route_report`。
- 回答必须引用 `allCount/actualCount/qualifiedCount/unqualifiedCount/completePer/unqualifiedPer`。
- 若回答出现“达标/不达标”，必须能由工具返回或测试规则明确支持；否则只允许描述原始统计。

建议 expect：

```json
{
  "tool_in": ["consult_route_expert", "consult_omni"],
  "tool_not_in": ["generate_route_report"],
  "mcp_tool_in": ["get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount"],
  "grounded_fields": ["allCount", "actualCount", "qualifiedCount", "unqualifiedCount", "completePer", "unqualifiedPer"]
}
```

### NS-ORG-001 单位事故统计

用户输入：

```text
二巴公司 20251231 往前 30 天事故总数是多少？列出最近事故描述，不要生成正式单位报告。
```

预期：

- 外层工具允许 `consult_unit_expert` 或 `consult_omni`。
- 内部必须调用 `get_mcp_ods_odsJituanBsEmployee_getOrganAccident`。
- 不得调用 `generate_unit_report`。
- 回答必须引用 `accidentCount` 和 `accidentDescList`。
- 不得编造事故地点、责任、原因、整改措施。

建议 expect：

```json
{
  "tool_in": ["consult_unit_expert", "consult_omni"],
  "tool_not_in": ["generate_unit_report"],
  "mcp_tool_in": ["get_mcp_ods_odsJituanBsEmployee_getOrganAccident"],
  "grounded_fields": ["accidentCount", "accidentDescList"]
}
```

---

## 6. 建议 Fixture JSON

```json
[
  {
    "id": "NS-DRV-001",
    "category": "mcp_new_stats_quality",
    "title": "驾驶员不良行为统计必须来自 MCP",
    "turns": [
      "查一下任宇邦在 20251231 往前 30 天的不良驾驶行为总数和线路排名，直接给我统计结论，不要生成正式报告。"
    ],
    "expect": {
      "tool_in": ["consult_driver_expert", "consult_omni"],
      "tool_not_in": ["generate_driver_report"],
      "mcp_tool_in": ["get_mcp_ods_odsJituanBsEmployee_getBehaviorStat"],
      "grounded_fields": ["eventName", "eventNum", "ranking"]
    }
  },
  {
    "id": "NS-RTE-001",
    "category": "mcp_new_stats_quality",
    "title": "线路岗前检查统计必须来自 MCP",
    "turns": [
      "527路 20251231 的岗前检查情况怎么样？给出应测、实测、合格、不合格和完成率，不要生成正式线路报告。"
    ],
    "expect": {
      "tool_in": ["consult_route_expert", "consult_omni"],
      "tool_not_in": ["generate_route_report"],
      "mcp_tool_in": ["get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount"],
      "grounded_fields": ["allCount", "actualCount", "qualifiedCount", "unqualifiedCount", "completePer", "unqualifiedPer"]
    }
  },
  {
    "id": "NS-ORG-001",
    "category": "mcp_new_stats_quality",
    "title": "单位事故统计必须来自 MCP",
    "turns": [
      "二巴公司 20251231 往前 30 天事故总数是多少？列出最近事故描述，不要生成正式单位报告。"
    ],
    "expect": {
      "tool_in": ["consult_unit_expert", "consult_omni"],
      "tool_not_in": ["generate_unit_report"],
      "mcp_tool_in": ["get_mcp_ods_odsJituanBsEmployee_getOrganAccident"],
      "grounded_fields": ["accidentCount", "accidentDescList"]
    }
  }
]
```

---

## 7. 执行规范

| 项 | 要求 |
| --- | --- |
| 会话 | 每条 fixture 单独新建会话。 |
| 等待 | 每条消息发送后等待约 2 分钟。 |
| 记录 | 记录外层 `metadata.tool`、内部 MCP tool、最终回答摘要、失败原因。 |
| 数据核对 | 对 `grounded_fields` 中的字段逐项核对。 |
| 失败保留 | 失败时保留完整会话 ID、请求、响应、工具调用日志。 |

---

## 8. 自动化判定口径

脚本至少检查：

- `metadata.tool` 不在 `tool_not_in` 中。
- 若存在 `tool_in`，则 `metadata.tool` 必须命中。
- 内部工具调用列表必须包含 `mcp_tool_in` 中的目标工具。
- 最终回答不得出现原始工具泄漏，如裸 JSON tool call、无关 schema、代码块形式工具调用。
- 若可读取 MCP 返回，应检查 `grounded_fields` 对应值在最终回答中出现，或回答明确说明“未查到”。

人工复核补充检查：

- 回答是否把未返回字段写成事实。
- 回答是否把“未查到”解释为“0 次/无事故/全部合格”。
- 回答是否误生成正式报告。

---

## 9. 结果记录表

| ID | 输入摘要 | `metadata.tool` | MCP 工具命中 | 禁止工具是否触发 | 核心字段是否一致 | 结论 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NS-DRV-001 | 驾驶员不良行为 |  |  |  |  | 待执行 |  |
| NS-RTE-001 | 线路岗前检查 |  |  |  |  | 待执行 |  |
| NS-ORG-001 | 单位事故统计 |  |  |  |  | 待执行 |  |

---

## 10. 验收结论模板

```text
本轮新增 MCP 统计 fixture 回归共执行 3 条：
- NS-DRV-001: PASS / FAIL / BLOCKED
- NS-RTE-001: PASS / FAIL / BLOCKED
- NS-ORG-001: PASS / FAIL / BLOCKED

结论：
- 3 条全部 PASS，方可认为最小回归覆盖完成。
- 任一 FAIL，说明对应接口未被正确路由或回答未被工具结果约束。
- 任一 BLOCKED，说明系统整合前置条件不足，不能进入验收通过。
```
