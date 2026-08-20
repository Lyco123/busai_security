/**
 * 查询列表工具实现代码示例
 * 
 * 这个文件展示了如何在 agent/src/index.ts 中添加查询列表功能
 */

// ============================================
// 方案1：添加新工具（推荐）
// ============================================

// 1. 更新 ToolName 类型定义
type ToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_route_report'
  | 'query_driver_list'      // 新增
  | 'query_vehicle_list'     // 新增
  | 'query_route_list'       // 新增
  | 'consult_omni';

// 2. 添加查询函数
async function queryDriverList(
  db: D1Database,
  args: Record<string, unknown>
): Promise<{ drivers: Array<{ id: string; name: string; identifier: string | null; fleet_name?: string; status?: string }>; total: number }> {
  const fleetId = typeof args.fleet_id === 'string' ? args.fleet_id : null;
  const status = typeof args.status === 'string' ? args.status : null;
  const limit = typeof args.limit === 'number' ? Math.min(Math.max(args.limit, 1), 100) : 50;

  // 查询所有司机
  let query = 'SELECT id, name, identifier, data FROM agent_profiles WHERE kind = ?';
  const bindings: unknown[] = ['driver'];

  // 如果支持 JSON 查询（SQLite 3.38+）
  // 注意：Cloudflare D1 可能不支持 JSON_EXTRACT，需要先查询再过滤
  const result = await db.prepare(query).bind(...bindings).all<{
    id: string;
    name: string;
    identifier: string | null;
    data: string;
  }>();

  // 解析并过滤数据
  let drivers = result.results.map((row) => {
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
      data: parsedData, // 保留完整数据用于后续过滤
    };
  });

  // 应用过滤条件
  if (fleetId) {
    drivers = drivers.filter(d => d.fleet_name === fleetId);
  }
  if (status) {
    drivers = drivers.filter(d => d.status === status);
  }

  // 排序并限制数量
  drivers = drivers
    .sort((a, b) => a.name.localeCompare(b.name))
    .slice(0, limit);

  // 获取总数（未过滤前）
  const totalResult = await db
    .prepare('SELECT COUNT(*) as count FROM agent_profiles WHERE kind = ?')
    .bind('driver')
    .first<{ count: number }>();

  return {
    drivers: drivers.map(({ data, ...rest }) => rest), // 移除 data 字段
    total: totalResult?.count ?? drivers.length,
  };
}

async function queryVehicleList(
  db: D1Database,
  args: Record<string, unknown>
): Promise<{ vehicles: Array<{ id: string; name: string; identifier: string | null; fleet_name?: string }>; total: number }> {
  const limit = typeof args.limit === 'number' ? Math.min(Math.max(args.limit, 1), 100) : 50;

  const result = await db
    .prepare('SELECT id, name, identifier, data FROM agent_profiles WHERE kind = ? ORDER BY name LIMIT ?')
    .bind('vehicle', limit)
    .all<{
      id: string;
      name: string;
      identifier: string | null;
      data: string;
    }>();

  const vehicles = result.results.map((row) => {
    const parsedData = safeJsonParse(row.data);
    const basic = parsedData && typeof parsedData === 'object' && 'basic' in parsedData
      ? (parsedData.basic as Record<string, unknown>)
      : {};

    return {
      id: row.id,
      name: row.name,
      identifier: row.identifier,
      fleet_name: typeof basic.fleet_name === 'string' ? basic.fleet_name : undefined,
    };
  });

  const totalResult = await db
    .prepare('SELECT COUNT(*) as count FROM agent_profiles WHERE kind = ?')
    .bind('vehicle')
    .first<{ count: number }>();

  return {
    vehicles,
    total: totalResult?.count ?? vehicles.length,
  };
}

async function queryRouteList(
  db: D1Database,
  args: Record<string, unknown>
): Promise<{ routes: Array<{ id: string; name: string; identifier: string | null; fleet_name?: string }>; total: number }> {
  const limit = typeof args.limit === 'number' ? Math.min(Math.max(args.limit, 1), 100) : 50;

  const result = await db
    .prepare('SELECT id, name, identifier, data FROM agent_profiles WHERE kind = ? ORDER BY name LIMIT ?')
    .bind('route', limit)
    .all<{
      id: string;
      name: string;
      identifier: string | null;
      data: string;
    }>();

  const routes = result.results.map((row) => {
    const parsedData = safeJsonParse(row.data);
    const basic = parsedData && typeof parsedData === 'object' && 'basic' in parsedData
      ? (parsedData.basic as Record<string, unknown>)
      : {};

    return {
      id: row.id,
      name: row.name,
      identifier: row.identifier,
      fleet_name: typeof basic.fleet_name === 'string' ? basic.fleet_name : undefined,
    };
  });

  const totalResult = await db
    .prepare('SELECT COUNT(*) as count FROM agent_profiles WHERE kind = ?')
    .bind('route')
    .first<{ count: number }>();

  return {
    routes,
    total: totalResult?.count ?? routes.length,
  };
}

// 3. 在 runTool 函数中添加处理逻辑
async function runTool(
  env: Env,
  toolCall: ToolCall,
  isStream = false
): Promise<{ content: string | ReadableStream; metadata?: Record<string, unknown> }> {
  const skill = TOOL_SKILLS[toolCall.tool];
  if (!skill) {
    return { content: `暂不支持的工具：${toolCall.tool}` };
  }

  // 处理查询列表工具（新增）
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

  // ... 现有的 consult_omni 和其他工具处理逻辑 ...
}

// 4. 更新 callOpenAIRouter 函数中的工具定义
async function callOpenAIRouter(
  env: Env,
  options: {
    model: string;
    messages: ChatCompletionMessage[];
    temperature?: number;
  }
): Promise<{ content?: string; toolCall?: ToolCall }> {
  // ... 现有代码 ...

  const tools: Array<{ type: 'function'; function: ToolSchema }> = [
    // ... 现有工具 ...
    {
      type: 'function',
      function: {
        name: 'query_driver_list',
        description: '查询驾驶员列表，支持按车队、状态等条件过滤。当用户询问"有哪些司机"、"列出所有司机"、"查询司机列表"时使用。',
        parameters: {
          type: 'object',
          properties: {
            fleet_id: { 
              type: 'string', 
              description: '车队ID，用于过滤特定车队的司机。' 
            },
            status: { 
              type: 'string', 
              enum: ['active', 'leave', 'suspended'],
              description: '状态过滤，可选值：active（在职）、leave（离职）、suspended（停职）。' 
            },
            limit: { 
              type: 'number', 
              description: '返回数量限制，默认50，最大100。' 
            },
          },
          required: [],
        },
      },
    },
    {
      type: 'function',
      function: {
        name: 'query_vehicle_list',
        description: '查询车辆列表。当用户询问"有哪些车辆"、"列出所有车辆"、"查询车辆列表"时使用。',
        parameters: {
          type: 'object',
          properties: {
            limit: { 
              type: 'number', 
              description: '返回数量限制，默认50，最大100。' 
            },
          },
          required: [],
        },
      },
    },
    {
      type: 'function',
      function: {
        name: 'query_route_list',
        description: '查询线路列表。当用户询问"有哪些线路"、"列出所有线路"、"查询线路列表"时使用。',
        parameters: {
          type: 'object',
          properties: {
            limit: { 
              type: 'number', 
              description: '返回数量限制，默认50，最大100。' 
            },
          },
          required: [],
        },
      },
    },
    // ... 其他工具 ...
  ];

  // ... 现有代码 ...
}

// 5. 更新 isToolName 函数
function isToolName(value: string): value is ToolName {
  return (
    value === 'generate_driver_report' ||
    value === 'generate_vehicle_report' ||
    value === 'generate_route_report' ||
    value === 'query_driver_list' ||      // 新增
    value === 'query_vehicle_list' ||     // 新增
    value === 'query_route_list' ||       // 新增
    value === 'consult_omni'
  );
}

// ============================================
// 方案2：增强 consult_omni（快速实现）
// ============================================

// 在 runTool 函数的 consult_omni 处理中添加：
async function runTool_方案2(
  env: Env,
  toolCall: ToolCall,
  isStream = false
): Promise<{ content: string | ReadableStream; metadata?: Record<string, unknown> }> {
  // ... 现有代码 ...

  if (toolCall.tool === 'consult_omni') {
    const query = String(toolCall.args.query ?? '').trim();
    if (!query) {
      return { content: '请提供需要解答的问题或背景信息。' };
    }

    // 检测查询列表请求
    const isQueryDriverList = /有哪些司机|列出所有司机|司机列表|查询司机|所有司机/i.test(query);
    const isQueryVehicleList = /有哪些车辆|列出所有车辆|车辆列表|查询车辆|所有车辆/i.test(query);
    const isQueryRouteList = /有哪些线路|列出所有线路|线路列表|查询线路|所有线路/i.test(query);

    let contextData = '';
    
    if (isQueryDriverList) {
      const list = await queryDriverList(env.DB, { limit: 50 });
      contextData = `当前系统中有以下司机（共 ${list.total} 名）：\n${list.drivers.map((d, i) => `${i + 1}. ${d.name}${d.identifier ? ` (${d.identifier})` : ''}${d.fleet_name ? ` - ${d.fleet_name}` : ''}`).join('\n')}`;
    } else if (isQueryVehicleList) {
      const list = await queryVehicleList(env.DB, { limit: 50 });
      contextData = `当前系统中有以下车辆（共 ${list.total} 辆）：\n${list.vehicles.map((v, i) => `${i + 1}. ${v.name}${v.identifier ? ` (${v.identifier})` : ''}${v.fleet_name ? ` - ${v.fleet_name}` : ''}`).join('\n')}`;
    } else if (isQueryRouteList) {
      const list = await queryRouteList(env.DB, { limit: 50 });
      contextData = `当前系统中有以下线路（共 ${list.total} 条）：\n${list.routes.map((r, i) => `${i + 1}. ${r.name}${r.identifier ? ` (${r.identifier})` : ''}${r.fleet_name ? ` - ${r.fleet_name}` : ''}`).join('\n')}`;
    }

    const context =
      typeof toolCall.args.context === 'string' ? toolCall.args.context.trim() : '';
    const prompt = contextData 
      ? `问题：${query}\n\n系统数据：\n${contextData}${context ? `\n\n补充背景：${context}` : ''}`
      : context 
        ? `问题：${query}\n\n补充背景：${context}` 
        : query;

    // ... 调用 LLM 的代码保持不变 ...
  }

  // ... 其他工具处理 ...
}

