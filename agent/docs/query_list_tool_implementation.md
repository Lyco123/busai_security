# 查询列表工具实现方案

## 问题

当前工具层只有：
- `generate_driver_report` - 生成单个司机报告
- `generate_vehicle_report` - 生成单个车辆报告  
- `generate_route_report` - 生成单个线路报告
- `consult_omni` - 通用助手（但无法直接查询数据库）

**缺失**：查询列表的工具（如"有哪些司机"、"列出所有车辆"）

## 解决方案

### 方案1：添加专门的查询列表工具（推荐）

添加新工具 `query_driver_list`、`query_vehicle_list`、`query_route_list`，直接从数据库查询列表。

**优点**：
- 结构化、可预测
- 可以直接返回列表数据
- 支持过滤参数（如按车队、状态等）

**缺点**：
- 需要修改多个文件
- 需要添加新的工具定义

### 方案2：增强 consult_omni 的数据库访问能力

让 `consult_omni` 能够访问数据库查询列表。

**优点**：
- 不需要添加新工具
- 灵活性高

**缺点**：
- 需要修改 `runTool` 函数
- 可能违反单一职责原则

## 推荐实现：方案1

### 1. 添加新工具类型

在 `agent/src/index.ts` 中添加：

```typescript
type ToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_route_report'
  | 'query_driver_list'      // 新增
  | 'query_vehicle_list'     // 新增
  | 'query_route_list'       // 新增
  | 'consult_omni';
```

### 2. 创建工具技能文件

创建 `agent/skills/structured/query_driver_list/SKILL.md`：

```markdown
---
name: query-driver-list
description: 查询驾驶员列表，支持按车队、状态等条件过滤
---

# 技能：查询驾驶员列表

## 功能描述
查询系统中的驾驶员列表，支持按车队、状态等条件过滤。

## 输入参数

### 可选参数
- `fleet_id`（字符串）：车队ID，用于过滤特定车队的司机
- `status`（字符串）：状态过滤，可选值：`active`、`leave`、`suspended`
- `limit`（数字）：返回数量限制，默认50，最大100

## 输出格式

返回JSON格式的列表：

```json
{
  "drivers": [
    {
      "id": "driver-001",
      "name": "张三",
      "identifier": "D-001",
      "fleet_name": "一车队",
      "status": "active"
    }
  ],
  "total": 10
}
```

## 注意事项
1. 如果未提供过滤条件，返回所有司机
2. limit 参数用于分页，避免返回过多数据
3. 返回的列表按名称排序
```

### 3. 实现工具执行逻辑

在 `runTool` 函数中添加：

```typescript
async function runTool(
  env: Env,
  toolCall: ToolCall,
  isStream = false
): Promise<{ content: string | ReadableStream; metadata?: Record<string, unknown> }> {
  // ... 现有代码 ...

  // 处理查询列表工具
  if (toolCall.tool === 'query_driver_list') {
    const list = await queryDriverList(env.DB, toolCall.args);
    return {
      content: JSON.stringify(list, null, 2),
      metadata: {
        tool: toolCall.tool,
        args: toolCall.args,
      },
    };
  }

  if (toolCall.tool === 'query_vehicle_list') {
    const list = await queryVehicleList(env.DB, toolCall.args);
    return {
      content: JSON.stringify(list, null, 2),
      metadata: {
        tool: toolCall.tool,
        args: toolCall.args,
      },
    };
  }

  if (toolCall.tool === 'query_route_list') {
    const list = await queryRouteList(env.DB, toolCall.args);
    return {
      content: JSON.stringify(list, null, 2),
      metadata: {
        tool: toolCall.tool,
        args: toolCall.args,
      },
    };
  }

  // ... 现有代码 ...
}

async function queryDriverList(
  db: D1Database,
  args: Record<string, unknown>
): Promise<{ drivers: Array<{ id: string; name: string; identifier: string | null; fleet_name?: string; status?: string }>; total: number }> {
  const fleetId = typeof args.fleet_id === 'string' ? args.fleet_id : null;
  const status = typeof args.status === 'string' ? args.status : null;
  const limit = typeof args.limit === 'number' ? Math.min(args.limit, 100) : 50;

  let query = 'SELECT id, name, identifier, data FROM agent_profiles WHERE kind = ?';
  const bindings: unknown[] = ['driver'];

  if (fleetId) {
    // 需要从 data JSON 中提取 fleet_name 进行过滤
    // 注意：SQLite 的 JSON 查询语法
    query += ' AND JSON_EXTRACT(data, "$.basic.fleet_name") = ?';
    bindings.push(fleetId);
  }

  query += ' ORDER BY name LIMIT ?';
  bindings.push(limit);

  const result = await db.prepare(query).bind(...bindings).all<{
    id: string;
    name: string;
    identifier: string | null;
    data: string;
  }>();

  const drivers = result.results.map((row) => {
    const parsedData = safeJsonParse(row.data);
    const basic = parsedData && typeof parsedData === 'object' && 'basic' in parsedData
      ? (parsedData.basic as Record<string, unknown>)
      : {};

    return {
      id: row.id,
      name: row.name,
      identifier: row.identifier,
      fleet_name: typeof basic.fleet_name === 'string' ? basic.fleet_name : undefined,
      status: typeof basic.status === 'string' ? basic.status : undefined,
    };
  });

  // 获取总数（如果需要）
  const totalResult = await db
    .prepare('SELECT COUNT(*) as count FROM agent_profiles WHERE kind = ?')
    .bind('driver')
    .first<{ count: number }>();

  return {
    drivers,
    total: totalResult?.count ?? drivers.length,
  };
}
```

### 4. 更新路由器提示词

在 `agent/skills/router/SKILL.md` 中添加新工具：

```markdown
### 5. `query_driver_list`
- **功能**：查询驾驶员列表
- **可选参数**：
  - `fleet_id`（字符串）：车队ID
  - `status`（字符串）：状态（active/leave/suspended）
  - `limit`（数字）：返回数量限制，默认50
- **调用格式**：
```json
{"tool": "query_driver_list", "args": {"limit": 20}}
```

### 0. 查询列表类请求（优先判断）
- 若用户意图是**查询列表**，请调用相应的查询列表工具。
- **示例**：
  - 用户输入："有哪些司机"
    → 输出：`{"tool": "query_driver_list", "args": {}}`
  - 用户输入："列出所有车辆"
    → 输出：`{"tool": "query_vehicle_list", "args": {}}`
```

### 5. 更新工具注册

```typescript
const TOOL_SKILLS: Record<ToolName, string> = {
  generate_driver_report: driverSkill,
  generate_vehicle_report: vehicleSkill,
  generate_route_report: routeSkill,
  query_driver_list: queryDriverListSkill,      // 新增
  query_vehicle_list: queryVehicleListSkill,    // 新增
  query_route_list: queryRouteListSkill,        // 新增
  consult_omni: omniSkill,
};
```

### 6. 更新路由器工具定义

在 `callOpenAIRouter` 函数中添加：

```typescript
const tools: Array<{ type: 'function'; function: ToolSchema }> = [
  // ... 现有工具 ...
  {
    type: 'function',
    function: {
      name: 'query_driver_list',
      description: '查询驾驶员列表，支持按车队、状态等条件过滤。',
      parameters: {
        type: 'object',
        properties: {
          fleet_id: { type: 'string', description: '车队ID，用于过滤特定车队的司机。' },
          status: { type: 'string', description: '状态过滤，可选值：active、leave、suspended。' },
          limit: { type: 'number', description: '返回数量限制，默认50，最大100。' },
        },
        required: [],
      },
    },
  },
  // ... 其他查询列表工具 ...
];
```

## 简化方案：方案2（快速实现）

如果不想添加新工具，可以让 `consult_omni` 在检测到查询列表请求时，直接查询数据库：

```typescript
if (toolCall.tool === 'consult_omni') {
  const query = String(toolCall.args.query ?? '').trim();
  
  // 检测是否为查询列表请求
  if (query.includes('有哪些司机') || query.includes('列出所有司机') || query.includes('司机列表')) {
    const list = await queryDriverList(env.DB, {});
    const listText = `当前系统中有以下司机：\n${list.drivers.map(d => `- ${d.name} (${d.identifier || d.id})`).join('\n')}\n\n共 ${list.total} 名司机。`;
    
    // 将列表信息作为上下文传递给 omni
    const prompt = `用户问题：${query}\n\n系统数据：${listText}`;
    // ... 调用 LLM ...
  }
}
```

## 总结

**推荐使用方案1**，因为：
1. 更符合工具化设计原则
2. 结构化、可预测
3. 易于扩展和维护
4. 支持更复杂的过滤条件

**如果急需上线**，可以先使用方案2快速实现，后续再迁移到方案1。

