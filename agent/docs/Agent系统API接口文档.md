# Agent系统 API 接口文档

> **版本**：v1.11  
> **最后更新**：2026-06-09  
> **适用范围**：Agent 智能助手系统（按当前后端实现对齐）

## 文档概述

本文档基于当前后端实现，补全接口调用参数、默认值、响应结构和权限约束，可直接用于联调。

### 主要功能模块

| 模块           | 主要功能                                     | 适用场景                                 |
| -------------- | -------------------------------------------- | ---------------------------------------- |
| **认证授权**   | 匿名态/登录态识别、登录登出、会话隔离        | 用户身份与权限控制                       |
| **会话与对话** | 会话管理、普通对话、流式对话、无会话报告生成 | 用户与 AI 助手交互、页面按钮直接生成报告 |
| **规则管理**   | 规则增删改查、向量匹配、效果测试             | 规则运营与验证                           |
| **规则配置**   | 草稿会话、测试、确认保存、取消               | 对话式规则配置                           |
| **场景管理**   | 工作场景配置、向量更新                       | 路由场景维护                             |
| **数据统计**   | AB 路由统计                                  | 路由效果分析                             |
| **研究评估**   | Eval/Issue 管理、看板与筛选                  | 质检与问题闭环（管理员）                 |
| **知识库代理** | KB 接口转发                                  | 检索与文档管理（登录用户）               |

### 访问说明

- **API 前缀**：`/api/agent`
- **数据格式**：JSON（UTF-8），流式接口为 SSE（`text/event-stream`）
- **时间格式**：ISO 8601
- **认证方式**：Cookie（`bus_anon_id`（匿名用户标识）、`bus_auth_token`）
- **数据隔离**：按 `principal_id` 隔离数据，匿名态与登录态可见范围不同
- **权限要点**：
  - `/research/*` 仅管理员可访问（非管理员返回 `403`）
  - `/kb/*` 需要登录；写操作还要求管理员

## 1. 技术规范

| 项目       | 说明                                     |
| ---------- | ---------------------------------------- |
| API 前缀   | `/api/agent`                             |
| 数据格式   | JSON（UTF-8）                            |
| 流式协议   | SSE（`Content-Type: text/event-stream`） |
| 认证方式   | Cookie-based                             |
| 分页默认值 | `page=1`、`pageSize=20`                  |
| 分页上限   | `pageSize<=100`                          |

### 1.1 响应格式约定（当前实现）

系统存在以下响应风格，具体以接口说明为准：

1. 直接返回对象/数组（例如：`GET /sessions`、`POST /chat`）。
2. `{"data": ...}` 包装（例如：`/auth/*`、`/rules/*`、`/scenarios/*`、`/research/*`）。
3. `{"success": true/false, "data": ..., "error": "..."}`（主要用于工具型返回，如规则匹配/测试）。

### 1.2 枚举与默认值

| 项目                   | 取值                                                            |
| ---------------------- | --------------------------------------------------------------- |
| `ab_test.experiment`   | `vehicle_expert_cot`                                            |
| `ab_test.group`        | `X` / `Y`（盲测组标签）                                         |
| `ab_test.variant`      | `baseline` / `cot_enabled`（当前实验显示名）                    |
| `ab_test.routing_mode` | 固定为 `router_decide`                                          |
| 评估结论 `conclusion`  | `pass` / `warning` / `fail`                                     |
| 问题严重度 `severity`  | `low` / `medium` / `high` / `critical`                          |
| 问题优先级 `priority`  | `p0` / `p1` / `p2` / `p3`                                       |
| 问题状态 `status`      | `pending_confirm` / `in_progress` / `pending_verify` / `closed` |
| 提交方式 `submit_mode` | `quick` / `full`                                                |
| 规则匹配阈值           | `0.7`（用于 `high_score_hit` 等判定）                           |
| `rules/match` 默认参数 | `top_k=5`、`min_score=0.3`，`top_k` 范围 `1-20`                 |

### 1.3 MCP 运行配置

| 环境变量                                          | 必填 | 说明                                                                                                                                                                                                                                                                |
| ------------------------------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MCP_SERVER_URL`                                  | 是   | MCP 服务地址；配置后 Agent 优先通过 MCP 调用画像、报告、统计等工具                                                                                                                                                                                                  |
| `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` | 否   | Cloudflare Access 访问 MCP 网关时使用                                                                                                                                                                                                                               |
| `MCP_ACCESS_TOKEN`                                | 是   | 业务侧 `X-Access-Token` 的兜底值；Agent 调用 MCP 的所有链路优先使用客户端请求头 `X-Access-Token`（经 `withRequestAccessTokenEnv` 覆盖 `env.MCP_ACCESS_TOKEN`），客户端未传时回退到该环境变量；开发/测试默认值可配置在 `wrangler.toml`，生产或客户环境建议用密钥覆盖 |

> `wrangler.toml` 可保留开发/测试默认 token；生产或客户环境使用 `wrangler secret put MCP_ACCESS_TOKEN` 等密钥方式覆盖，避免把生产 token 写入仓库或公开配置文件。覆盖优先级：客户端请求头 `X-Access-Token` > `wrangler.toml` / secret 环境变量 `MCP_ACCESS_TOKEN`。

## 2. 认证与访问

### 2.1 Cookie 说明

| Cookie 名称      | 用途         | 说明                              |
| ---------------- | ------------ | --------------------------------- |
| `bus_anon_id`    | 匿名用户标识 |                                   |
| `bus_auth_token` | 登录态令牌   | 登录成功后设置，默认有效期约 7 天 |

### 2.2 权限矩阵

| 路径范围                                                                                                                       | 访问要求                                         |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ |
| `/health`、`/auth/*`、`/sessions*`、`/chat*`、`/reports/summary*`、`/rules*`、`/rule-config*`、`/scenarios*`、`/ab-test/stats` | 匿名或登录态                                     |
| `/research/*`                                                                                                                  | 管理员                                           |
| `/kb/*`                                                                                                                        | **全部需管理员**（非管理员或未登录均返回 `403`） |

## 3. API 接口清单（实现对齐）

### 3.1 基础与认证

#### `GET /health`

- 用途：健康检查
- 响应示例：

```json
{
  "status": "ok",
  "timestamp": "2026-03-03T12:00:00.000Z"
}
```

#### `GET /auth/me`

- 用途：获取当前身份（匿名/登录）
- 响应示例：

```json
{
  "data": {
    "role": "anon",
    "is_authenticated": false,
    "principal_id": "anon:anon_xxx",
    "anon_id": "anon_xxx",
    "user": null
  }
}
```

#### `POST /auth/login`

- 请求体：

| 字段       | 类型   | 必填 | 说明   |
| ---------- | ------ | ---- | ------ |
| `username` | string | 是   | 用户名 |
| `password` | string | 是   | 密码   |

- 响应：`{ data: { role, is_authenticated, principal_id, anon_id, user } }`
- 常见错误：
  - `400`：缺少用户名或密码
  - `401`：用户名或密码错误

#### `POST /auth/logout`

- 用途：清除登录态（幂等）
- 响应：`{ data: { role: "anon", is_authenticated: false, ... } }`

### 3.2 会话与对话

#### 3.2.1 `GET /sessions`

- Query 参数：

| 参数                  | 类型    | 必填 | 默认值  | 说明                                           |
| --------------------- | ------- | ---- | ------- | ---------------------------------------------- |
| `include_rule_config` | boolean | 否   | `false` | `false` 时过滤掉仍处于规则草稿会话中的 session |

- 响应：会话数组

```json
[
  {
    "id": "session_001",
    "title": "驾驶员风险分析",
    "preview": "分析张三的驾驶风险等级...",
    "updatedAt": "2026-03-03T12:00:00.000Z"
  }
]
```

#### 3.2.2 `POST /sessions`

- 请求体：

| 字段    | 类型   | 必填 | 默认值   | 说明     |
| ------- | ------ | ---- | -------- | -------- |
| `title` | string | 否   | `新会话` | 会话标题 |

- 响应：`AgentSessionDetail`（含空 `messages`）

#### 3.2.3 `GET /sessions/{sessionId}`

- 响应：`AgentSessionDetail`

```json
{
  "id": "session_001",
  "title": "驾驶员风险分析",
  "preview": "...",
  "updatedAt": "2026-03-03T12:00:00.000Z",
  "messages": [
    {
      "id": "msg_001",
      "role": "assistant",
      "content": "...",
      "createdAt": "2026-03-03T12:00:01.000Z",
      "status": "complete",
      "metadata": {}
    }
  ]
}
```

#### 3.2.4 `PATCH /sessions/{sessionId}`

- 请求体：

| 字段    | 类型   | 必填 | 说明               |
| ------- | ------ | ---- | ------------------ |
| `title` | string | 是   | 新标题，空值会报错 |

- 响应：`{ "success": true, "title": "..." }`

#### 3.2.5 `DELETE /sessions/{sessionId}`

- 响应：`{ "success": true }`

#### 3.2.6 `POST /chat`

- 请求体：

| 字段        | 类型   | 必填 | 说明                                   |
| ----------- | ------ | ---- | -------------------------------------- |
| `sessionId` | string | 是   | 会话 ID                                |
| `content`   | string | 是   | 当前用户输入                           |
| `messages`  | array  | 否   | 历史消息，元素结构 `{ role, content }` |

- 说明：当前实验分桶由服务端按会话自动分配，不再接收手工分组参数。
- 响应：助手消息对象

```json
{
  "role": "assistant",
  "content": "...",
  "metadata": {
    "tool": "consult_vehicle_expert",
    "iterations": 2,
    "rule_match": {
      "ok": true,
      "total_matched": 1,
      "top": {
        "rule_id": "rule_xxx",
        "rule_name": "规则名",
        "score": 0.35
      }
    },
    "scenario": {
      "matched": true,
      "method": "vector",
      "candidates_count": 12
    },
    "ab_test": {
      "experiment": "vehicle_expert_cot",
      "group": "Y",
      "variant": "cot_enabled",
      "locked": true,
      "source": "session_bound",
      "routing_mode": "router_decide",
      "top_score": 0.359,
      "high_score_hit": false,
      "selected_tool": "consult_vehicle_expert",
      "selected_rule_id": null,
      "rule_exit_fallback": false,
      "skip_rule_id": null
    },
    "llm": {
      "agent": "vehicle_expert",
      "cot_enabled": true
    }
  }
}
```

- 消息来源补充说明：
  - 只要后端在 MCP、结构化查询、后续 RAG 引用等链路中拿到了可透传的来源信息，都应返回在消息级字段 `sources` 中。
  - `sources` 属于稳定业务字段，不属于消息级 `metadata`。
  - 前端如果要渲染来源入口，应读取 `sources`，不要依赖 `metadata`。
  - `sources` 固定为数组；没有来源时返回 `[]`，不要返回 `null`。

- 消息级 `sources` 示例：

```json
{
  "role": "assistant",
  "content": "...",
  "sources": [
    {
      "type": "mcp",
      "path": "/bus/profile",
      "path_args": {
        "partition": "20251221",
        "numberplate": "粤A09272D"
      }
    }
  ]
}
```

- `sources[]` 字段说明：

| 字段        | 类型   | 必填 | 说明                                               |
| ----------- | ------ | ---- | -------------------------------------------------- |
| `type`      | string | 是   | 来源类型，例如 `mcp`；后续也可能扩展 `rag_file` 等 |
| `path`      | string | 是   | 来源路径，例如 `/bus/profile`                      |
| `path_args` | object | 否   | 路径参数对象，前端可据此生成跳转链接或查询参数     |

#### 3.2.7 `POST /chat/stream`

- 请求体：与 `/chat` 相同
- 协议：SSE（每帧以 `data: ...` 开头，空行分隔）
- 事件流：
  - `start`
  - `delta`：`{ "type":"delta","delta":"..." }`
  - `final`：`{ "type":"final","message": AgentMessage }`
  - `error`：`{ "type":"error","error":"..." }`
  - 结束帧：`data: [DONE]`

#### 3.2.8 `POST /reports/summary`

- 用途：页面点击“生成报告/生成总结”按钮时，直接生成 5 类对象报告。
- 完整路径：`POST /api/agent/reports/summary`
- 兼容路径：`POST /api/agent/reports/summary/{type}`
- 会话行为：
  - 请求体不需要、也不建议传 `sessionId`。
  - 后端不会创建 `agent_sessions`。
  - 后端不会写入 `agent_messages`。
  - 后端根据入参定位对象，复用现有报告 worker 生成结果并直接返回。

- 请求体：

| 字段                                              | 类型   | 必填 | 说明                                                                                                                        |
| ------------------------------------------------- | ------ | ---- | --------------------------------------------------------------------------------------------------------------------------- |
| `driverName` / `driver_name`                      | string | 否   | 驾驶员名称；传该字段时生成驾驶员报告                                                                                        |
| `numberPlate`                                     | string | 否   | 车牌号；传该字段时生成车辆报告                                                                                              |
| `organName` / `organ_name`                        | string | 否   | 单位名称；传该字段时生成单位报告                                                                                            |
| `routeName` / `route_name`                        | string | 否   | 线路名称；传该字段时生成线路报告                                                                                            |
| `stationName` / `station_name` / `busStationName` | string | 否   | 站场名称；传该字段时生成站场报告                                                                                            |
| `driverName` / `driver_name` + `type=accident`    | string | 否   | 事故调查报告当前按肇事驾驶员姓名定位；生成事故报告时必须显式指定事故类型，避免与驾驶员报告歧义                              |
| `accidentDate` / `accident_date`                  | string | 否   | 事故报告专用事故发生时间，格式 `yyyyMMddHHmmss`，例如 `20251231050505`；生成事故报告时必填，并会作为事故查询参数传入 worker |
| `ppartition` / `partition`                        | string | 否   | 数据日期分区，格式 `yyyyMMdd`；仅用于驾驶员、车辆、单位、线路、站场报告并透传到画像查询；事故调查报告不再使用该字段         |
| `type` / `reportType` / `tool`                    | string | 否   | 显式指定报告类型；使用通用 `id/name` 字段或路径 `{type}` 时使用                                                             |
| `id` / `name` / `nameOrId` / `entityId`           | string | 否   | 通用对象标识；使用时必须同时指定 `type`、`reportType`、`tool` 或路径 `{type}`                                               |

> 目标字段互斥：未显式指定 `type` / `reportType` / `tool` 或路径 `{type}` 时，`driverName`、`numberPlate`、`organName`、`routeName`、`stationName` / `station_name` / `busStationName` 只能传其中一类。若同时传入多类目标字段，接口返回 `ambiguous report target parameters`。`driverName` 默认识别为驾驶员报告；事故调查报告必须显式指定事故类型。

> 说明：当前专用接口层尚未按 `incidentId` / `incident_id` 直接查询事故。事故调查报告的可用路径是显式指定 `type=accident`、`reportType=accident`、`tool=generate_accident_investigation_report` 或路径 `/reports/summary/accident`，并提供肇事驾驶员姓名和 `accidentDate`。

- 自动识别规则：

| 入参字段                                          | 报告类型     | 内部 worker                              |
| ------------------------------------------------- | ------------ | ---------------------------------------- |
| `driverName` / `driver_name`                      | 驾驶员报告   | `generate_driver_report`                 |
| `numberPlate`                                     | 车辆报告     | `generate_vehicle_report`                |
| `organName` / `organ_name`                        | 单位报告     | `generate_unit_report`                   |
| `routeName` / `route_name`                        | 线路报告     | `generate_route_report`                  |
| `stationName` / `station_name` / `busStationName` | 站场报告     | `generate_station_report`                |
| 显式事故类型 + `driverName` / `driver_name`       | 事故调查报告 | `generate_accident_investigation_report` |

- 支持的显式类型值：

| 类型值                                                           | 报告类型     |
| ---------------------------------------------------------------- | ------------ |
| `driver`、`generate_driver_report`                               | 驾驶员报告   |
| `vehicle`、`bus`、`generate_vehicle_report`                      | 车辆报告     |
| `unit`、`company`、`generate_unit_report`                        | 单位报告     |
| `route`、`line`、`generate_route_report`                         | 线路报告     |
| `station`、`bus_station`、`generate_station_report`              | 站场报告     |
| `accident`、`incident`、`generate_accident_investigation_report` | 事故调查报告 |

- 推荐调用示例：

```json
{ "driverName": "任宇邦", "ppartition": "20260106" }
```

```json
{ "numberPlate": "粤A02650D", "ppartition": "20260106" }
```

```json
{ "organName": "二巴公司", "ppartition": "20251221" }
```

```json
{ "routeName": "527", "ppartition": "20260503" }
```

```json
{ "busStationName": "303太古仓路总站", "ppartition": "20260531" }
```

```json
{
  "type": "accident",
  "driverName": "龚永添",
  "accidentDate": "20251014083000"
}
```

或使用兼容路径：

```http
POST /api/agent/reports/summary/accident
```

```json
{
  "driverName": "龚永添",
  "accidentDate": "20251014083000"
}
```

- 通用字段调用示例：

```json
{
  "type": "vehicle",
  "id": "粤A02650D",
  "ppartition": "20251221"
}
```

事故报告也支持通用字段，但仍表示肇事驾驶员姓名，不表示事故 ID：

```json
{
  "type": "accident",
  "id": "龚永添",
  "accidentDate": "20251014083000"
}
```

- 事故调查报告当前完成度（按当前实现）：
  - 专用接口已接入 `generate_accident_investigation_report` worker。
  - 入参解析已支持 `type/reportType/tool=accident|incident|generate_accident_investigation_report` 与 `/reports/summary/{type}`。
  - 数据定位使用 `driverName` / `driver_name` / 通用 `id/name/nameOrId/entityId` + `accidentDate` / `accident_date`，事故时间格式为 `yyyyMMddHHmmss`。
  - 后端会通过 `get_mcp_ods_odsJituanBsEmployee_getAccidentList` 查询事故案例，并补充驾驶员事故统计、单位事故统计、驾驶员/线路/车辆整改建议等可用数据。
  - 输出归一为 `report_type=accident_investigation_summary`、`template_version=20260415`，包含 `layout`、`basic`、`section_1` 至 `section_4`、`trigger_analysis`、`appendix`。
  - 未命中事故数据时返回事故报告链路错误，不生成占位报告；当前错误语义包含 `incident_not_found`、`accident_report_format_mismatch`。
  - 当前限制：专用接口未实现 `incidentId` / `incident_id` 直查；若同名驾驶员同一事故时间存在多条事故，需依赖底层 MCP 返回的命中结果，接口层没有单独的事故 ID disambiguation。

- 响应：与 `/chat` 非流式 assistant reply 对齐。

```json
{
  "role": "assistant",
  "content": "{...结构化报告 JSON 或格式化后的报告内容...}",
  "sources": [],
  "metadata": {
    "tool": "generate_vehicle_report"
  },
  "tools": []
}
```

- 常见错误：
  - `400`：没有传目标字段。
  - `400`：同时传入多个目标字段，且没有显式 `type` / `reportType` / `tool`。
  - `400`：使用通用 `id/name/nameOrId/entityId` 但没有指定报告类型。
  - `400`：事故报告缺少 `accidentDate`，或格式不是 `yyyyMMddHHmmss`。
  - `400`：显式类型不在支持列表内。
  - 报告内容错误：当 worker 已查询到数据但最终结构化 JSON 未通过模板校验时，`content` 可能返回 `{ "error": "..._report_format_mismatch" }`；站场报告对应 `station_report_format_mismatch`。该错误表示报告生成格式不符合模板，不表示 `busStationName` / `ppartition` 参数未传到或站场画像未命中。

### 3.3 车辆专家 CoT 开关统计

#### `GET /ab-test/stats`

- 响应：

```json
{
  "data": {
    "experiment": "vehicle_expert_cot",
    "title": "车辆专家 CoT 开关统计",
    "groups": ["baseline", "cot_enabled"],
    "sample_turns": 120,
    "sample_sessions": 35,
    "metrics": [
      { "key": "turns", "label": "轮次", "values": { "baseline": 58, "cot_enabled": 62 } },
      {
        "key": "omni_selected",
        "label": "`consult_omni` 选择",
        "values": { "baseline": 12, "cot_enabled": 8 }
      },
      {
        "key": "vehicle_expert_selected",
        "label": "车辆专家选择",
        "values": { "baseline": 28, "cot_enabled": 30 }
      },
      {
        "key": "rule_reply_selected",
        "label": "`rule_reply` 选择",
        "values": { "baseline": 2, "cot_enabled": 2 }
      },
      {
        "key": "report_selected",
        "label": "报告链路选择",
        "values": { "baseline": 8, "cot_enabled": 8 }
      },
      {
        "key": "other_selected",
        "label": "其他链路处理",
        "values": { "baseline": 8, "cot_enabled": 14 }
      }
    ],
    "updated_at": "2026-03-03T12:00:00.000Z"
  }
}
```

- 说明：
  - `metrics` 为可扩展指标数组，后续切换实验时可复用同一统计结构
  - 当前默认统计 `ab_test.experiment === "vehicle_expert_cot"` 的数据
  - 会话页中的实验分组展示以服务端写入的 `ab_test.group` / `ab_test.variant` 为准，前端不再手动指定分组

### 3.4 规则管理

规则对象字段：

| 字段         | 类型    | 说明     |
| ------------ | ------- | -------- |
| `id`         | string  | 规则 ID  |
| `name`       | string  | 规则名   |
| `match_text` | string  | 匹配文本 |
| `enabled`    | boolean | 是否启用 |
| `priority`   | number  | 优先级   |
| `version`    | number  | 版本     |
| `data`       | object  | 规则数据 |
| `created_at` | string  | 创建时间 |
| `updated_at` | string  | 更新时间 |

#### `GET /rules`

- Query 参数：

| 参数               | 类型    | 必填 | 默认值  | 说明             |
| ------------------ | ------- | ---- | ------- | ---------------- |
| `include_disabled` | boolean | 否   | `false` | 是否包含禁用规则 |

- 响应：`{ data: Rule[] }`

#### `POST /rules`

- 请求体：

| 字段         | 类型    | 必填 | 说明                          |
| ------------ | ------- | ---- | ----------------------------- |
| `name`       | string  | 是   | 规则名称                      |
| `match_text` | string  | 是   | 匹配文本                      |
| `data`       | object  | 是   | 规则数据                      |
| `id`         | string  | 否   | 自定义规则 ID，不传则自动生成 |
| `enabled`    | boolean | 否   | 是否启用（默认 true）         |
| `priority`   | number  | 否   | 优先级（默认 50）             |
| `version`    | number  | 否   | 版本（默认 1）                |

- 响应：`{ data: Rule, embedding_status: "ok"|"skipped" }`

#### `GET /rules/{id}`

- 响应：`{ data: Rule }`
- 错误：`404`

#### `PUT /rules/{id}`

- 用途：部分更新（未传字段保持不变）
- 请求体：

| 字段                | 类型    | 必填 | 说明             |
| ------------------- | ------- | ---- | ---------------- |
| `name`              | string  | 否   | 规则名称         |
| `match_text`        | string  | 否   | 匹配文本         |
| `enabled`           | boolean | 否   | 是否启用         |
| `priority`          | number  | 否   | 优先级           |
| `version`           | number  | 否   | 版本             |
| `data`              | object  | 否   | 规则数据         |
| `refresh_embedding` | boolean | 否   | 是否强制刷新向量 |

- 响应：`{ data: Rule, embedding_status: "ok"|"skipped" }`
- 错误：`404`

#### `DELETE /rules/{id}`

- 响应：`{ "success": true }`

#### `POST /rules/match`

- 请求体：

| 字段        | 类型   | 必填 | 默认值 | 说明                  |
| ----------- | ------ | ---- | ------ | --------------------- |
| `query`     | string | 是   | -      | 查询文本              |
| `top_k`     | number | 否   | `5`    | 返回条数，范围 `1-20` |
| `min_score` | number | 否   | `0.3`  | 最低相似度阈值        |

- 响应：

```json
{
  "success": true,
  "data": {
    "query": "车祸怎么处理",
    "matches": [
      {
        "rule_id": "rule_xxx",
        "rule_name": "车祸相关问题回答规范",
        "score": 0.81,
        "metadata": {
          "match_text": "车祸怎么处理",
          "tone": "professional"
        }
      }
    ],
    "total_matched": 1,
    "top_k": 5
  }
}
```

#### `POST /rules/{id}/test`

- 请求体：

| 字段            | 类型     | 必填 | 默认值       | 说明             |
| --------------- | -------- | ---- | ------------ | ---------------- |
| `queries`       | string[] | 否   | 自动建议样本 | 待测问题列表     |
| `top_k`         | number   | 否   | `5`          | 对比返回条数     |
| `min_score`     | number   | 否   | `0.3`        | 最低阈值         |
| `preview_reply` | boolean  | 否   | `true`       | 是否生成回复预览 |

- 响应：`ToolResult`，`data` 为 `RuleDraftTestResponse`

#### `POST /rules/{id}/refresh_embedding`

- 请求体：无
- 响应：`{ "embedding_status": "ok" | "skipped" }`

### 3.5 规则配置

#### `POST /rule-config/session`

- 请求体：

| 字段        | 类型   | 必填 | 说明                        |
| ----------- | ------ | ---- | --------------------------- |
| `sessionId` | string | 否   | 已有会话 ID，不传则新建会话 |
| `rule_id`   | string | 否   | 指定规则进入编辑模式        |

- 响应：`{ session_id, draft }`

#### `POST /rule-config/{sessionId}/test`

- 请求体：同 `POST /rules/{id}/test`
- 响应：`ToolResult`，`data` 为 `RuleDraftTestResponse`

#### `POST /rule-config/{sessionId}/confirm`

- 请求体：

| 字段         | 类型    | 必填 | 默认值  | 说明                 |
| ------------ | ------- | ---- | ------- | -------------------- |
| `force_save` | boolean | 否   | `false` | 有冲突时是否强制保存 |

- 响应字段：

| 字段       | 类型   | 说明                                           |
| ---------- | ------ | ---------------------------------------------- |
| `status`   | string | `collecting` / `blocked` / `ready_for_confirm` |
| `rule_id`  | string | 保存成功后的规则 ID                            |
| `conflict` | object | 冲突信息（如有）                               |
| `message`  | string | 提示信息                                       |

#### `POST /rule-config/{sessionId}/cancel`

- 请求体：无
- 响应：`{ "success": true }`

### 3.6 场景管理

场景对象字段：

| 字段          | 类型     | 说明     |
| ------------- | -------- | -------- |
| `id`          | string   | 场景 ID  |
| `name`        | string   | 场景名   |
| `description` | string   | 描述     |
| `keywords`    | string[] | 关键词   |
| `enabled`     | boolean  | 是否启用 |
| `created_at`  | string   | 创建时间 |
| `updated_at`  | string   | 更新时间 |

#### `GET /scenarios`

- Query 参数：

| 参数               | 类型    | 必填 | 默认值  | 说明             |
| ------------------ | ------- | ---- | ------- | ---------------- |
| `include_disabled` | boolean | 否   | `false` | 是否包含禁用场景 |

- 响应：`{ data: Scenario[] }`

#### `POST /scenarios`

- 请求体：

| 字段          | 类型     | 必填 | 说明                    |
| ------------- | -------- | ---- | ----------------------- |
| `name`        | string   | 是   | 场景名                  |
| `description` | string   | 是   | 场景描述                |
| `id`          | string   | 否   | 自定义 ID，不传自动生成 |
| `keywords`    | string[] | 否   | 关键词                  |
| `enabled`     | boolean  | 否   | 是否启用（默认 true）   |

- 响应：`{ data: Scenario, embedding_status: "ok"|"skipped" }`

#### `GET /scenarios/{id}`

- 响应：`{ data: Scenario }`
- 错误：`404`

#### `PUT /scenarios/{id}`

- 请求体（至少传一个字段）：

| 字段                | 类型     | 必填 | 说明         |
| ------------------- | -------- | ---- | ------------ |
| `name`              | string   | 否   | 场景名       |
| `description`       | string   | 否   | 场景描述     |
| `keywords`          | string[] | 否   | 关键词       |
| `enabled`           | boolean  | 否   | 启用状态     |
| `refresh_embedding` | boolean  | 否   | 强制刷新向量 |

- 响应：`{ data: Scenario, embedding_status: "ok"|"skipped" }`
- 错误：`400`（参数缺失或类型错误）、`404`

#### `DELETE /scenarios/{id}`

- 响应：`{ "success": true }`

### 3.7 研究评估接口（`/research/*`，管理员）

> 权限：管理员。非管理员访问返回 `403`。

#### 3.7.1 通用筛选参数（`overview/evals/issues`）

| 参数                                         | 类型    | 说明                                                          |
| -------------------------------------------- | ------- | ------------------------------------------------------------- |
| `from` / `to`                                | string  | 时间范围（ISO 8601）                                          |
| `modelVersion`                               | string  | 模型版本                                                      |
| `scenario`                                   | string  | 场景                                                          |
| `orgGroup/orgCompany/orgFleet/orgLine`       | string  | 组织维度                                                      |
| `issueTypeIds` / `issueTypeId` / `issueType` | string  | 问题类型筛选（支持逗号分隔）                                  |
| `issueTypeMode`                              | string  | `any` / `all`（默认 `any`）                                   |
| `severity`                                   | string  | `low/medium/high/critical`（issues）                          |
| `priority`                                   | string  | `p0/p1/p2/p3`（issues）                                       |
| `status`                                     | string  | `pending_confirm/in_progress/pending_verify/closed`（issues） |
| `assignee`                                   | string  | 处理人（issues）                                              |
| `conclusion`                                 | string  | `pass/warning/fail`（evals）                                  |
| `isRead` / `isFavorite`                      | boolean | 评估状态筛选（evals）                                         |
| `keyword`                                    | string  | 关键词检索                                                    |
| `page` / `pageSize`                          | number  | 分页，默认 `1/20`，`pageSize<=100`                            |
| `sortBy` / `sortOrder`                       | string  | 排序字段与方向（`asc/desc`）                                  |

#### `GET /research/options`

- 响应：筛选项集合（模型、场景、组织、问题类型、处理人及各枚举值）

#### `GET /research/issue-types`

- Query 参数：`include_disabled`、`include_merged`、`keyword`
- 响应：`{ data: IssueType[] }`

#### `POST /research/issue-types`

- 请求体：`{ name, created_by? }`，`name` 必填
- 响应：`{ data: IssueType }`

#### `PATCH /research/issue-types/{id}`

- 请求体：`{ name?, enabled?, updated_by? }`
- 响应：`{ data: IssueType }`

#### `POST /research/issue-types/merge`

- 请求体：
  - `target_type_id`（必填）
  - `source_type_ids`（必填，数组）
  - `operator?`、`note?`
- 响应：`{ data: ... }`

#### `GET /research/overview`

- Query：使用“通用筛选参数”
- 响应：`{ data: { kpi, trend, issue_type_distribution_*, scenario_distribution, model_distribution, risk_hotspots, updated_at }, meta? }`

#### `GET /research/evals`

- Query：使用“通用筛选参数”
- 可排序字段：`created_at`、`updated_at`、`confidence`
- 响应：`{ data: { items, total, page, pageSize }, meta? }`

#### `POST /research/evals`

- 请求体：
  - 必填：`session_id` 或 `sessionId`
  - 可选：`conclusion`、`issue_type_ids`、`new_issue_type_names`、`confidence`、`note`、`tags`
  - 可选：`model_version`、`scenario`、`org_group`、`org_company`、`org_fleet`、`org_line`
  - 可选：`referenced_message_ids`、`source`（`assistant|research`）、`is_read`、`is_favorite`
- 响应：`{ data: EvalRecord }`

#### `GET /research/evals/{id}`

- 响应：`{ data: EvalRecord + linked_issues + session }`

#### `PATCH /research/evals/{id}`

- 请求体：`conclusion?`、`issue_type_ids?`、`new_issue_type_names?`、`confidence?`、`note?`、`tags?`、`is_read?`、`is_favorite?`
- 响应：`{ data: EvalRecord }`

#### `GET /research/issues`

- Query：使用“通用筛选参数”
- 可排序字段：`created_at`、`updated_at`、`due_at`、`severity`、`priority`
- 响应：`{ data: { items, total, page, pageSize, kanban, status_counts, severity_distribution, trend }, meta? }`

#### `POST /research/issues`

- 请求体：
  - 必填：`description`、`session_id` 或 `sessionId`
  - 可选：`title`、`issue_type_ids`、`new_issue_type_names`
  - 可选：`severity`、`priority`、`status`
  - 可选：`expected_result`、`business_impact`、`repro_steps`
  - 可选：`source_eval_id`、`referenced_message_ids`、`context_summary`
  - 可选：`model_version`、`scenario`、`org_group`、`org_company`、`org_fleet`、`org_line`
  - 可选：`assignee`、`due_at`、`submit_mode`、`source_metric`
  - 可选：`created_by`、`updated_by`、`event_note`、`operator`
  - 可选：`comment`（`handling_type/description/commit_id`）
- 响应：`{ data: IssueRecord }`

#### `GET /research/issues/{id}`

- 响应：`{ data: IssueRecord + events + linked_eval + session }`

#### `PATCH /research/issues/{id}`

- 请求体：问题字段的部分更新（与创建字段同类，均可选）
- 响应：`{ data: IssueRecord }`

### 3.8 知识库代理接口（`/kb/*`）

> 权限：**当前实现下，全部 `/kb/*` 接口均要求管理员身份**。非管理员（含未登录）访问任意 `/kb/*` 均返回 `403`。
> 完整的 KB/RAG 入参、响应、上传路径、权限继承、错误码和底层 `/v1` 行为见：`agent/docs/current/operations/知识库系统API接口文档.md`。

#### 3.8.1 路由映射

| Agent 路径                      | 方法             | 转发到 KB 服务                  |
| ------------------------------- | ---------------- | ------------------------------- |
| `/kb/retrieve`                  | POST             | `/v1/retrieve`                  |
| `/kb/reindex`                   | POST             | `/v1/reindex`                   |
| `/kb/documents/preview`         | POST             | `/v1/documents/preview`         |
| `/kb/documents/commit`          | POST             | `/v1/documents/commit`          |
| `/kb/documents/{docId}/replace` | POST             | `/v1/documents/{docId}/replace` |
| `/kb/documents`                 | GET/POST         | `/v1/documents`                 |
| `/kb/documents/{docId}`         | GET/PATCH/DELETE | `/v1/documents/{docId}`         |
| `/kb/documents/{docId}/file`    | GET              | `/v1/documents/{docId}/file`    |
| `/kb/jobs/{jobId}`              | GET              | `/v1/jobs/{jobId}`              |

显式接口签名（便于联调）：

- `POST /kb/retrieve`
- `POST /kb/reindex`
- `POST /kb/documents/preview`
- `POST /kb/documents/commit`
- `POST /kb/documents/{docId}/replace`
- `GET /kb/documents`
- `POST /kb/documents`
- `GET /kb/documents/{docId}`
- `PATCH /kb/documents/{docId}`
- `DELETE /kb/documents/{docId}`
- `GET /kb/documents/{docId}/file`
- `GET /kb/jobs/{jobId}`

#### 3.8.2 说明

- Query 参数透传到 KB 服务。
- 请求体按原样透传（`GET/HEAD` 无 body）。
- 特殊限制：底层 retrieval 服务支持 `/v1/documents/{docId}/clauses:batchUpsert` 和 `/v1/documents/{docId}/clauses/{clauseId}`，但 Agent 代理层 `/kb/documents/{docId}/clauses*` 当前不开放，返回 `404`。
- 常规文件上传不传物理文件路径，使用 `preview -> commit`；正式 `file_storage_key` 由 retrieval 服务生成。`POST /kb/documents` 是直接创建/迁移入口，允许传 `file_storage_key`，不执行文件上传或迁移。
- 当前 `query_kb` 工具仅为运行时预留能力，默认受 `KB_TOOL_ENABLED=false` 控制，不属于默认对外开放能力。
- 转发时附加请求头：
  - `X-Tenant-Id`
  - `X-Caller-Level`
  - `X-Caller-Id`
  - `X-Request-Id`
  - `X-Caller-Company-Id`（公司级调用时）

## 4. 错误处理

### 4.1 常见 HTTP 状态码

| 状态码 | 含义           | 常见场景                                                      |
| ------ | -------------- | ------------------------------------------------------------- |
| `400`  | 请求参数错误   | 必填缺失、字段类型不合法                                      |
| `401`  | 未认证         | 用户名或密码错误（如 `POST /auth/login`）                     |
| `403`  | 权限不足       | 非管理员访问 `/research/*` 或 `/kb/*`（含未登录访问 `/kb/*`） |
| `404`  | 资源不存在     | session/rule/scenario/eval/issue 不存在                       |
| `500`  | 服务器内部错误 | 后端内部异常                                                  |
| `502`  | 上游代理失败   | KB 代理调用失败                                               |

### 4.2 错误响应格式

```json
{
  "error": "具体错误信息"
}
```

或

```json
{
  "success": false,
  "error": "错误代码"
}
```

## 5. 快速开始

1. `GET /health` 检查服务状态。
2. 如需登录态，`POST /auth/login`。
3. 页面按钮直接生成报告时，调用 `POST /reports/summary`，不需要创建会话。
4. 需要普通对话时，`POST /sessions` 创建会话。
5. 发送消息：`POST /chat` 或 `POST /chat/stream`。
6. 需要规则运营时，使用 `/rules*`、`/rule-config*`。
7. 需要研究看板时，管理员使用 `/research*`。
8. 需要知识库时，需管理员登录后使用 `/kb*`。

---

如后续接口实现变更，建议同步更新本文件的“版本”和“最后更新”字段，并附带变更清单。

### 变更记录

- **v1.11**（2026-06-09）：新增 MCP 业务访问令牌配置说明；Agent 调用 MCP 时优先使用客户端请求头 `X-Access-Token`（经 `withRequestAccessTokenEnv` 覆盖 `env.MCP_ACCESS_TOKEN`），未传时回退到环境变量 `MCP_ACCESS_TOKEN` 并透传为 `X-Access-Token`。
- **v1.10**（2026-06-08）：更新事故报告专用接口入参；`POST /reports/summary` 生成事故调查报告时使用 `accidentDate` / `accident_date`，格式 `yyyyMMddHHmmss`，不再使用 `ppartition` / `partition` 作为事故时间；补充报告目标字段互斥说明和 `station_report_format_mismatch` 语义，避免将站场报告模板校验失败误判为客户传参错误。
- **v1.9**（2026-06-06）：同步报告接口测试页的站场报告入口；`POST /reports/summary` 文档补齐站场自动识别规则、显式类型值 `station` / `bus_station` / `generate_station_report`，并将推荐样例更新为 MCP 可命中的 `303太古仓路总站` + `20260531`。
- **v1.8**（2026-06-05）：补充站场三条管线完成状态：站场专家 `consult_station_expert`、对话式 router 工具 `generate_station_report` / `consult_station_expert`、报告专用接口 `POST /reports/summary` 的 `stationName` / `station_name` / `busStationName`、`type=station`、`/reports/summary/station` 均已按当前实现接入；站场画像数据源为 `get_mcp_base_absBusStationProfileMain_queryBusStationProfile`。
- **v1.7**（2026-06-05）：按当前事故报告管线实现修正 `POST /reports/summary` 文档；事故调查报告专用接口当前使用显式事故类型 + 肇事驾驶员姓名 + `ppartition/partition` 生成，不再描述为 `incidentId/incident_id` 直查；补充事故报告链路完成度、输出结构和限制说明。
- **v1.6**（2026-05-06）：新增 `POST /reports/summary` 无会话报告生成接口，支持驾驶员、车辆、单位、线路、事故调查 5 类报告；补充字段自动识别、通用 `id/name` + 类型调用方式、响应结构和错误规则。
- **v1.5**（2026-04-02）：补充 `POST /chat` 返回消息级 `sources` 字段说明，明确来源信息统一通过消息层透传，不使用报告级字段或 `metadata` 承载业务来源。
- **v1.4**（2026-03-25）：补充知识库代理说明中的 `query_kb` 默认关闭状态；修正“快速开始”中 `/kb*` 的访问描述为“需管理员登录后使用”。
- **v1.3**（2026-03-21）：同步车辆专家 CoT 开关实验的统计口径；`GET /ab-test/stats` 响应改为通用 `metrics` 数组结构，并补充当前实验过滤说明。
- **v1.2**（2026-03-04）：与当前代码对齐：修正 `/kb/*` 权限描述为“全部需管理员，非管理员或未登录均返回 403”；修正 4.1 中 401/403 的说明与场景。
- **v1.1**：按后端实现补全参数、响应与权限说明。
