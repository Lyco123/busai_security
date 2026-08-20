# BUSAI MCP Tools 交接文档模板

> 用途：本模板用于约束乙方交付 **MCP tools** 时必须提交的文档内容。  
> 目标：让甲方能够基于交付文档完成 **工具接入、调试、验收、后续维护**。  
> 说明：本文档不再以传统 REST 接口说明为中心，而以 **MCP tool 可被模型稳定调用** 为中心。
> 规范边界：凡涉及 `tools/list`、`tools/call`、`inputSchema`、`outputSchema`、`annotations`、`CallToolResult` 的内容，必须与 MCP 官方规范一致；权限矩阵、可观测性、验收、兼容策略等属于企业交付惯例。
> 版本说明：最新官方规范可参考 `2025-11-25`；BUS 当前联调基线仍为 `2025-03-26`，乙方需明确实际支持版本。
> BUS 当前项目侧基线：我方联调与运行链路当前通过 **HTTP MCP endpoint** 接入，默认协议版本仍为 `2025-03-26`；若乙方仅支持更高版本，需在联调前明确兼容性。

---

## BUS 当前接入基线（项目侧）

- 当前接入方式：HTTP MCP endpoint
- 当前联调顺序：`initialize` → `notifications/initialized` → `tools/list` → `tools/call`
- 当前默认请求头：`Accept: application/json, text/event-stream`
- 当前我方强依赖字段：`name`、`description`、`inputSchema`
- 当前我方增强但非阻塞字段：`title`、`outputSchema`、`annotations`
- 若乙方当前仅能按 `2025-03-26` 基线交付，至少保证上述强依赖字段与 `isError` 语义正确；增强字段按 server 实际支持情况提供
- 当前我方判错方式：JSON-RPC `error` 或 `result.isError=true`
- 当前我方错误提取方式：优先读取首个 `content[].text`
- 当前我方结果处理方式：保留原始 `CallToolResult`，并尝试从 `content[].text` 中提取 JSON；为了稳定联调，建议同时提供 `structuredContent` 与简洁文本摘要

---

## 版本变更历史

| 版本 | 状态 | 说明 | 日期 | 创建人 |
|---|---|---|---|---|
| V1.0 | 创建 | MCP tools 交接模板初始化 | YYYY-MM-DD | [姓名] |
| V1.1 | 修订 | 补充返回契约、安全语义、权限矩阵、可观测性、兼容性与废弃策略 | YYYY-MM-DD | [姓名] |
| V1.2 | 修订 | 按 MCP 官方规范校正 tool 字段、CallToolResult、outputSchema、annotations 与错误处理边界 | YYYY-MM-DD | [姓名] |

---

# 1. 交付范围说明

## 1.1 本次交付的 MCP tools 清单

请列出本次交付的全部 tools。

| Tool 名称 | Tool 中文名称 | 功能简介 | 所属业务域 | 状态 |
|---|---|---|---|---|
| `get_vehicle_basic_info` | 查询车辆基础信息 | 根据车辆标识查询车辆基础资料 | 车辆 | 已交付 |
| `get_driver_risk_events` | 查询司机风险事件 | 查询指定司机在时间范围内的风险事件 | 驾驶员 | 已交付 |

## 1.2 本次不在交付范围内的内容

请明确写出哪些能力 **不属于本次交付范围**，避免边界不清。

示例：
- 不包含 Agent Prompt / Skill 编写
- 不包含 前端页面开发
- 不包含 报表 PDF 渲染
- 不包含 历史数据修复
- 不包含 生产环境监控大盘

---

# 2. MCP Server 基本信息

## 2.1 服务信息

| 项目 | 内容 |
|---|---|
| MCP Server 名称 |  |
| 运行环境 |  |
| 部署地址 |  |
| 所属系统/子系统 |  |
| 负责人 |  |
| 联系方式 |  |
| 版本号 |  |

## 2.2 连接与启动方式

请说明甲方如何连接该 MCP Server。

### 启动方式
- MCP 服务地址（HTTP endpoint）：
- 本地启动命令：
- Docker 启动方式：
- 所需环境变量：

### 认证方式
- 是否需要认证：
- 认证类型（如 API Key / Bearer Token / 内网白名单）：
- 鉴权字段位置：
- 凭证申请方式：

### 健康检查方式
- 健康检查接口/方式：
- 启动成功判定标准：

---

# 3. 单个 Tool 交接模板

> 以下内容 **每个 tool 都必须单独填写一份**。  
> 若本次交付多个 tool，请按本章节结构重复编写。

---

## 3.1 Tool 基本定义

| 项目 | 内容 |
|---|---|
| Tool 名称 |  |
| Tool 中文名称 |  |
| MCP `title`（可选） |  |
| Tool 版本号 |  |
| 功能描述 |  |
| 适用场景 |  |
| 不适用场景 |  |
| 是否只读 | 是 / 否 |
| 风险等级 | 低 / 中 / 高 |
| 是否影响生产数据 | 是 / 否 |
| 幂等性 | 幂等 / 非幂等 / 条件幂等 |
| 是否允许自动重试 | 是 / 否 / 仅限特定错误 |
| 副作用说明 |  |

### 3.1.1 Tool description（提供给模型的描述）

请填写最终注册到 MCP 中的 description 文案。要求：
- 准确说明用途
- 写清触发条件
- 写清边界与限制
- 避免模糊表达

```text
[在此填写 tool description]
```

### 3.1.2 Tool 使用约束

请明确说明：
- 必须传哪些关键信息
- 缺少哪些参数时禁止调用
- 哪些情况下应优先调用其他 tool
- 哪些情况下禁止调用该 tool

### 3.1.3 MCP `annotations` 约定

若该 tool 使用 MCP 官方字段 `annotations`，请明确填写：
- `annotations.readOnlyHint`
- `annotations.destructiveHint`
- `annotations.idempotentHint`
- `annotations.openWorldHint`

说明：
- `annotations` 是给客户端和宿主的提示信息，不是安全边界，也不能替代真实权限控制

### 3.1.4 写操作与重试安全约定

若该 tool 不是只读查询，必须额外说明：
- 是否存在创建、修改、删除、触发任务、发送通知等副作用
- 哪些调用是天然幂等的，哪些不是
- 哪些错误下允许自动重试，哪些错误下严禁重试
- 重试时是否要求传入幂等键、请求流水号或业务单号
- 若执行部分成功，如何判定、回滚或补偿
- 若 tool 会影响生产数据，甲方联调时应使用什么隔离环境或测试租户

---

## 3.2 Input Schema（入参定义）

> 该部分必须与实际 MCP tool 注册时的 `inputSchema` 一致。  
> MCP 默认 schema dialect 为 JSON Schema 2020-12；`inputSchema` 根节点应为 `object`。若 tool 无参数，建议使用 `{ "type": "object", "additionalProperties": false }`。

### 3.2.1 JSON Schema

```json
{
  "type": "object",
  "properties": {
    "example_field": {
      "type": "string",
      "description": "示例字段"
    }
  },
  "required": ["example_field"]
}
```

### 3.2.2 参数说明表

| 参数名 | 类型 | 必填 | 取值范围/格式 | 示例 | 含义说明 | 缺失/非法时处理 |
|---|---|---|---|---|---|---|
| `example_field` | string | 是 | 不超过50字符 | `A123` | 示例字段 | 返回参数错误 |

### 3.2.3 参数校验规则

请明确说明：
- 必填字段校验规则
- 枚举值校验规则
- 时间格式规则
- 字符串长度限制
- 数值上下限
- 多字段联合校验规则

示例：
- `start_time` 不得晚于 `end_time`
- `vehicle_id` 与 `plate_no` 至少传一个
- `page_size` 最大不超过 100

### 3.2.4 `outputSchema`（如适用）

若该 tool 会返回 `structuredContent`，建议同时提供与之对应的 `outputSchema`。若提供，则凡是返回 `structuredContent` 的结果都必须符合该 schema。若错误场景也需要返回机器可读结构，请将错误对象一并纳入 schema，或改为仅返回 `content` + `isError=true`。

```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "example_result": {
            "type": "string"
          }
        },
        "required": ["example_result"]
      }
    },
    "total": {
      "type": "integer"
    }
  },
  "required": ["items", "total"]
}
```

---

## 3.3 Output 定义（返回结果）

> 该部分必须与实际 tool 返回结构一致。  
> 要求区分：**JSON-RPC 协议层**、**`CallToolResult` 结果层** 与 **业务数据结构**。

### 3.3.1 协议层返回约定

请先说明：
- `tools/call` 的外层响应遵循 JSON-RPC 2.0
- JSON-RPC 成功响应的 `result` 必须是 MCP 的 `CallToolResult`
- `CallToolResult` 至少包含 `content`
- `structuredContent`、`isError`、`_meta` 为可选字段
- 不要为了适配模板人为引入 `success/data/message` 包装层，除非这就是 tool 的真实业务 payload
- 为兼容 BUS 当前项目侧，建议在 `content` 首个 text block 中给出简洁稳定的文字摘要；如需机器可读数据，再放入 `structuredContent`

### 3.3.2 成功返回结构示例

以下示例描述 `tools/call` 成功响应中的 `result` 部分；若你的 tool 返回结构不同，请以真实 `CallToolResult` 为准。

```json
{
  "content": [
    {
      "type": "text",
      "text": "查询成功，共返回 1 条记录"
    }
  ],
  "structuredContent": {
    "items": [
      {
        "example_result": "value"
      }
    ],
    "total": 1
  }
}
```

### 3.3.3 返回字段说明表

| 字段路径 | 类型 | 必返 | 示例 | 含义说明 |
|---|---|---|---|---|
| `content` | ContentBlock[] | 是 | `[{ "type": "text", "text": "ok" }]` | 非结构化返回内容 |
| `structuredContent` | object | 否 | `{ "items": [], "total": 0 }` | 结构化返回内容 |
| `isError` | boolean | 否 | `false` | 是否为 Tool Execution Error |
| `_meta` | object | 否 | `{}` | MCP 保留扩展元数据 |

### 3.3.4 业务数据结构说明

请补充说明：
- `structuredContent` 的实际 schema 或字段表
- 列表结果、详情结果、分页结果是否使用同一结构
- 若存在分页，分页字段名、游标/页码语义、排序约束是什么
- 哪些字段可能缺省、为 `null`、为空数组

### 3.3.5 空结果约定

请明确说明以下情况如何返回：
- 查询成功但无数据
- 条件合法但无匹配记录
- 上游返回空数组

建议写法：
- `isError` 不填或为 `false`
- `content` 明确告知“无数据”
- `structuredContent` 使用与 `outputSchema` 一致的空数组 / 空对象
- 空结果必须与异常区分开

### 3.3.6 错误返回结构

```json
{
  "content": [
    {
      "type": "text",
      "text": "参数错误：example_field 为必填"
    }
  ],
  "isError": true
}
```

说明：
- 参数校验失败、上游失败、业务规则不满足等，应优先作为 Tool Execution Error 返回
- 若需要机器可读的业务错误码，建议在 `structuredContent` 中定义统一错误对象，并在 `outputSchema` 或文档中说明；若错误结构不满足 `outputSchema`，则不应返回不合规的 `structuredContent`
- 为兼容 BUS 当前项目侧，失败结果的首个 `content[].text` 应给出稳定错误文案，便于我方调试台和运行链路直接展示与诊断

---

## 3.4 协议错误与业务错误

> MCP 需要区分 **协议错误（JSON-RPC / MCP 层）** 与 **Tool Execution Error（业务/执行层）**。

### 3.4.1 协议错误（JSON-RPC / MCP 层）

以下错误应作为 JSON-RPC `error` 返回，而不是 Tool Execution Error：

| 场景 | 典型错误码 | 含义 | 是否建议暴露给模型 | 说明 |
|---|---|---|---|---|
| 未知 tool / tool 不存在 | `-32602` | 请求参数或 tool 名称无效 | 可选 | 官方示例使用 `-32602` |
| 请求不满足 `CallToolRequest` schema | `-32602` | 请求结构本身非法 | 可选 | 属于协议层问题 |
| 服务端内部异常 | `-32603` | 服务端无法完成本次协议请求 | 可选 | 属于协议层问题 |

### 3.4.2 Tool Execution Error（业务/执行层错误码）

以下错误建议作为 `CallToolResult` 返回，并设置 `isError=true`：

| 业务错误码 | 错误类型 | 含义 | 是否可重试 | 建议处理方式 |
|---|---|---|---|---|
| `PARAM_INVALID` | 参数错误 | 输入参数不合法 | 否 | 修正参数后重试 |
| `AUTH_FAILED` | 认证失败 | 凭证无效或缺失 | 否 | 检查认证配置 |
| `PERMISSION_DENIED` | 权限错误 | 无权限访问数据 | 否 | 申请权限 |
| `UPSTREAM_TIMEOUT` | 上游超时 | 依赖系统超时 | 是 | 可有限重试 |
| `UPSTREAM_UNAVAILABLE` | 上游不可用 | 依赖系统不可访问 | 是 | 稍后重试 |
| `INTERNAL_ERROR` | 内部异常 | Tool 内部处理异常 | 视情况 | 记录日志并排查 |

### 3.4.3 错误处理约定

请说明：
- 哪些错误允许自动重试
- 最大重试次数
- 哪些错误应直接透传给上层
- 哪些错误需要转换为统一错误码
- 哪些错误需要提示人工介入，不能由 Agent 自行继续尝试

---

## 3.5 Tool 调用示例

### 3.5.1 最小可用请求示例

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "get_vehicle_basic_info",
    "arguments": {
      "vehicle_id": "A123"
    }
  }
}
```

### 3.5.2 完整请求示例

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "get_driver_risk_events",
    "arguments": {
      "driver_id": "D001",
      "start_time": "2026-03-01T00:00:00Z",
      "end_time": "2026-03-31T23:59:59Z",
      "page_size": 20
    }
  }
}
```

### 3.5.3 成功返回示例

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "查询成功，共返回 1 条记录"
      }
    ],
    "structuredContent": {
      "items": [
        {
          "example_result": "value"
        }
      ],
      "total": 1
    }
  }
}
```

### 3.5.4 无数据示例

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "未查询到符合条件的数据"
      }
    ],
    "structuredContent": {
      "items": [],
      "total": 0
    }
  }
}
```

### 3.5.5 错误示例

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "参数错误：start_time 不得晚于 end_time"
      }
    ],
    "isError": true
  }
}
```

### 3.5.6 协议错误示例

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "Unknown tool: invalid_tool_name"
  }
}
```

---

## 3.6 数据来源与业务口径

> 该部分非常重要，必须让甲方知道这个 tool 的数据到底从哪来、按什么口径算。

| 项目 | 内容 |
|---|---|
| 数据来源系统 |  |
| 数据表/接口/服务 |  |
| 刷新频率 |  |
| 是否实时 | 是 / 否 |
| 时间口径 |  |
| 统计口径 |  |
| 排序规则 |  |
| 去重规则 |  |

### 需特别说明的问题
- 是否存在延迟数据
- 是否存在脏数据/历史缺口
- 是否存在口径切换
- 是否有业务字段经过映射、转换、聚合

---

## 3.7 依赖关系

| 依赖项 | 类型 | 是否必须 | 说明 |
|---|---|---|---|
| 认证服务 | 外部服务 | 是 | 用于鉴权 |
| 风险事件数据库 | 数据源 | 是 | 用于读取风险事件 |
| 字典映射表 | 配置 | 否 | 用于状态码转中文 |

请额外说明：
- 上游系统不可用时该 tool 的表现
- 是否有降级方案
- 是否有缓存方案
- 上游依赖的版本要求、网络白名单要求、调用配额要求

---

## 3.8 性能与稳定性要求

| 指标 | 目标值 | 说明 |
|---|---|---|
| 单次调用平均耗时 |  |  |
| P95 耗时 |  |  |
| 超时时间 |  |  |
| 并发能力 |  |  |
| 限流规则 |  |  |

请说明：
- 大查询量时如何处理
- 是否支持分页
- 是否建议 Agent 在大范围查询前先缩小范围

---

## 3.9 可观测性与排障要求

请明确说明：
- 是否生成并透传 `trace_id` / `request_id`
- 调用日志至少记录哪些字段
- 错误日志如何定位到上游依赖和具体入参
- 是否暴露调用量、成功率、P95、超时率等指标
- 是否有告警规则，触发阈值是什么

### 3.9.1 关键日志字段

| 字段名 | 是否必有 | 示例 | 说明 |
|---|---|---|---|
| `trace_id` | 是 | `trc_123` | 全链路追踪标识 |
| `request_id` | 是 | `req_123` | 单次请求标识 |
| `tool_name` | 是 | `get_driver_risk_events` | 当前 tool 名称 |
| `caller` | 否 | `agent-runtime` | 调用方标识 |
| `error_code` | 否 | `UPSTREAM_TIMEOUT` | 失败时错误码 |

### 3.9.2 常见排查路径

请至少说明：
- 启动失败如何排查
- 认证失败如何排查
- 上游超时如何排查
- 返回为空但业务怀疑有数据时如何排查

---

## 3.10 安全与权限控制

请明确说明：
- tool 可访问哪些数据
- tool 不可访问哪些敏感数据
- 是否做字段脱敏
- 是否区分不同角色权限
- 是否记录审计日志
- 敏感或破坏性操作是否要求用户确认 / 审批
- `annotations.readOnlyHint` / `idempotentHint` / `destructiveHint` 仅为提示，不得替代真实鉴权

### 3.10.1 权限矩阵

| 调用主体/角色 | 可调用 tool | 可访问数据范围 | 字段级限制 | 环境限制 | 备注 |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

### 3.10.2 敏感字段说明

| 字段名 | 是否敏感 | 脱敏规则 | 备注 |
|---|---|---|---|
|  |  |  |  |

---

## 3.11 验收用例

> 每个 tool 必须提供至少 3 类验收样例：正常、边界、异常。

### 用例 1：正常场景
- 输入：
- 预期输出：
- 验收标准：

### 用例 2：边界场景
- 输入：
- 预期输出：
- 验收标准：

### 用例 3：异常场景
- 输入：
- 预期输出：
- 验收标准：

### 用例 4：空结果场景
- 输入：
- 预期输出：
- 验收标准：

---

# 4. 联调与验收要求

## 4.1 乙方必须提交的内容

乙方在交付每个 MCP tool 时，至少必须提交以下内容：

1. Tool 注册字段（项目当前强依赖 `name` / `description` / `inputSchema`；若存在 `title` / `outputSchema` / `annotations` 也需原样提交）
2. 最终版 description
3. 最终版 inputSchema
4. 最终版 outputSchema（如适用）
5. 成功 / 空结果 / Tool Execution Error / 协议错误示例
6. 业务错误码说明（如使用）
7. 数据来源与业务口径说明
8. 依赖说明
9. 可观测性与排障说明
10. 权限矩阵与敏感字段说明
11. 写操作安全约定（如适用）
12. 验收测试样例
13. 联调方式说明
14. 上线注意事项
15. 兼容性与废弃策略说明

## 4.2 乙方必须提供的实际交付物

| 交付物 | 是否必须 | 说明 |
|---|---|---|
| Tool 文档 | 是 | 按本模板填写 |
| MCP Server 可运行版本 | 是 | 可供联调 |
| Tool 注册清单 | 是 | 至少包含 `name`、`description`、`inputSchema`；若已注册 `title`、`outputSchema`、`annotations` 也需同步提供 |
| 测试环境地址 | 是 | 用于联调验收 |
| 测试账号/凭证 | 视情况 | 如需认证 |
| 验收样例数据 | 是 | 至少覆盖正常/异常/空结果 |
| 错误码清单 | 是 | 统一定义 |
| 权限矩阵 | 是 | 说明谁能调用、能看什么 |
| 可观测性说明 | 是 | 包含日志字段、trace_id、指标与排障方式 |
| 写操作安全说明 | 视情况 | 写 tool 时需说明幂等性、重试与补偿 |
| 部署说明 | 是 | 启动、配置、依赖 |
| 日志排查说明 | 建议 | 便于联调 |
| 版本兼容与废弃说明 | 是 | 说明升级影响与迁移窗口 |

---

# 5. 上线说明

## 5.1 上线前检查项

- MCP Server 可正常启动
- 全部 tools 可被发现
- 项目当前强依赖的 `name`、`description`、`inputSchema` 为最终版；若已注册 `title`、`outputSchema`、`annotations` 也需与服务端一致
- 测试环境联调通过
- `CallToolResult` 与文档一致
- 协议错误与 Tool Execution Error 的边界正确
- 权限配置正确
- 日志可追踪
- trace_id / request_id 可贯穿联调链路
- 写操作 tool 已验证幂等性与重试策略
- 关键场景已验收

## 5.2 变更影响说明

请说明本次交付对以下内容是否有影响：
- 现有 tools 兼容性
- 参数结构变更
- 返回结构变更
- 权限策略变更
- 数据口径变更

## 5.3 兼容性与废弃策略

请明确说明：
- 本次版本号及发布日期
- 是否向后兼容：兼容 / 部分兼容 / 不兼容
- 若不兼容，影响哪些调用方、字段、错误码或行为
- 旧版本、旧字段、旧错误码的保留期限
- 废弃公告时间、切换时间、下线时间
- 甲方升级所需动作和迁移步骤

---

# 6. 附录

## 6.1 Tool 注册清单汇总

| Tool 名称 | version | 是否只读 | 兼容级别 | 是否已验收 | 备注 |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## 6.2 推荐补充规范（建议乙方遵守）

1. `name` 应遵循 MCP 官方建议：长度 1-128，使用字母、数字、下划线、短横线、点号，避免空格与特殊字符
2. `title` 用于人类展示，`description` 用于帮助客户端和模型理解用途
3. `inputSchema` / `outputSchema` 默认按 JSON Schema 2020-12 处理，根节点建议为 `object`
4. `inputSchema.required` 必须完整，禁止省略必填项
5. 返回结构保持稳定，不要同一字段忽而对象、忽而数组
6. `tools/call` 的成功结果应符合 `CallToolResult`，不要伪造 `success/data/message` 包装层
7. Tool 只返回事实数据，不在 tool 内输出分析结论
8. 空结果必须可区分，不得与异常混淆
9. 参数校验失败等业务错误应优先作为 Tool Execution Error 返回，并设置 `isError=true`
10. 写操作必须说明幂等性、重试边界与补偿策略
11. `annotations` 只是提示，不得替代真实权限控制
12. 文档示例必须能真实跑通

---

# 7. 单个 Tool 交付最小清单（可直接发乙方）

若乙方只看最简版要求，可直接要求其对 **每个 MCP tool** 提交以下内容：

1. tool name  
2. tool description  
3. inputSchema（完整 JSON Schema）  
4. tool title（如已注册）  
5. outputSchema（如已注册或计划启用 structuredContent 校验）  
6. annotations 说明（如已注册）  
7. 参数说明表  
8. 成功返回示例  
9. 空结果返回示例  
10. Tool Execution Error 示例  
11. 协议错误示例  
12. 业务错误码表  
13. 数据来源与业务口径说明  
14. 依赖项说明  
15. 可观测性与排障说明  
16. 权限与敏感字段说明  
17. 写操作的幂等性/重试/补偿说明（如适用）  
18. 至少 3 条验收用例  
19. 测试环境联调方式  
20. 部署与启动说明  
21. 版本兼容与废弃说明

---

> 备注：若甲方后续还需要，我可以在此模板基础上继续细化一版《乙方必须提交的 MCP Tool 开发与验收规范》，把“文档要求 + 开发要求 + 验收标准”合并成一份更强约束的正式规范。
