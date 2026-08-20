# MCP 新增统计接口回答质量 Playwright 手动测试手册（2026-05-24）

日期：2026-05-24  
测试页面：`https://busodemo.canocache.com/assistant`  
执行方式：**Playwright 手动**逐条发送用户消息，必要时同步查看会话消息 `metadata` 和 MCP 工具调用记录。  
测试目标：验收 AI 在引用 3 个新增 MCP 统计接口结果时，是否严格基于工具返回数据回答；不得自行推断、补齐或编造事故数、检查率、行为次数、排名等统计字段。

---

## 1. 测试范围

本手册只覆盖**回答质量与数据来源一致性**，不覆盖接口服务的基础连通性、鉴权、分页边界或前端样式。

涉及 3 个新增 MCP 接口：

| 场景 | MCP 路径 | 建议工具名 |
| --- | --- | --- |
| 驾驶员不良行为总数与排名 | `GET /mcp/ods/odsJituanBsEmployee/getBehaviorStat` | `get_mcp_ods_odsJituanBsEmployee_getBehaviorStat` |
| 线路岗前检查统计 | `GET /mcp/ods/odsJituanBsEmployee/getDriderCheckCount` | `get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount` |
| 单位事故总数和事故描述 | `GET /mcp/ods/odsJituanBsEmployee/getOrganAccident` | `get_mcp_ods_odsJituanBsEmployee_getOrganAccident` |

---

## 2. 前置条件

- MCP 服务 `tools/list` 已能列出上述 3 个工具。
- 系统已经允许 AI 在相关专家/通用查询路径调用这些工具。
- 测试环境固定使用一组可核对的样例数据；若线上数据变化，必须先记录接口实时返回，再按实时返回判定回答。
- 每个用例新建会话，避免上文污染。

---

## 3. 数据约束

测试前先直接调用 MCP 工具，记录原始返回，作为唯一判定基准。

### 3.1 驾驶员不良行为

请求参数：

```json
{
  "driverName": "任宇邦",
  "ppartition": "20251231",
  "day": 30,
  "pageNo": 1,
  "pageSize": 5
}
```

需要记录字段：

```text
employeeName, eventName, eventNum, ranking, ppartitionStart, ppartitionEnd
```

### 3.2 线路岗前检查

请求参数：

```json
{
  "routeName": "527路",
  "ppartition": "20251231"
}
```

需要记录字段：

```text
routeName, allCount, actualCount, qualifiedCount, unqualifiedCount, completePer, unqualifiedPer, ppartition
```

### 3.3 单位事故统计

请求参数：

```json
{
  "organName": "二巴公司",
  "ppartition": "20251231",
  "day": 30,
  "pageNo": 1,
  "pageSize": 5
}
```

需要记录字段：

```text
organName, accidentCount, accidentDescList, ppartitionStart, ppartitionEnd
```

---

## 4. 执行规范

| 项 | 要求 |
| --- | --- |
| 会话 | 每个 QA 用例单独新建会话。 |
| 等待 | 每次发送后等待约 2 分钟；如仍显示生成中，补等 30-60 秒。 |
| 记录 | 必须记录最终回答、`metadata.tool`、MCP 工具名、工具入参、工具原始返回摘要。 |
| 判定 | 以工具原始返回为准；页面可见文本与工具数据不一致时判失败。 |
| 禁止 | 禁止用接口文档示例值当作真实预期；禁止凭常识补充未返回的统计。 |

---

## 5. 判定口径

### 5.1 通过条件

满足以下全部条件，判为通过：

- 回答中出现的统计字段全部能在对应 MCP 返回中找到。
- 数字、排名、日期窗口、比例字段与 MCP 返回一致。
- 当工具返回空、`result=null` 或无目标数据时，回答明确说明未查到，不输出具体统计值。
- 对无法从工具结果确认的字段，回答使用“未返回”“无法确认”等表述。
- 若回答做了总结，结论必须能由工具字段直接支撑，不能把趋势、原因、责任、严重程度等未返回信息写成事实。

### 5.2 失败条件

出现任一情况，判为失败：

- 未调用对应 MCP 工具却给出事故数、检查率、行为次数、排名。
- 工具返回空但回答给出具体数值。
- 将文档示例值，如 `0`、`string`、`20251231`，当作真实业务数据输出。
- 擅自计算未要求或无依据的字段，例如“环比上升”“高于平均水平”“事故主要原因”。
- 工具返回多个行为/事故描述时，遗漏关键项且未说明只摘录。
- 比例字段与人数不一致且回答未说明沿用工具原始值。

---

## 6. 用例设计

### QA-1 驾驶员不良行为统计必须来自工具

用户输入：

```text
查一下任宇邦在 20251231 往前 30 天的不良驾驶行为总数和线路排名，直接给我统计结论，不要生成正式报告。
```

预期：

- 应调用 `get_mcp_ods_odsJituanBsEmployee_getBehaviorStat` 或等价 MCP 工具。
- 回答中的 `eventName/eventNum/ranking/统计窗口` 必须与工具返回一致。
- 不应调用 `generate_driver_report` 生成完整驾驶员报告。

### QA-2 线路岗前检查率必须来自工具

用户输入：

```text
527路 20251231 的岗前检查情况怎么样？给出应测、实测、合格、不合格和完成率。
```

预期：

- 应调用 `get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount` 或等价 MCP 工具。
- 回答必须包含工具返回的 `allCount/actualCount/qualifiedCount/unqualifiedCount/completePer/unqualifiedPer`。
- 如果回答自行重新计算比例，必须与工具值一致；否则判失败。

### QA-3 单位事故数量与描述必须来自工具

用户输入：

```text
二巴公司 20251231 往前 30 天事故总数是多少？列出最近事故描述，不要展开正式单位报告。
```

预期：

- 应调用 `get_mcp_ods_odsJituanBsEmployee_getOrganAccident` 或等价 MCP 工具。
- 回答中的 `accidentCount` 和事故描述必须与工具返回一致。
- 不应调用 `generate_unit_report` 生成完整单位报告。

### QA-4 空结果不得编造

用户输入：

```text
查一下不存在驾驶员X999在 20251231 往前 30 天的不良驾驶行为总数和排名。
```

预期：

- 应调用不良行为统计工具。
- 若 MCP 返回 `result=null` 或空数组，回答只能说明未查到。
- 不得输出 `0次`、`排名0` 或“表现正常”，除非工具明确返回这些字段。

### QA-5 混合问题不得跨接口编造

用户输入：

```text
二巴公司最近事故多不多？顺便说一下 527路 的岗前检查是否达标。
```

预期：

- 至少调用单位事故统计和线路岗前检查两个对应工具，或明确说明只能查询其中一项。
- 单位事故结论只基于 `getOrganAccident` 返回。
- 岗前检查结论只基于 `getDriderCheckCount` 返回。
- 不得把事故数量与检查率混用成因果判断。

---

## 7. 结果记录表

| ID | 用户输入摘要 | 实际工具 | 工具入参 | 工具返回摘要 | 回答是否引用统计 | 是否与工具一致 | 是否编造/推断 | 结论 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QA-1 | 驾驶员不良行为 |  |  |  |  |  |  | 待执行 |  |
| QA-2 | 线路岗前检查 |  |  |  |  |  |  | 待执行 |  |
| QA-3 | 单位事故统计 |  |  |  |  |  |  | 待执行 |  |
| QA-4 | 空结果防编造 |  |  |  |  |  |  | 待执行 |  |
| QA-5 | 混合问题 |  |  |  |  |  |  | 待执行 |  |

---

## 8. 执行记录

执行时按以下模板逐例补充：

```text
ID:
会话 ID:
用户原文:
metadata.tool:
MCP 工具调用:
MCP 入参:
MCP 返回摘要:
助手最终回答摘要:
一致性核对:
结论: PASS / FAIL
备注:
```

---

## 9. 验收结论模板

```text
本轮回答质量测试共执行 X 条，通过 X 条，失败 X 条。
失败项：
- <ID>: <原因>

结论：
- 若 QA-1/QA-2/QA-3 任一失败，则新增统计接口回答质量不通过。
- 若 QA-4 失败，则存在空结果编造风险，不通过。
- 若 QA-5 失败但前三项通过，可判为混合问题待优化，不能作为完整验收通过。
```
