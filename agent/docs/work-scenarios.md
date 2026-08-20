# 工作场景表（Work Scenario Table）

本系统通过“工作场景表”进行业务门控。运行时代码会先判断当前请求是否仍在受支持的业务范围内；命中场景表才继续进入 Router，不命中则直接拒绝。

工作场景**不再**作为 Router 的决策提示词注入，也**不再**承担工具分流、缺参追问或自然语言拒绝策略。工具分流由以下部分共同完成：
- 规则匹配结果（`[RULE_MATCH_RESULTS]` / `[RULE_ROUTING_POLICY]`）
- router skill
- function tool description

## 表结构（D1）

```sql
work_scenarios(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  keywords TEXT,
  embedding TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
```

字段说明：
- `name`：场景名称（人类可读）
- `description`：场景描述（用于表达业务边界）
- `keywords`：关键词（JSON 数组，辅助表达业务范围）
- `embedding`：向量（JSON 数组，用于场景召回）
- `enabled`：是否启用（1/0）

## 门控行为

- 如果场景有 `embedding`，系统会使用向量相似度筛选候选场景。
- 当向量不可用（缺少 embedding 或接口失败）时，系统会退化为返回所有启用场景供门控代码使用。
- 只要没有任何可用场景候选，运行时代码会直接拒绝，不会再把场景表交给 Router 做二次判断。
- Router 仍会收到 `scenario` metadata 便于记录与分析，但不会基于工作场景表做软决策。

## API

### 列表
`GET /api/agent/scenarios?include_disabled=true`

### 新增
`POST /api/agent/scenarios`
```json
{
  "name": "车辆安全报告相关请求",
  "description": "与单车安全报告、车辆画像、车辆风险总结相关的业务请求",
  "keywords": ["车辆", "安全报告", "画像", "风险总结"],
  "enabled": true
}
```

### 查询
`GET /api/agent/scenarios/{id}`

### 更新
`PUT /api/agent/scenarios/{id}`
```json
{
  "description": "更新后的业务范围描述",
  "keywords": ["新的关键词"],
  "enabled": true,
  "refresh_embedding": true
}
```

### 删除
`DELETE /api/agent/scenarios/{id}`

> 注：embedding 会在新增或更新时自动尝试生成；如果未配置 API Key（通过 `OPENAI_API_KEY` 环境变量），则会跳过。默认使用阿里云 DashScope 服务（`https://dashscope.aliyuncs.com/compatible-mode/v1`）和 `text-embedding-v1` 模型。
