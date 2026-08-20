import { extractMessageSources, withMessageSources } from './message-sources';

export const DEFAULT_MCP_PROTOCOL_VERSION = '2025-03-26';

const DEFAULT_MCP_ACCEPT = 'application/json, text/event-stream';
const DEFAULT_MCP_USER_AGENT = 'Mozilla/5.0 (compatible; bus-agent/1.0)';
const DEFAULT_MCP_REQUEST_TIMEOUT_MS = 25_000;

export interface McpAdaptedToolDefinition {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface McpAgentToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
  error_code?: number | string;
}

export interface McpServerConfig {
  serverUrl?: string;
  clientId?: string;
  clientSecret?: string;
  accessToken?: string;
  protocolVersion?: string;
  clientName?: string;
  clientVersion?: string;
  requestTimeoutMs?: number | string;
}

export interface McpRawTool {
  name: string;
  description?: string;
  inputSchema?: unknown;
  [key: string]: unknown;
}

export interface McpStageResult {
  stage: 'initialize' | 'notifications/initialized' | 'tools/list' | 'tools/call';
  ok: boolean;
  duration_ms: number;
  http_status: number | null;
  error?: string;
}

export interface McpProbeResult {
  configured: boolean;
  ok: boolean;
  target_url: string | null;
  protocol_version: string;
  session_id: string | null;
  server_info: Record<string, unknown> | null;
  stages: McpStageResult[];
  total_duration_ms: number;
  tools: McpRawTool[];
  tool_count: number;
  raw_initialize: unknown;
  raw_tools_list: unknown;
  error?: string;
  timestamp: string;
}

export interface McpToolSummary {
  name: string;
  description: string;
  required_count: number;
  property_count: number;
  input_schema: unknown;
  adapted_parameters: McpAdaptedToolDefinition['parameters'];
}

export interface McpToolDetailResult {
  configured: boolean;
  ok: boolean;
  target_url: string | null;
  protocol_version: string;
  tool_name: string;
  stages: McpStageResult[];
  total_duration_ms: number;
  error?: string;
  raw_tool?: McpRawTool;
  adapted_tool?: McpAdaptedToolDefinition;
  timestamp: string;
}

export interface McpToolCallDebugResult {
  configured: boolean;
  ok: boolean;
  target_url: string | null;
  protocol_version: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  stages: McpStageResult[];
  total_duration_ms: number;
  raw_result: unknown;
  result: unknown;
  agent_received_content: string | null;
  error?: string;
  timestamp: string;
}

interface HttpJsonResult {
  ok: boolean;
  status: number | null;
  headers: Record<string, string>;
  json: unknown;
  bodyText: string;
  error?: string;
}

interface McpSessionState {
  configured: boolean;
  ok: boolean;
  targetUrl: string | null;
  protocolVersion: string;
  sessionId: string | null;
  serverInfo: Record<string, unknown> | null;
  headers: Record<string, string>;
  stages: McpStageResult[];
  totalDurationMs: number;
  rawInitialize: unknown;
  error?: string;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const tryParseJson = (value: string): unknown | null => {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
};

const stripMarkdownCodeFence = (value: string): string => {
  const trimmed = value.trim();
  const match = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return match ? match[1].trim() : trimmed;
};

const extractBalancedJsonBlock = (value: string): string | null => {
  const source = value.trim();
  const firstBraceIndex = source.search(/[\[{]/);
  if (firstBraceIndex < 0) return null;
  const stack: string[] = [];
  let inString = false;
  let escaped = false;
  for (let index = firstBraceIndex; index < source.length; index += 1) {
    const ch = source[index];
    if (inString) {
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === '\\') {
        escaped = true;
        continue;
      }
      if (ch === '"') {
        inString = false;
      }
      continue;
    }
    if (ch === '"') {
      inString = true;
      continue;
    }
    if (ch === '{' || ch === '[') {
      stack.push(ch);
      continue;
    }
    if (ch === '}' || ch === ']') {
      const expected = ch === '}' ? '{' : '[';
      if (stack[stack.length - 1] !== expected) {
        return null;
      }
      stack.pop();
      if (stack.length === 0) {
        return source.slice(firstBraceIndex, index + 1);
      }
    }
  }
  return null;
};

const parseJsonFromText = (value: string): unknown | null => {
  const normalized = stripMarkdownCodeFence(value);
  const direct = tryParseJson(normalized);
  if (direct !== null) return direct;
  const balanced = extractBalancedJsonBlock(normalized);
  if (!balanced) return null;
  return tryParseJson(balanced);
};

const extractOriginalResponsePayload = (value: string): unknown | null => {
  const marker = 'Original Response';
  const markerIndex = value.indexOf(marker);
  if (markerIndex < 0) return null;
  const candidate = value.slice(markerIndex + marker.length).trim();
  return parseJsonFromText(candidate);
};

const extractResponseStructureText = (value: string): string | null => {
  const structureMarker = '## Response Structure';
  const originalMarker = '## Original Response';
  const structureIndex = value.indexOf(structureMarker);
  if (structureIndex < 0) return null;
  const originalIndex = value.indexOf(originalMarker, structureIndex + structureMarker.length);
  const endIndex = originalIndex >= 0 ? originalIndex : value.length;
  const structureText = value.slice(structureIndex + structureMarker.length, endIndex).trim();
  return structureText || null;
};

const extractFieldSemanticsFromResponseStructure = (value: string): Record<string, string> | null => {
  const structureText = extractResponseStructureText(value);
  if (!structureText) return null;
  const fieldSemantics: Record<string, string> = {};
  for (const line of structureText.split(/\r?\n/)) {
    const match = line.match(/^\s*-\s+\*\*([^*]+)\*\*:\s*(.*)$/);
    if (!match) continue;
    const fieldPath = match[1]?.trim();
    const rawDescription = match[2]?.replace(/\s*\(Type:\s*[^)]*\)\s*$/i, '').trim();
    if (!fieldPath || !rawDescription) continue;
    fieldSemantics[fieldPath] = rawDescription;
  }
  return Object.keys(fieldSemantics).length > 0 ? fieldSemantics : null;
};

const hasFieldSemantics = (value: Record<string, unknown>): boolean => {
  if (!isRecord(value.fieldSemantics)) return false;
  return Object.keys(value.fieldSemantics).length > 0;
};

const withFallbackFieldSemantics = (payload: unknown, sourceText: string): unknown => {
  if (!isRecord(payload) || hasFieldSemantics(payload)) {
    return payload;
  }
  const fieldSemantics = extractFieldSemanticsFromResponseStructure(sourceText);
  if (!fieldSemantics) return payload;
  return {
    ...payload,
    fieldSemantics,
  };
};

const normalizeMcpToolResult = (result: unknown): unknown => {
  if (!isRecord(result)) return result;
  const content = Array.isArray(result.content) ? result.content : [];
  for (const item of content) {
    if (!isRecord(item)) continue;
    const text = typeof item.text === 'string' ? item.text.trim() : '';
    if (!text) continue;
    const originalResponsePayload = extractOriginalResponsePayload(text);
    if (originalResponsePayload !== null) {
      return withFallbackFieldSemantics(originalResponsePayload, text);
    }
    const parsedText = parseJsonFromText(text);
    if (parsedText !== null) {
      return withFallbackFieldSemantics(parsedText, text);
    }
  }
  return result;
};

const extractMcpContentText = (result: unknown): string | null => {
  if (!isRecord(result)) return null;
  const content = Array.isArray(result.content) ? result.content : [];
  const texts = content
    .map((item) => (isRecord(item) && typeof item.text === 'string' ? item.text.trim() : ''))
    .filter(Boolean);
  return texts.length ? texts.join('\n\n') : null;
};

const normalizeConfig = (config: McpServerConfig) => {
  const serverUrl = typeof config.serverUrl === 'string' ? config.serverUrl.trim() : '';
  const requestTimeoutMs =
    typeof config.requestTimeoutMs === 'number'
      ? config.requestTimeoutMs
      : Number.parseInt(String(config.requestTimeoutMs ?? ''), 10);
  return {
    serverUrl,
    clientId: typeof config.clientId === 'string' ? config.clientId.trim() : '',
    clientSecret: typeof config.clientSecret === 'string' ? config.clientSecret.trim() : '',
    accessToken: typeof config.accessToken === 'string' ? config.accessToken.trim() : '',
    requestTimeoutMs:
      Number.isFinite(requestTimeoutMs) && requestTimeoutMs > 0
        ? requestTimeoutMs
        : DEFAULT_MCP_REQUEST_TIMEOUT_MS,
    protocolVersion:
      typeof config.protocolVersion === 'string' && config.protocolVersion.trim()
        ? config.protocolVersion.trim()
        : DEFAULT_MCP_PROTOCOL_VERSION,
    clientName:
      typeof config.clientName === 'string' && config.clientName.trim() ? config.clientName.trim() : 'bus-agent',
    clientVersion:
      typeof config.clientVersion === 'string' && config.clientVersion.trim()
        ? config.clientVersion.trim()
        : '1.0.0',
  };
};

const normalizeObjectSchema = (schema: unknown): McpAdaptedToolDefinition['parameters'] => {
  if (!isRecord(schema)) {
    return { type: 'object', properties: {} };
  }
  const properties = isRecord(schema.properties) ? schema.properties : {};
  const required = Array.isArray(schema.required)
    ? schema.required.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  return {
    type: 'object',
    properties,
    ...(required.length ? { required } : {}),
  };
};

const normalizeHeaders = (headers: Headers): Record<string, string> => {
  const result: Record<string, string> = {};
  headers.forEach((value, key) => {
    result[key.toLowerCase()] = value;
  });
  return result;
};

const buildHeaders = (config: ReturnType<typeof normalizeConfig>, sessionId?: string | null): Record<string, string> => ({
  Accept: DEFAULT_MCP_ACCEPT,
  'Content-Type': 'application/json',
  'MCP-Protocol-Version': config.protocolVersion,
  'User-Agent': DEFAULT_MCP_USER_AGENT,
  ...(config.clientId ? { 'CF-Access-Client-Id': config.clientId } : {}),
  ...(config.clientSecret ? { 'CF-Access-Client-Secret': config.clientSecret } : {}),
  ...(config.accessToken ? { 'X-Access-Token': config.accessToken } : {}),
  ...(sessionId ? { 'MCP-Session-Id': sessionId } : {}),
});

const postJson = async (
  serverUrl: string,
  headers: Record<string, string>,
  payload: Record<string, unknown>,
  timeoutMs: number
): Promise<HttpJsonResult> => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(serverUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const bodyText = await response.text();
    let json: unknown = null;
    if (bodyText.trim()) {
      try {
        json = JSON.parse(bodyText);
      } catch {
        json = null;
      }
    }
    return {
      ok: response.ok,
      status: response.status,
      headers: normalizeHeaders(response.headers),
      json,
      bodyText,
      ...(response.ok ? {} : { error: `HTTP ${response.status}` }),
    };
  } catch (error) {
    const isAbortError = error instanceof Error && error.name === 'AbortError';
    return {
      ok: false,
      status: null,
      headers: {},
      json: null,
      bodyText: '',
      error: isAbortError
        ? `MCP request timeout after ${timeoutMs}ms`
        : error instanceof Error
          ? error.message
          : String(error),
    };
  } finally {
    clearTimeout(timer);
  }
};

const extractRpcError = (value: unknown): string | null => {
  if (!isRecord(value) || !isRecord(value.error)) return null;
  const message = typeof value.error.message === 'string' ? value.error.message.trim() : '';
  return message || 'MCP RPC error';
};

const extractSessionId = (headers: Record<string, string>): string | null => {
  const sessionId = headers['mcp-session-id'];
  return typeof sessionId === 'string' && sessionId.trim() ? sessionId.trim() : null;
};

const extractServerInfo = (value: unknown): Record<string, unknown> | null => {
  if (!isRecord(value) || !isRecord(value.result) || !isRecord(value.result.serverInfo)) {
    return null;
  }
  return value.result.serverInfo;
};

const extractTools = (value: unknown): McpRawTool[] => {
  if (!isRecord(value) || !isRecord(value.result) || !Array.isArray(value.result.tools)) {
    return [];
  }
  return value.result.tools
    .filter((tool): tool is McpRawTool => isRecord(tool) && typeof tool.name === 'string')
    .map((tool) => ({
      ...tool,
      name: String(tool.name),
      ...(typeof tool.description === 'string' ? { description: tool.description } : {}),
    }));
};

const extractToolError = (result: unknown): string | null => {
  if (!isRecord(result) || result.isError !== true) return null;
  const content = Array.isArray(result.content) ? result.content : [];
  for (const item of content) {
    if (!isRecord(item)) continue;
    const text = typeof item.text === 'string' ? item.text.trim() : '';
    if (text) return text;
  }
  return 'MCP tool returned isError=true';
};

type McpBusinessError = {
  message: string;
  code: number | string | null;
};

const extractBusinessError = (result: unknown): McpBusinessError | null => {
  if (!isRecord(result) || result.success !== false) return null;
  const message =
    typeof result.message === 'string' && result.message.trim()
      ? result.message.trim()
      : typeof result.error === 'string' && result.error.trim()
        ? result.error.trim()
        : '';
  const code =
    typeof result.code === 'number' && Number.isFinite(result.code)
      ? result.code
      : typeof result.code === 'string' && result.code.trim()
        ? result.code.trim()
        : null;
  return {
    message: message || (code != null ? `MCP tool business error (${String(code)})` : 'MCP tool business error'),
    code,
  };
};

const buildStage = (
  stage: McpStageResult['stage'],
  startedAt: number,
  http: HttpJsonResult,
  error?: string
): McpStageResult => ({
  stage,
  ok: http.ok && !error,
  duration_ms: Date.now() - startedAt,
  http_status: http.status,
  ...(error ? { error } : {}),
});

async function initializeSession(configInput: McpServerConfig): Promise<McpSessionState> {
  const timestamp = Date.now();
  const config = normalizeConfig(configInput);
  if (!config.serverUrl) {
    return {
      configured: false,
      ok: false,
      targetUrl: null,
      protocolVersion: config.protocolVersion,
      sessionId: null,
      serverInfo: null,
      headers: {},
      stages: [],
      totalDurationMs: 0,
      rawInitialize: null,
      error: 'MCP_SERVER_URL is not configured',
    };
  }

  const stages: McpStageResult[] = [];
  const initializeStartedAt = Date.now();
  const initializeHeaders = buildHeaders(config);
  const initializePayload = {
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {
      protocolVersion: config.protocolVersion,
      capabilities: {},
      clientInfo: {
        name: config.clientName,
        version: config.clientVersion,
      },
    },
  };
  const initializeResult = await postJson(
    config.serverUrl,
    initializeHeaders,
    initializePayload,
    config.requestTimeoutMs
  );
  const initializeRpcError = extractRpcError(initializeResult.json);
  stages.push(buildStage('initialize', initializeStartedAt, initializeResult, initializeRpcError ?? undefined));
  if (!initializeResult.ok || initializeRpcError) {
    return {
      configured: true,
      ok: false,
      targetUrl: config.serverUrl,
      protocolVersion: config.protocolVersion,
      sessionId: extractSessionId(initializeResult.headers),
      serverInfo: extractServerInfo(initializeResult.json),
      headers: initializeHeaders,
      stages,
      totalDurationMs: Date.now() - timestamp,
      rawInitialize: initializeResult.json,
      error: initializeRpcError ?? initializeResult.error ?? 'initialize failed',
    };
  }

  if (!isRecord(initializeResult.json) || !isRecord(initializeResult.json.result)) {
    return {
      configured: true,
      ok: false,
      targetUrl: config.serverUrl,
      protocolVersion: config.protocolVersion,
      sessionId: extractSessionId(initializeResult.headers),
      serverInfo: extractServerInfo(initializeResult.json),
      headers: initializeHeaders,
      stages,
      totalDurationMs: Date.now() - timestamp,
      rawInitialize: initializeResult.json,
      error: 'initialize returned invalid payload',
    };
  }

  const sessionId = extractSessionId(initializeResult.headers);
  const followHeaders = buildHeaders(config, sessionId);
  const initializedStartedAt = Date.now();
  const initializedResult = await postJson(
    config.serverUrl,
    followHeaders,
    {
      jsonrpc: '2.0',
      method: 'notifications/initialized',
      params: {},
    },
    config.requestTimeoutMs
  );
  const initializedRpcError = extractRpcError(initializedResult.json);
  stages.push(
    buildStage('notifications/initialized', initializedStartedAt, initializedResult, initializedRpcError ?? undefined)
  );
  if (!initializedResult.ok || initializedRpcError) {
    return {
      configured: true,
      ok: false,
      targetUrl: config.serverUrl,
      protocolVersion: config.protocolVersion,
      sessionId,
      serverInfo: extractServerInfo(initializeResult.json),
      headers: followHeaders,
      stages,
      totalDurationMs: Date.now() - timestamp,
      rawInitialize: initializeResult.json,
      error: initializedRpcError ?? initializedResult.error ?? 'notifications/initialized failed',
    };
  }

  return {
    configured: true,
    ok: true,
    targetUrl: config.serverUrl,
    protocolVersion: config.protocolVersion,
    sessionId,
    serverInfo: extractServerInfo(initializeResult.json),
    headers: followHeaders,
    stages,
    totalDurationMs: Date.now() - timestamp,
    rawInitialize: initializeResult.json,
  };
}

export function adaptMcpToolDefinition(rawTool: McpRawTool): McpAdaptedToolDefinition {
  return {
    name: String(rawTool.name ?? ''),
    description: typeof rawTool.description === 'string' ? rawTool.description : '',
    parameters: normalizeObjectSchema(rawTool.inputSchema),
  };
}

export function buildMcpToolSummary(rawTool: McpRawTool): McpToolSummary {
  const adapted = adaptMcpToolDefinition(rawTool);
  const required = adapted.parameters.required ?? [];
  return {
    name: adapted.name,
    description: adapted.description,
    required_count: required.length,
    property_count: Object.keys(adapted.parameters.properties).length,
    input_schema: rawTool.inputSchema ?? null,
    adapted_parameters: adapted.parameters,
  };
}

export function buildMcpStubArguments(inputSchema: unknown): Record<string, unknown> {
  const normalized = normalizeObjectSchema(inputSchema);
  const propertyEntries = Object.entries(normalized.properties);
  const targetKeys =
    normalized.required && normalized.required.length
      ? normalized.required
      : propertyEntries.slice(0, 3).map(([key]) => key);
  const args: Record<string, unknown> = {};
  for (const key of targetKeys) {
    const field = normalized.properties[key];
    if (isRecord(field) && Array.isArray(field.enum) && field.enum.length > 0) {
      args[key] = field.enum[0];
      continue;
    }
    const type = isRecord(field) && typeof field.type === 'string' ? field.type : 'string';
    if (type === 'integer' || type === 'number') {
      args[key] = 1;
    } else if (type === 'boolean') {
      args[key] = false;
    } else if (type === 'array') {
      args[key] = [];
    } else if (type === 'object') {
      args[key] = {};
    } else {
      args[key] = 'test';
    }
  }
  return args;
}

export async function probeMcpServer(config: McpServerConfig): Promise<McpProbeResult> {
  const startedAt = Date.now();
  const session = await initializeSession(config);
  const timestamp = new Date().toISOString();
  if (!session.configured || !session.ok || !session.targetUrl) {
    return {
      configured: session.configured,
      ok: false,
      target_url: session.targetUrl,
      protocol_version: session.protocolVersion,
      session_id: session.sessionId,
      server_info: session.serverInfo,
      stages: session.stages,
      total_duration_ms: Date.now() - startedAt,
      tools: [],
      tool_count: 0,
      raw_initialize: session.rawInitialize,
      raw_tools_list: null,
      ...(session.error ? { error: session.error } : {}),
      timestamp,
    };
  }

  const toolsStartedAt = Date.now();
  const toolsResult = await postJson(
    session.targetUrl,
    session.headers,
    {
      jsonrpc: '2.0',
      id: 2,
      method: 'tools/list',
      params: {},
    },
    normalizeConfig(config).requestTimeoutMs
  );
  const toolsRpcError = extractRpcError(toolsResult.json);
  const stages = [...session.stages, buildStage('tools/list', toolsStartedAt, toolsResult, toolsRpcError ?? undefined)];
  const tools = extractTools(toolsResult.json);
  return {
    configured: true,
    ok: toolsResult.ok && !toolsRpcError,
    target_url: session.targetUrl,
    protocol_version: session.protocolVersion,
    session_id: session.sessionId,
    server_info: session.serverInfo,
    stages,
    total_duration_ms: Date.now() - startedAt,
    tools,
    tool_count: tools.length,
    raw_initialize: session.rawInitialize,
    raw_tools_list: toolsResult.json,
    ...((toolsRpcError ?? toolsResult.error) ? { error: toolsRpcError ?? toolsResult.error ?? 'tools/list failed' } : {}),
    timestamp,
  };
}

export async function listMcpToolsForAgent(config: McpServerConfig): Promise<McpAdaptedToolDefinition[]> {
  const probe = await probeMcpServer(config);
  if (!probe.ok) {
    throw new Error(probe.error ?? 'Failed to list MCP tools');
  }
  return probe.tools.map(adaptMcpToolDefinition);
}

export async function callMcpToolForAgent(
  config: McpServerConfig,
  name: string,
  args: Record<string, unknown>
): Promise<McpAgentToolResult> {
  const result = await callMcpToolDebug(config, name, args);
  if (!result.ok) {
    return { success: false, error: result.error ?? 'MCP tool call failed' };
  }
  const businessError = extractBusinessError(result.result);
  if (businessError) {
    return {
      success: false,
      error: businessError.message,
      ...(businessError.code != null ? { error_code: businessError.code } : {}),
    };
  }
  const normalizedData =
    isRecord(result.result) && !Array.isArray(result.result)
      ? withMessageSources(result.result, extractMessageSources(result.result, 'mcp'))
      : result.result;
  return { success: true, data: normalizedData };
}

export async function getMcpToolDetail(config: McpServerConfig, name: string): Promise<McpToolDetailResult> {
  const probe = await probeMcpServer(config);
  const timestamp = new Date().toISOString();
  if (!probe.configured || !probe.ok) {
    return {
      configured: probe.configured,
      ok: false,
      target_url: probe.target_url,
      protocol_version: probe.protocol_version,
      tool_name: name,
      stages: probe.stages,
      total_duration_ms: probe.total_duration_ms,
      ...(probe.error ? { error: probe.error } : {}),
      timestamp,
    };
  }
  const tool = probe.tools.find((item) => item.name === name);
  if (!tool) {
    return {
      configured: true,
      ok: false,
      target_url: probe.target_url,
      protocol_version: probe.protocol_version,
      tool_name: name,
      stages: probe.stages,
      total_duration_ms: probe.total_duration_ms,
      error: 'tool not found',
      timestamp,
    };
  }
  return {
    configured: true,
    ok: true,
    target_url: probe.target_url,
    protocol_version: probe.protocol_version,
    tool_name: name,
    stages: probe.stages,
    total_duration_ms: probe.total_duration_ms,
    raw_tool: tool,
    adapted_tool: adaptMcpToolDefinition(tool),
    timestamp,
  };
}

export async function callMcpToolDebug(
  config: McpServerConfig,
  name: string,
  args: Record<string, unknown>
): Promise<McpToolCallDebugResult> {
  const startedAt = Date.now();
  const session = await initializeSession(config);
  const timestamp = new Date().toISOString();
  if (!session.configured || !session.ok || !session.targetUrl) {
    return {
      configured: session.configured,
      ok: false,
      target_url: session.targetUrl,
      protocol_version: session.protocolVersion,
      tool_name: name,
      arguments: args,
      stages: session.stages,
      total_duration_ms: Date.now() - startedAt,
      raw_result: null,
      result: null,
      agent_received_content: null,
      ...(session.error ? { error: session.error } : {}),
      timestamp,
    };
  }

  const callStartedAt = Date.now();
  const callResult = await postJson(
    session.targetUrl,
    session.headers,
    {
      jsonrpc: '2.0',
      id: 3,
      method: 'tools/call',
      params: {
        name,
        arguments: args,
      },
    },
    normalizeConfig(config).requestTimeoutMs
  );
  const rpcError = extractRpcError(callResult.json);
  const rawResult = isRecord(callResult.json) ? callResult.json.result ?? null : null;
  const normalizedResult = normalizeMcpToolResult(rawResult);
  const agentReceivedContent = extractMcpContentText(rawResult);
  const businessError = extractBusinessError(normalizedResult);
  const toolError = extractToolError(rawResult) ?? businessError?.message ?? null;
  const error = rpcError ?? toolError ?? callResult.error;
  const stages = [...session.stages, buildStage('tools/call', callStartedAt, callResult, error ?? undefined)];
  return {
    configured: true,
    ok: callResult.ok && !error,
    target_url: session.targetUrl,
    protocol_version: session.protocolVersion,
    tool_name: name,
    arguments: args,
    stages,
    total_duration_ms: Date.now() - startedAt,
    raw_result: rawResult,
    result: normalizedResult,
    agent_received_content: agentReceivedContent,
    ...(error ? { error } : {}),
    timestamp,
  };
}
