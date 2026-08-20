import {
  buildContextHistoryOptions,
  buildContextFromHistory,
  looksLikeInternalInstructionLeak,
  type ChatCompletionMessage,
  type HistoryMessage,
  type ToolCallMessage,
} from './context';
import { resolveFurtherInfoDisplayMessage } from './clarification-state';
import { getStructuredReportDataSourceConfig } from './structured-report-data-sources';
import {
  buildMcpDataSource,
  extractMessageSources,
  mergeMessageSources,
  type MessageSource,
} from '../../shared/message-sources';
import { applyMcpFieldSemanticsPatch } from '../../shared/mcp-field-semantics';
import { buildServerTimeSystemPrompt } from './server-time-context';

export type WorkerToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_unit_report'
  | 'generate_route_report'
  | 'generate_station_report'
  | 'generate_accident_investigation_report'
  | 'consult_omni'
  | 'consult_driver_expert'
  | 'consult_vehicle_expert'
  | 'consult_unit_expert'
  | 'consult_route_expert'
  | 'consult_station_expert'
  | 'consult_incident_expert'
  | 'rule_reply'
  | 'rule_asker'
  | 'rule_builder';

export type StructuredReportWorkerToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_unit_report'
  | 'generate_route_report'
  | 'generate_station_report'
  | 'generate_accident_investigation_report';

export type StructuredManagementReportWorkerToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_unit_report'
  | 'generate_route_report'
  | 'generate_station_report'
  | 'generate_accident_investigation_report';

export interface WorkerToolCall {
  tool: WorkerToolName;
  args: Record<string, unknown>;
}

type ToolCall = ToolCallMessage;

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
  error_code?: number | string;
}

export interface ToolUsage {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolProviderDebugInfo {
  provider_mode: 'local' | 'mcp' | 'hybrid' | 'scoped';
  base_provider_mode?: 'local' | 'mcp' | 'hybrid' | 'scoped';
  mcp_configured: boolean;
  mcp_visible?: boolean | null;
  mcp_list_failed?: boolean;
  mcp_list_error?: string | null;
  mcp_tool_names?: string[];
  allow_list?: string[];
  kb_tool_enabled?: boolean;
  kb_api_configured?: boolean;
  kb_default_id?: string;
}

export interface ToolProvider {
  listTools(): Promise<ToolDefinition[]>;
  callTool(name: string, args: Record<string, unknown>): Promise<ToolResult>;
  getDebugInfo?(): Promise<ToolProviderDebugInfo> | ToolProviderDebugInfo;
}

export interface StructuredManagementReportRuntimeConfig {
  reportType: string;
  noDataError: { error: string; message: string };
  formatMismatchError: string;
  missingDataRetryLimit: number;
  maxDataToolCallsWithoutHit: number | null;
  normalizeReport: (
    report: Record<string, unknown>,
    sourceData: Record<string, unknown> | null
  ) => Record<string, unknown>;
  hasCompleteReport: (report: Record<string, unknown>) => boolean;
  hasTemplateMarkerNotation: (report: Record<string, unknown>) => boolean;
  extractRequestedEntityToken?: (prompt: string) => string | null;
  doesGetPayloadMatchRequestedEntity?: (
    requestedEntityToken: string | null,
    payload: Record<string, unknown>
  ) => boolean;
}

export interface WorkerRuntimeOptions {
  prefetchedSourceData?: Record<string, unknown> | null;
  systemPromptPrefix?: string;
  blockedResponse?: {
    content: string;
    metadata?: Record<string, unknown>;
  };
  metadata?: Record<string, unknown>;
  suppressStageText?: boolean;
  suppressOpeningText?: boolean;
  suppressClosingText?: boolean;
  onAssistantDelta?: (delta: string) => void;
  onAssistantProgress?: (progress: AssistantProgressUpdate) => void;
  onAgentEvent?: (event: WorkerAgentStreamEvent) => void;
  onProbeEvent?: (event: WorkerProbeStageEvent) => void;
}

type WorkerRunnerEnv = {
  OPENAI_MODEL?: string;
  OPENAI_WORKER_MODEL?: string;
  OPENAI_EXPERT_THINKING_ENABLED?: string;
  OPENAI_STREAM_DIAGNOSTICS?: string;
};

type OpeningMode = 'consult' | 'report' | 'other' | 'pre_router';
const PRE_ROUTER_OPENING_HISTORY_MESSAGES = 6;
const PRE_ROUTER_OPENING_HISTORY_CHARS = 600;
const INTERNAL_LEAK_BLOCKED_FALLBACK = '当前回答生成异常，已阻止内部指令输出。请重新发起查询。';

export type AssistantProgressCode =
  | 'prefetched_source_data_ready'
  | 'first_meaningful_external_data_hit';

export interface AssistantProgressUpdate {
  code: AssistantProgressCode;
  text: string;
}

export type WorkerProbeStageEvent = {
  type: 'probe_stage';
  stage: string;
  detail?: Record<string, unknown>;
};

export type WorkerAgentStreamEvent =
  | { type: 'tool_call_delta'; index: number; id?: string; tool?: string; argumentsDelta?: string }
  | { type: 'reasoning_delta'; field: 'reasoning' | 'reasoning_content'; delta: string }
  | { type: 'tool_call_ready'; id: string; tool: string; args: Record<string, unknown> }
  | { type: 'tool_execution_started'; id: string; tool: string; args: Record<string, unknown> }
  | {
      type: 'tool_execution_completed';
      id: string;
      tool: string;
      success: boolean;
      resultSummary?: Record<string, unknown>;
    }
  | { type: 'tool_execution_failed'; id: string; tool: string; error: string };

type WorkerRunnerDeps = {
  DEFAULT_MODEL: string;
  MAX_TOOL_ITERATIONS: number;
  WORKER_SKILLS: Record<WorkerToolName, string>;
  STRUCTURED_REPORT_WORKER_TOOLS: ReadonlySet<WorkerToolName>;
  createToolProvider: (env: any) => ToolProvider;
  getStructuredManagementReportRuntimeConfig: (
    workerTool: WorkerToolName
  ) => StructuredManagementReportRuntimeConfig | null;
  toOpenAIToolSchema: (tool: ToolDefinition) => { type: 'function'; function: ToolDefinition };
  callOpenAI: (
    env: any,
    options: {
      model: string;
      temperature?: number;
      messages: ChatCompletionMessage[];
      responseFormat?: 'json_object';
      enableThinking?: boolean;
    }
  ) => Promise<string>;
  callOpenAIStreamText: (
    env: any,
    options: {
      model: string;
      temperature?: number;
      messages: ChatCompletionMessage[];
      enableThinking?: boolean;
    }
  ) => Promise<string>;
  callOpenAIWithTools: (
    env: any,
    options: {
      model: string;
      temperature?: number;
      messages: ChatCompletionMessage[];
      tools: Array<{ type: 'function'; function: ToolDefinition }>;
      enableThinking?: boolean;
    }
  ) => Promise<{ content?: string; toolCalls?: ToolCall[] }>;
  callOpenAIWithToolsStream: (
    env: any,
    options: {
      model: string;
      temperature?: number;
      messages: ChatCompletionMessage[];
      tools: Array<{ type: 'function'; function: ToolDefinition }>;
      enableThinking?: boolean;
      onTextDelta?: (delta: string) => void;
      onReasoningDelta?: (delta: {
        delta: string;
        field: 'reasoning' | 'reasoning_content';
      }) => void;
      onToolCallDelta?: (delta: {
        index: number;
        id?: string;
        tool?: string;
        argumentsDelta?: string;
      }) => void;
      onToolCallReady?: (toolCall: ToolCall) => void;
    }
  ) => Promise<{ content?: string; toolCalls?: ToolCall[]; finishReason?: string }>;
  callOpenAIStreamWithTools: (
    env: any,
    options: {
      model: string;
      temperature?: number;
      messages: ChatCompletionMessage[];
      tools: Array<{ type: 'function'; function: ToolDefinition }>;
      enableThinking?: boolean;
    }
  ) => Promise<ReadableStream>;
  safeJsonParse: (value: string) => unknown;
  isRecord: (value: unknown) => value is Record<string, unknown>;
  buildStructuredReportNoDataError: (workerTool: WorkerToolName) => string;
  buildStructuredReportFormatMismatchError: (workerTool: WorkerToolName) => string;
  buildStructuredReportMissingDataPrompt: (
    workerTool: WorkerToolName,
    mode: 'missing_read_call' | 'read_failed' | 'no_data_hit' | 'missing_get_hit'
  ) => string;
};

const INTERNAL_NON_DATA_TOOL_NAMES = new Set([
  'get_rule',
  'get_rule_draft',
  'update_rule_draft',
  'submit_rule_turn',
  'rule_exit',
  'request_further_info',
]);

function isInternalNonDataToolName(name: string): boolean {
  return INTERNAL_NON_DATA_TOOL_NAMES.has(name);
}

const OPENAI_TOOL_NAME_MAX_LENGTH = 64;

function hashToolName(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function sanitizeToolNamePart(value: string): string {
  return value
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function createShortModelToolName(
  providerName: string,
  index: number,
  usedNames: Set<string>
): string {
  const hash = hashToolName(providerName);
  const lastPart = sanitizeToolNamePart(providerName.split('_').filter(Boolean).pop() ?? 'tool');
  const prefix = `mcp_${lastPart || 'tool'}`;
  const suffix = `_${hash}`;
  const maxPrefixLength = OPENAI_TOOL_NAME_MAX_LENGTH - suffix.length;
  let candidate = `${prefix.slice(0, Math.max(1, maxPrefixLength))}${suffix}`;
  if (!usedNames.has(candidate)) {
    return candidate;
  }

  const indexedSuffix = `_${index}_${hash}`;
  const indexedMaxPrefixLength = OPENAI_TOOL_NAME_MAX_LENGTH - indexedSuffix.length;
  candidate = `${prefix.slice(0, Math.max(1, indexedMaxPrefixLength))}${indexedSuffix}`;
  return candidate;
}

function buildModelToolExposure(tools: ToolDefinition[]): {
  modelTools: ToolDefinition[];
  modelNameToProviderName: Map<string, string>;
  aliases: Array<{ model_name: string; provider_name: string }>;
} {
  const usedNames = new Set<string>();
  const modelNameToProviderName = new Map<string, string>();
  const aliases: Array<{ model_name: string; provider_name: string }> = [];

  const modelTools = tools.map((tool, index) => {
    const needsAlias = tool.name.length > OPENAI_TOOL_NAME_MAX_LENGTH || usedNames.has(tool.name);
    const modelName = needsAlias
      ? createShortModelToolName(tool.name, index, usedNames)
      : tool.name;
    usedNames.add(modelName);
    modelNameToProviderName.set(modelName, tool.name);

    if (!needsAlias) {
      return tool;
    }

    aliases.push({ model_name: modelName, provider_name: tool.name });
    return {
      ...tool,
      name: modelName,
      description: [
        tool.description,
        `Original MCP tool name: ${tool.name}. Use this function for that MCP endpoint.`,
      ]
        .filter(Boolean)
        .join('\n'),
    };
  });

  return { modelTools, modelNameToProviderName, aliases };
}

function hasMeaningfulToolData(data: unknown): boolean {
  if (data == null) return false;
  if (Array.isArray(data)) return data.length > 0;
  if (typeof data === 'string') return data.trim().length > 0;
  if (typeof data === 'number' || typeof data === 'boolean') return true;
  if (typeof data !== 'object') return false;
  return Object.keys(data as Record<string, unknown>).length > 0;
}

function hasMeaningfulProgressData(data: unknown): boolean {
  if (!hasMeaningfulToolData(data)) {
    return false;
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return true;
  }

  const record = data as Record<string, unknown>;
  if (!Object.prototype.hasOwnProperty.call(record, 'result') || record.result != null) {
    return true;
  }

  const envelopeOnlyKeys = new Set([
    'result',
    'raw_result',
    'sources',
    '_sources',
    'code',
    'status',
    'message',
    'msg',
    'success',
    'error',
    'error_code',
  ]);
  return Object.entries(record).some(
    ([key, value]) => !envelopeOnlyKeys.has(key) && hasMeaningfulToolData(value)
  );
}

function buildToolMessageContent(toolName: string, result: ToolResult): string {
  const isExternalDataTool = !isInternalNonDataToolName(toolName);
  if (isExternalDataTool && result.success === true && result.data !== undefined) {
    const agentFacingData = applyMcpFieldSemanticsPatch(toolName, result.data, {
      stripAmbiguousFields: true,
    });
    return JSON.stringify(agentFacingData, null, 2);
  }
  return JSON.stringify(result, null, 2);
}

function normalizeConversationalArrayContent(value: unknown): string | null {
  if (!Array.isArray(value) || value.length === 0) {
    return null;
  }

  const primitiveItems = value.filter(
    (item) =>
      typeof item === 'string' ||
      typeof item === 'number' ||
      typeof item === 'boolean' ||
      item == null
  );
  if (primitiveItems.length !== value.length) {
    return null;
  }

  const stringCount = value.filter(
    (item) => typeof item === 'string' && item.trim().length > 0
  ).length;
  if (stringCount === 0) {
    return null;
  }

  const normalizedLines = value
    .map((item, index, items) => {
      if (typeof item === 'string') {
        const text = item.trim();
        return text || null;
      }

      // Some malformed rich-text serializations leak separator sentinels such as 0
      // between text blocks. When the array is otherwise text-heavy, drop them.
      if (
        item === 0 &&
        stringCount >= 2 &&
        index > 0 &&
        index < items.length - 1 &&
        typeof items[index - 1] === 'string' &&
        typeof items[index + 1] === 'string'
      ) {
        return null;
      }

      if (typeof item === 'number' || typeof item === 'boolean') {
        return String(item);
      }

      return null;
    })
    .filter((item): item is string => Boolean(item));

  if (!normalizedLines.length) {
    return null;
  }

  return normalizedLines.join('\n');
}

function normalizeWorkerFinalContent(
  workerTool: WorkerToolName,
  rawContent: string,
  parsedContent: unknown
): string {
  if (
    (workerTool === 'consult_omni' ||
      workerTool === 'consult_driver_expert' ||
      workerTool === 'consult_vehicle_expert' ||
      workerTool === 'consult_unit_expert' ||
      workerTool === 'consult_route_expert' ||
      workerTool === 'consult_station_expert' ||
      workerTool === 'consult_incident_expert') &&
    Array.isArray(parsedContent)
  ) {
    const conversational = normalizeConversationalArrayContent(parsedContent);
    if (conversational) {
      return conversational;
    }
  }

  if (parsedContent && typeof parsedContent === 'object') {
    return JSON.stringify(parsedContent, null, 2);
  }

  return rawContent;
}

function buildStructuredReportParseFailureMetadata(rawContent: string): Record<string, unknown> {
  return {
    structured_report_failure_stage: 'parse_final_content',
    structured_report_raw_content: rawContent,
    structured_report_raw_content_length: rawContent.length,
  };
}

function resolveOpeningMode(workerTool: WorkerToolName): OpeningMode | null {
  if (
    workerTool === 'consult_omni' ||
    workerTool === 'consult_driver_expert' ||
    workerTool === 'consult_vehicle_expert' ||
    workerTool === 'consult_unit_expert' ||
    workerTool === 'consult_route_expert' ||
    workerTool === 'consult_station_expert' ||
    workerTool === 'consult_incident_expert'
  ) {
    return 'consult';
  }

  if (
    workerTool === 'generate_driver_report' ||
    workerTool === 'generate_vehicle_report' ||
    workerTool === 'generate_unit_report' ||
    workerTool === 'generate_route_report' ||
    workerTool === 'generate_station_report' ||
    workerTool === 'generate_accident_investigation_report'
  ) {
    return 'report';
  }

  return null;
}

function supportsClosingStep(
  workerTool: WorkerToolName
): workerTool is StructuredReportWorkerToolName {
  return (
    workerTool === 'generate_driver_report' ||
    workerTool === 'generate_vehicle_report' ||
    workerTool === 'generate_unit_report' ||
    workerTool === 'generate_route_report' ||
    workerTool === 'generate_station_report' ||
    workerTool === 'generate_accident_investigation_report'
  );
}

function supportsConversationalToolUseGuardrails(workerTool: WorkerToolName): boolean {
  // Keep this list in sync with natural-language expert workers that can call data tools.
  // Structured report workers are intentionally excluded because they must preserve strict JSON output.
  return (
    workerTool === 'consult_omni' ||
    workerTool === 'consult_driver_expert' ||
    workerTool === 'consult_vehicle_expert' ||
    workerTool === 'consult_unit_expert' ||
    workerTool === 'consult_route_expert' ||
    workerTool === 'consult_station_expert' ||
    workerTool === 'consult_incident_expert'
  );
}

function supportsRiskScoreSemanticsGuardrail(workerTool: WorkerToolName): boolean {
  return supportsConversationalToolUseGuardrails(workerTool) || supportsClosingStep(workerTool);
}

function isConversationalWorkerTool(workerTool: WorkerToolName): boolean {
  return supportsConversationalToolUseGuardrails(workerTool);
}

function buildConversationalVisibleOutputGuardrail(workerTool: WorkerToolName): string {
  if (!isConversationalWorkerTool(workerTool)) {
    return '';
  }

  return [
    '',
    '',
    '用户可见输出要求：',
    '- 面向用户的最终回答必须是自然语言，只回答业务结论、必要的数据口径和无法确认项。',
    '- 即使真实调用了工具，也不要展示工具选择依据、工具名称、schema 字段名、入参推导、调用步骤或“调用工具/调用该工具”等内部执行说明；除非用户明确询问工具接入情况。',
    '- 不要用“根据工具列表”“当前可用工具”“参数设为”等方式解释你的查询规划。',
  ].join('\n');
}

function isExpertWorkerTool(workerTool: WorkerToolName): boolean {
  return (
    workerTool === 'consult_driver_expert' ||
    workerTool === 'consult_vehicle_expert' ||
    workerTool === 'consult_unit_expert' ||
    workerTool === 'consult_route_expert' ||
    workerTool === 'consult_station_expert' ||
    workerTool === 'consult_incident_expert'
  );
}

function isExpertThinkingEnabled(env: WorkerRunnerEnv): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    String(env.OPENAI_EXPERT_THINKING_ENABLED ?? '')
      .trim()
      .toLowerCase()
  );
}

function summarizeToolResultForStream(result: ToolResult): Record<string, unknown> {
  const data = result.data;
  let dataShape: string | undefined;
  let dataSize: number | undefined;
  let dataJsonChars: number | undefined;
  let resultShape: string | undefined;
  let resultCount: number | undefined;
  let resultJsonChars: number | undefined;
  if (data !== undefined) {
    try {
      dataJsonChars = JSON.stringify(data).length;
    } catch {
      dataJsonChars = undefined;
    }
  }
  if (Array.isArray(data)) {
    dataShape = 'array';
    dataSize = data.length;
    resultCount = data.length;
    resultJsonChars = dataJsonChars;
  } else if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>;
    dataShape = 'object';
    dataSize = Object.keys(record).length;
    if (Object.prototype.hasOwnProperty.call(record, 'result')) {
      const payload = record.result;
      try {
        resultJsonChars = JSON.stringify(payload).length;
      } catch {
        resultJsonChars = undefined;
      }
      if (Array.isArray(payload)) {
        resultShape = 'array';
        resultCount = payload.length;
      } else if (payload && typeof payload === 'object') {
        resultShape = 'object';
        resultCount = Object.keys(payload as Record<string, unknown>).length;
      } else if (typeof payload === 'string') {
        resultShape = 'string';
        resultCount = payload.length;
      } else if (payload != null) {
        resultShape = typeof payload;
      } else {
        resultShape = 'null';
      }
    }
  } else if (typeof data === 'string') {
    dataShape = 'string';
    dataSize = data.length;
  } else if (data != null) {
    dataShape = typeof data;
  }
  return {
    success: result.success === true,
    ...(result.error ? { error: result.error } : {}),
    ...(result.error_code !== undefined ? { error_code: result.error_code } : {}),
    ...(dataShape ? { data_shape: dataShape } : {}),
    ...(dataSize !== undefined ? { data_size: dataSize } : {}),
    ...(dataJsonChars !== undefined ? { data_json_chars: dataJsonChars } : {}),
    ...(resultShape ? { result_shape: resultShape } : {}),
    ...(resultCount !== undefined ? { result_count: resultCount } : {}),
    ...(resultJsonChars !== undefined ? { result_json_chars: resultJsonChars } : {}),
  };
}

function cleanStageText(value: string): string {
  return value
    .replace(/^["'\s]+|["'\s]+$/g, '')
    .replace(/\r\n/g, '\n')
    .trim();
}

function looksLikeEmptyStageText(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return (
    normalized === '' ||
    normalized === 'none' ||
    normalized === 'null' ||
    normalized === 'no opening'
  );
}

function truncateOpeningHistoryContent(value: string): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= PRE_ROUTER_OPENING_HISTORY_CHARS) {
    return normalized;
  }
  return `${normalized.slice(0, PRE_ROUTER_OPENING_HISTORY_CHARS)}...`;
}

function buildOpeningHistoryContext(
  historyMessages: HistoryMessage[] = [],
  env?: WorkerRunnerEnv
): ChatCompletionMessage[] {
  const history = buildContextFromHistory(
    historyMessages,
    PRE_ROUTER_OPENING_HISTORY_MESSAGES,
    buildContextHistoryOptions(env, 'pre_router_opening')
  )
    .map((message) => ({
      ...message,
      content: truncateOpeningHistoryContent(message.content),
    }))
    .filter((message) => message.content);

  if (!history.length) {
    return [];
  }

  return [
    {
      role: 'user',
      content:
        '下面是最近三轮以内的对话历史，仅用于判断当前用户这句话是否延续上一轮任务、补充参数或确认对象。开场说明仍必须面向当前用户请求，不要复述历史正文。',
    },
    ...history,
  ];
}

function buildOpeningStepPrompt(
  env: WorkerRunnerEnv,
  workerTool: WorkerToolName | null,
  openingMode: OpeningMode,
  userQuery: string,
  availableTools: ToolDefinition[],
  historyMessages: HistoryMessage[] = []
): ChatCompletionMessage[] {
  const toolNames =
    availableTools
      .map((tool) => tool.name)
      .sort()
      .join(', ') || 'none';
  const historyContext =
    openingMode === 'pre_router' ? buildOpeningHistoryContext(historyMessages, env) : [];
  return [
    {
      role: 'system',
      content: [
        '你负责在执行任何工具之前，为助手生成一句简短的开场说明。',
        '请使用与用户相同的语言回复。',
        '只输出一句纯文本，不要使用项目符号、列表或 Markdown。',
        '不要提及内部推理、工具、MCP、函数调用或实现细节。',
        '不要声称任何结果已经被验证、确认或生成完成。',
        openingMode === 'pre_router'
          ? '如果用户只是寒暄、致谢、确认、取消，或没有提出可处理任务，请只输出：NONE'
          : '如果当前请求不需要开场说明，请只输出：NONE',
        '开场说明必须表达“正在处理”，不能表达“已经完成”。',
        '不要说或暗示报告或结果已经生成、完成、交付或写好。',
        '不要使用“已生成”“已完成”“已经写好”“generated”“completed”等完成态表述。',
        openingMode === 'pre_router'
          ? '请只基于用户这句话生成一句自然的处理中开场，可以表达正在理解需求、整理关键信息或准备核对相关信息；如果用户原话已经明确要求报告、查询或分析，可以贴合该主题表达；不要提及问题类型判断、worker、工具或实现细节，不要凭空假定任务类型。'
          : openingMode === 'report'
            ? '当前任务已由上游明确判定为报告生成类。请结合用户这句话，自然生成一句贴合主题的处理中开场，可以灵活提到正在整理、汇总或准备该主题的报告内容；但不要声称已经找到、确认、定位到相关数据，也不要暗示报告已经生成。'
            : openingMode === 'consult'
              ? '当前任务已由上游明确判定为咨询/查询类。请结合用户这句话，自然生成一句贴合主题的处理中开场，可以灵活提到正在查询、核对、分析或了解用户关心的信息；但不要把它表述成报告生成任务，也不要声称已经找到、确认、定位到相关数据。'
              : '当前任务使用通用开场说明。请结合用户这句话，自然生成一句简短的处理中开场，不要引入额外任务类型判断，也不要预先声称结果已经明确。',
        workerTool
          ? `当前 worker：${workerTool}。当前 opening mode：${openingMode}。当前可见工具：${toolNames}。`
          : `当前 opening mode：${openingMode}。当前尚未选择 worker。当前可见工具：${toolNames}。`,
      ].join('\n'),
    },
    ...historyContext,
    {
      role: 'user',
      content: userQuery,
    },
  ];
}

function buildClosingStepPrompt(
  workerTool: StructuredReportWorkerToolName,
  userQuery: string,
  finalContent: string
): ChatCompletionMessage[] {
  void workerTool;
  return [
    {
      role: 'system',
      content: [
        '你负责在报告正文已经生成后，补一句简短的收尾说明。',
        '请使用与用户相同的语言回复。',
        '只输出一句纯文本，不要使用项目符号、列表或 Markdown。',
        '这句话应自然邀请用户继续索取更多细节、依据或补充信息。',
        '不要复述报告内容，不要提及内部推理、工具、MCP 或函数调用。',
      ].join('\n'),
    },
    {
      role: 'user',
      content: `用户请求：\n${userQuery}\n\n报告内容：\n${finalContent}`,
    },
  ];
}

function buildProgressStepPrompt(
  workerTool: WorkerToolName,
  progressCode: AssistantProgressCode,
  userQuery: string
): ChatCompletionMessage[] {
  const eventDescription =
    progressCode === 'prefetched_source_data_ready'
      ? '系统已经获得了支撑当前请求的预取数据。'
      : '系统已经命中了与当前请求相关的第一批有效外部数据。';
  return [
    {
      role: 'system',
      content: [
        '你负责在助手处理中途生成一句简短的阶段性进展提示。',
        '请使用与用户相同的语言回复。',
        '只输出一句纯文本，不要使用项目符号、列表或 Markdown。',
        `当前已发生的真实事件：${eventDescription}`,
        '请结合用户原话和当前任务，自然表达“已有真实进展，仍在继续整理、核对或分析”。',
        '不要声称最终结论已经确认，不要声称报告已经完成，不要提及工具、MCP、函数调用或实现细节。',
        `当前 worker：${workerTool}。当前 progress code：${progressCode}。`,
      ].join('\n'),
    },
    {
      role: 'user',
      content: userQuery,
    },
  ];
}

export function createWorkerRunner(deps: WorkerRunnerDeps) {
  const streamShortModelText = async (
    env: WorkerRunnerEnv,
    options: {
      messages: ChatCompletionMessage[];
      suppressNone?: boolean;
      onDelta: (delta: string, fullText: string) => void;
    }
  ): Promise<string> => {
    let fullText = '';
    let bufferedPrefix = '';
    let prefixReleased = !options.suppressNone;

    await deps.callOpenAIWithToolsStream(env, {
      model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
      temperature: 0.2,
      messages: options.messages,
      tools: [],
      enableThinking: false,
      onTextDelta(delta) {
        fullText += delta;
        if (prefixReleased) {
          options.onDelta(delta, fullText);
          return;
        }

        bufferedPrefix += delta;
        const normalized = bufferedPrefix.trim().toLowerCase();
        const couldStillBeNone =
          normalized === '' ||
          ('none'.startsWith(normalized) && normalized.length <= 'none'.length) ||
          normalized === 'none';
        if (couldStillBeNone && bufferedPrefix.trim().length <= 8) {
          return;
        }

        prefixReleased = true;
        options.onDelta(bufferedPrefix, fullText);
        bufferedPrefix = '';
      },
    });

    if (!prefixReleased && bufferedPrefix && !looksLikeEmptyStageText(fullText)) {
      options.onDelta(bufferedPrefix, fullText);
    }

    return cleanStageText(fullText);
  };

  async function generatePreRouterOpening(
    env: WorkerRunnerEnv,
    userQuery: string,
    historyMessages: HistoryMessage[] = [],
    runtimeOptions?: Pick<WorkerRuntimeOptions, 'onAssistantDelta' | 'onProbeEvent'>
  ): Promise<{ content: string; emittedAt: string | null }> {
    const onAssistantDelta = runtimeOptions?.onAssistantDelta;
    const onProbeEvent = runtimeOptions?.onProbeEvent;
    const emitProbeStage = (stage: string, detail?: Record<string, unknown>) => {
      onProbeEvent?.({
        type: 'probe_stage',
        stage,
        ...(detail ? { detail } : {}),
      });
    };

    let content = '';
    try {
      let openingFirstDeltaEmitted = false;
      emitProbeStage('opening_started', { opening_mode: 'pre_router' });
      const openingText = await streamShortModelText(env, {
        messages: buildOpeningStepPrompt(env, null, 'pre_router', userQuery, [], historyMessages),
        suppressNone: true,
        onDelta(delta) {
          if (!openingFirstDeltaEmitted) {
            openingFirstDeltaEmitted = true;
            emitProbeStage('opening_first_delta', { opening_mode: 'pre_router' });
          }
          content += delta;
          onAssistantDelta?.(delta);
        },
      });
      emitProbeStage('opening_done', {
        opening_mode: 'pre_router',
        emitted_text: !looksLikeEmptyStageText(openingText),
      });

      if (looksLikeEmptyStageText(openingText)) {
        return { content: '', emittedAt: null };
      }

      if (!content.endsWith('\n\n')) {
        content = `${cleanStageText(content)}\n\n`;
        onAssistantDelta?.('\n\n');
      }

      return { content, emittedAt: new Date().toISOString() };
    } catch (error) {
      emitProbeStage('opening_failed', {
        opening_mode: 'pre_router',
        error: error instanceof Error ? error.message : String(error),
      });
      return { content: '', emittedAt: null };
    }
  }

  async function runWorkerWithTools(
    env: WorkerRunnerEnv,
    workerTool: WorkerToolName,
    userQuery: string,
    isStream = false,
    toolProvider?: ToolProvider,
    historyMessages?: HistoryMessage[],
    runtimeOptions?: WorkerRuntimeOptions
  ): Promise<{
    content: string | ReadableStream;
    metadata?: Record<string, unknown>;
    sources?: Array<Record<string, unknown>>;
    leadingContent?: string;
    trailingContent?: string;
  }> {
    const skill = deps.WORKER_SKILLS[workerTool];
    if (!skill) {
      return { content: `暂不支持的工具：${workerTool}` };
    }

    const provider = toolProvider ?? deps.createToolProvider(env);
    const requireRuleDraftTools = workerTool === 'rule_asker';
    const prefetchedSourceData = runtimeOptions?.prefetchedSourceData ?? null;
    const suppressStageText = runtimeOptions?.suppressStageText === true;
    const suppressOpeningText = suppressStageText || runtimeOptions?.suppressOpeningText === true;
    const suppressClosingText = suppressStageText || runtimeOptions?.suppressClosingText === true;
    const onAssistantDelta = runtimeOptions?.onAssistantDelta;
    const onAssistantProgress = runtimeOptions?.onAssistantProgress;
    const onAgentEvent = runtimeOptions?.onAgentEvent;
    const onProbeEvent = runtimeOptions?.onProbeEvent;
    const emitProbeStage = (stage: string, detail?: Record<string, unknown>) => {
      onProbeEvent?.({
        type: 'probe_stage',
        stage,
        ...(detail ? { detail } : {}),
      });
    };
    emitProbeStage('worker_started', { worker_tool: workerTool, is_stream: isStream });
    const structuredPrefetchedMode =
      deps.STRUCTURED_REPORT_WORKER_TOOLS.has(workerTool) && Boolean(prefetchedSourceData);
    const listedTools = structuredPrefetchedMode ? [] : await provider.listTools();
    const toolExposure = buildModelToolExposure(listedTools);
    const openAITools = toolExposure.modelTools.map(deps.toOpenAIToolSchema);
    const enableThinkingForMainAnswer =
      isExpertWorkerTool(workerTool) && isExpertThinkingEnabled(env);
    const availableToolNames = listedTools.map((tool) => tool.name).sort();
    const providerDebugInfo = await provider.getDebugInfo?.();
    const toolProviderMetadata: Record<string, unknown> = {
      tool_provider_mode:
        providerDebugInfo?.provider_mode ??
        ((env as { MCP_SERVER_URL?: string } | null)?.MCP_SERVER_URL ? 'hybrid' : 'local'),
      available_tool_names: availableToolNames,
      mcp_configured:
        providerDebugInfo?.mcp_configured ??
        Boolean((env as { MCP_SERVER_URL?: string } | null)?.MCP_SERVER_URL),
      ...(providerDebugInfo?.base_provider_mode
        ? { tool_provider_base_mode: providerDebugInfo.base_provider_mode }
        : {}),
      ...(providerDebugInfo?.mcp_visible !== undefined
        ? { mcp_visible: providerDebugInfo.mcp_visible }
        : {}),
      ...(providerDebugInfo?.mcp_list_failed !== undefined
        ? { mcp_list_failed: providerDebugInfo.mcp_list_failed }
        : {}),
      ...(providerDebugInfo?.mcp_list_error
        ? { mcp_list_error: providerDebugInfo.mcp_list_error }
        : {}),
      ...(providerDebugInfo?.mcp_tool_names
        ? { mcp_tool_names: [...providerDebugInfo.mcp_tool_names].sort() }
        : {}),
      ...(providerDebugInfo?.allow_list
        ? { tool_provider_allow_list: [...providerDebugInfo.allow_list].sort() }
        : {}),
      ...(toolExposure.aliases.length ? { model_tool_aliases: toolExposure.aliases } : {}),
      ...(providerDebugInfo?.kb_tool_enabled !== undefined
        ? { kb_tool_enabled: providerDebugInfo.kb_tool_enabled }
        : {}),
      ...(providerDebugInfo?.kb_api_configured !== undefined
        ? { kb_api_configured: providerDebugInfo.kb_api_configured }
        : {}),
      ...(providerDebugInfo?.kb_default_id
        ? { kb_default_id: providerDebugInfo.kb_default_id }
        : {}),
      ...(structuredPrefetchedMode ? { prefetched_source_tools_disabled: true } : {}),
    };
    const withToolProviderMetadata = (
      metadata: Record<string, unknown>
    ): Record<string, unknown> => ({
      ...metadata,
      ...(runtimeOptions?.metadata ?? {}),
      ...toolProviderMetadata,
    });
    if (runtimeOptions?.blockedResponse) {
      return {
        content: runtimeOptions.blockedResponse.content,
        metadata: withToolProviderMetadata({
          tool: workerTool,
          blocked_response: true,
          ...(runtimeOptions.blockedResponse.metadata ?? {}),
        }),
      };
    }
    const structuredReportRuntimeConfig =
      deps.getStructuredManagementReportRuntimeConfig(workerTool);
    const availableToolSummary = toolExposure.modelTools
      .map((tool) => {
        const providerName = toolExposure.modelNameToProviderName.get(tool.name) ?? tool.name;
        const aliasNote = providerName !== tool.name ? ` (MCP: ${providerName})` : '';
        return `- ${tool.name}${aliasNote}: ${tool.description}`;
      })
      .join('\n');

    const requireDataQueryBeforeReply =
      deps.STRUCTURED_REPORT_WORKER_TOOLS.has(workerTool) && !prefetchedSourceData;
    const prefetchedSourceGuardrail = structuredPrefetchedMode
      ? '\n\nPREFETCHED REPORT MODE:\n- A complete report_source is already provided in this turn.\n- Return the final structured JSON object directly from report_source.\n- Do not call, simulate, or re-resolve any tools.\n- The final answer must be exactly one JSON object with no markdown and no extra commentary.'
      : '';
    const toolAvailabilityGuardrail = supportsConversationalToolUseGuardrails(workerTool)
      ? [
          '',
          '',
          '关键要求：',
          '- 本轮列出的工具，就是当前唯一可用的工具。',
          '- 如果用户询问当前接入了哪些 MCP 或工具，只能基于下面的可用工具列表回答。',
          '- 不要虚构工具执行、示例入参、示例结果或业务数据。',
          '- 只有真实发起过工具调用，才能说“我查了”或“我调用了”。',
          '- 如果当前轮已提供 report_source 或其他真实数据，直接基于这些数据回答；仅在缺少数据且工具可用时再调用工具。',
          '- 优先使用最具体、最匹配的工具，不要用列表或搜索结果去硬推断统计结论或分类汇总。',
          '- 除非用户明确要求原始数据，否则不要直接输出原始 JSON、原始数组或整段工具返回。',
          '- 先总结工具结果，再用易读的方式呈现关键行、关键数字或结论。',
          '- 当用户请求复合信息时，不要因为其中一部分字段缺失而整体拒答；应先回答工具已返回的字段，再说明缺失字段。',
          '- 缺失字段说明“未返回”或“无法确认”，不要用 [字段名]、示例值或模板占位符补齐。',
          '',
          '查询规划要求：',
          '- 对所有需要业务数据的问题，先在内部拆分为：主体实体、目标字段、限定条件、可用查询键；不要向用户展示这段内部拆分。',
          '- 不要把用户自然语言中的限定条件直接塞进任意同名字段；必须核对当前可用工具 schema 是否支持该字段，以及该字段在历史结果或本轮工具结果中是否真实可用。',
          '- 当用户提供的限定条件是名称、简称、层级组织、车队、线路、别名等，而目标工具更适合使用 ID、编号或标准键过滤时，必须先调用最合适的明细/列表工具解析标准键，再用标准键查询目标实体。',
          '- 多步查询中，前一步工具结果里的 ID、编号、标准名称、所属机构等字段，应作为后续工具调用的过滤条件；不要仅凭自然语言名称做最终判断。',
          '- 已拿到可用 ID/编号/标准键时，不要为同一目标重复调用同一列表工具；也不要把 ID 填入名称字段（如 organId 填 organName、routeId 填 routeName）。',
          '- 多个候选需要补查且互不依赖时，在同一轮同时发起多个工具调用；补查后直接按候选列出结果，只有仍无法区分必要对象时才向用户澄清。',
          '- 如果直接字段为空，不要立即判定无法回答。先检查同一条可信记录中是否存在可推导字段；若可推导，给出计算结果并说明计算依据。若不可推导，再说明缺少哪些字段。',
          '- 如果查询结果存在多个候选，先用用户已给限定条件自动收窄；只有仍无法唯一确定时，才向用户澄清。',
          '- 最终回答必须区分：工具直接返回值、由工具字段计算得到的值、无法确认的值。',
          '',
          '多来源事实优先级：',
          '- 当本轮同时存在 MCP/业务数据工具结果、report_source、历史消息、知识库片段或规则材料时，事实优先级为：本轮 MCP/业务数据工具结果 > 本轮 report_source > 历史中已明确的工具结果 > 知识库/规则材料 > 常识。',
          '- 个体画像、风险评分、评价类型、日期、建议数量、统计数值、列表明细等业务事实，只能来自 MCP/业务数据工具或 report_source；知识库/规则材料不得覆盖、改写或补全这些字段。',
          '- 当用户询问“最新/当前/本次返回”的画像评分、风险指标或明细时，只能使用本轮 MCP/业务数据工具结果或本轮 report_source 中实际存在的字段；若某指标未出现在本轮返回的 quotaScoreSubList、quota_summary、high_risk_indicators 或等价明细中，不得从历史消息、历史报告、样例数据、知识库或模型记忆中补具体分值，只能说明“当前返回未包含该指标”。',
          '- 知识库/规则材料只能用于解释制度、流程、条款含义或管理要求；不得作为具体车辆、驾驶员、线路、站场、单位的评分、状态、数量或画像事实来源。',
          '- 如果 MCP/业务数据工具结果与知识库/规则材料看起来冲突，必须以 MCP/业务数据工具结果回答业务事实；知识库内容只可作为制度解释，并说明其与具体数据不是同一类来源。',
          '- 如果 MCP/业务数据工具未返回用户所问的具体字段，必须说“工具未返回/无法确认”，不得用知识库、历史回答、字段名、模板值或常识推断。',
          '',
          '多轮上下文使用要求：',
          '- 历史消息只能用于补充当前轮省略的对象、时间、范围或已确认数据，不得改写当前轮已经明确表达的任务类型。',
          '- 当当前轮已经包含完整的查询对象、动作和期望输出时，应把它作为当前任务独立理解；不要把上一轮的任务类型、数据来源、输出形态或处理阶段合并进来。',
          '- 只有当前轮明确表示延续上一轮，或当前轮缺少完成任务所必需的信息时，才使用历史消息补全；补全后仍必须服从当前轮的表达边界。',
          '- 如果历史结果与当前任务属于不同查询口径，历史结果只能作为背景说明，不能作为当前任务无数据、缺参或需要改问的依据。',
          '',
          '实体名称与工具参数要求：',
          '- 工具调用参数中的实体名称必须严格来自用户原文、历史中已确认的实体名称，或工具结果返回的标准名称。',
          '- 不得自行把简称、数字、序号、车队名、线路名、站场名、车牌号、驾驶员姓名改写成看起来更正式的名称。',
          '- 例如：“四分公司”不得改写为“第四分公司”；“一车队”不得改写为“第一车队”；“二巴公司”不得改写为“第二巴士公司”。',
          '- 如果怀疑用户名称不是系统标准名称，应先用用户原文查询；查询失败且存在候选时，再请用户确认候选名称。不要直接用未确认的候选名继续查。',
          '- 多轮对话中，当前轮省略实体时，只能继承历史中用户明确说过或工具确认过的实体；不得继承 assistant 自己猜测出来的实体名称。',
          '',
          '工具证据要求：',
          '- 只有本轮真实调用过的工具，才能说“已查询/已调用/返回结果”。',
          '- 没有调用过的工具，不得描述其返回值、错误码、空结果或失败原因。',
          '- 如果本轮没有工具调用，只能基于上一轮已明确的工具结果回答，并说明没有新增查询。',
          '- 工具返回记录的所属单位、线路、车辆、驾驶员与用户目标不一致时，不得当作目标对象的数据；只能说明“返回记录与目标不匹配，无法作为该对象结论”。',
          '',
          '基础数据与统计口径要求：',
          '- 用户说“基础数据、基础信息、运营基础数据、档案、台账”时，优先理解为对象的基础档案、组织归属、车辆、驾驶员、线路、站场等基础实体信息；不要默认理解为风险画像或管理效果。',
          '- “运营基础数据”“基础运营数据”里的“运营”只是公交运营业务范围限定，中心词仍是“基础数据”；不要自动扩展为日均发班次数、日均客运量、日运营里程、平均速度、能耗、风险评分等未被用户点名的指标。',
          '- 若用户只说“最近的运营基础数据”，应先查询可用的基础实体/档案字段；对于当前工具未覆盖的运营 KPI，只能说明未返回或无法确认，不能把它们加入查询计划后再据此判定查不到。',
          '- 用户问“数量、总数、人数、车辆数、线路数、规模、多少”时，不能用当前页 records 数组长度直接当总数。',
          '- pageSize=1 只能说明“当前页/样本返回 1 条”，不能说“总数为 1”或“仅有 1 条”。',
          '- 只有工具返回 total、count、total_record_count 等总数字段，或专门统计接口返回结果时，才能给出总数。',
          '- 如果可用工具只能返回明细页，必须说明“当前工具未返回可靠总数字段”，并避免输出确定总数。',
          '',
          '当前可用工具：',
          availableToolSummary || '- none',
        ].join('\n')
      : '';
    const fieldAlignmentGuardrail = supportsConversationalToolUseGuardrails(workerTool)
      ? [
          '',
          '',
          '字段对齐与补查流程：',
          '- 先判断用户要的是展示字段还是内部标识；“哪个/哪条/所属/名称”通常要业务名称或用户可识别标识，只有明确问 ID/编号/编码时才输出内部标识。',
          '- 工具结果里的 ID、编号、标准名称、所属机构等字段可作为下一步查询键；当前可见工具能继续定位目标字段时，优先补查后再回答。',
          '- 补查过程中可简短说明“正在用已返回的 ID/编号继续核对名称”，这属于继续完成同一问题，不是向用户索要补充信息。',
          '- 补查成功后按用户问题直接回答；仍缺精确字段时，回答已确认字段并说明未直接返回的字段，避免把相近字段当成精确字段。',
          '- 多候选命中时，若每个候选都有可展示的员工编号/车牌/线路/机构等区分字段，应直接逐项列出；不要为了唯一化而丢弃其他候选或要求用户先补充。',
          '- 常见例子：车辆结果只有 routeId 而用户问所属线路，应继续查 routeName；用户问车辆时优先答车牌号/自编号而不是 busId。',
        ].join('\n')
      : '';
    // TODO(ai-security-mcp-score-hotfix): Remove this guardrail after MCP descriptions
    // clearly distinguish source score from final risk score/originalValue.
    const riskScoreSemanticsGuardrail = supportsRiskScoreSemanticsGuardrail(workerTool)
      ? [
          '',
          '',
          '风险指标语义要求：',
          '- 凡是风险值、风险得分、riskValue、final_risk_score 或画像指标 originalValue 字段，均按“数值越高代表风险越高、越危险”解释。',
          '- 画像指标中的上游 score 字段不是最终分数，仅作为源指标分/计算中间值；生成报告和解释指标贡献时优先使用 final_risk_score/originalValue。',
          '- 建议明细类 score 字段没有 originalValue 时，可按风险建议分/风险优先级分解释，数值越高表示越需要优先关注。',
          '- 风险类环比、同比及同单位/同机构/同线路对比中，正数表示风险上升或高于基准，负数表示风险下降或低于基准。',
        ].join('\n')
      : '';
    const finalSkill = requireRuleDraftTools
      ? `${skill}\n\n关键要求：每一轮回复前，你都必须先调用 get_rule_draft 和 update_rule_draft；即使没有改动，也要用 noop: true 完成 update_rule_draft。没有先调用这两个工具时，不要直接回复用户。`
      : skill;

    const conversationalVisibleOutputGuardrail =
      buildConversationalVisibleOutputGuardrail(workerTool);
    const clarificationGuardrail =
      '\n\n澄清工具要求：\n- 如果已拿到可继续查询的 ID、编号或标准名称，优先继续查询；只有缺少用户才能判断的信息时再澄清。\n- 如果必要信息缺失或存在歧义，先在本轮 assistant 消息里写出要给用户看的澄清问题。\n- 然后再调用 request_further_info，仅用于持久化可恢复的待补充状态。\n- 不要在 request_further_info 的参数里重复那段给用户看的澄清文本。\n- resume_tool 必须是下一轮应继续执行的 worker 工具名。\n- 对结构化参数，使用 resume_mode=fill_args，并列出 missing_fields。\n- 对对话型工具，可使用 resume_mode=append_user_reply，并携带当前任务已知的 known_args。';
    const runtimeSystemPrefix = runtimeOptions?.systemPromptPrefix?.trim();
    const serverTimeGuide = buildServerTimeSystemPrompt();
    const finalSystemSkill = `${serverTimeGuide}\n\n${runtimeSystemPrefix ? `${runtimeSystemPrefix}\n\n` : ''}${finalSkill}${prefetchedSourceGuardrail}${conversationalVisibleOutputGuardrail}${toolAvailabilityGuardrail}${fieldAlignmentGuardrail}${riskScoreSemanticsGuardrail}${clarificationGuardrail}`;
    let messages: ChatCompletionMessage[] = [{ role: 'system', content: finalSystemSkill }];

    if (historyMessages?.length) {
      messages = messages.concat(
        buildContextFromHistory(
          historyMessages,
          30,
          buildContextHistoryOptions(env, 'worker_initial')
        )
      );
    }

    messages.push({ role: 'user', content: userQuery });

    let didGetRuleDraft = false;
    let didUpdateRuleDraft = false;
    const requestedStructuredEntityToken =
      structuredReportRuntimeConfig?.extractRequestedEntityToken?.(userQuery) ?? null;
    let dataToolCallCount = 0;
    let dataToolSuccessCount = 0;
    let dataToolHitCount = 0;
    let latestExternalDataPayload: Record<string, unknown> | null = prefetchedSourceData;
    let missingDataQueryRetries = 0;
    let consecutiveReadNoHitCount = 0;
    let collectedSources: MessageSource[] = extractMessageSources(prefetchedSourceData);

    let iteration = 0;
    let consecutiveNoToolCalls = 0;
    let emptyWorkerTurnCount = 0;
    let hasRestarted = false;
    const maxConsecutiveNoToolCalls = 2;
    const maxMissingDataQueryRetries = structuredReportRuntimeConfig?.missingDataRetryLimit ?? 2;
    const toolUsages: ToolUsage[] = [];
    let leadingContent = '';
    let trailingContent = '';
    let progressEmitted = false;
    let progressCode: AssistantProgressCode | null = null;
    let openingEmittedAt: string | null = null;
    let progressEmittedAt: string | null = null;
    let firstMeaningfulDataHitAt: string | null =
      prefetchedSourceData && hasMeaningfulProgressData(prefetchedSourceData)
        ? new Date().toISOString()
        : null;
    const buildToolUsageMetadata = (): Record<string, unknown> => ({
      tools: toolUsages,
      worker_tools: toolUsages,
      data_tool_calls: dataToolCallCount,
      data_tool_success: dataToolSuccessCount,
      data_tool_hits: dataToolHitCount,
      ...(prefetchedSourceData ? { prefetched_source_data: true } : {}),
      ...(openingEmittedAt ? { opening_emitted_at: openingEmittedAt } : {}),
      ...(firstMeaningfulDataHitAt
        ? { first_meaningful_data_hit_at: firstMeaningfulDataHitAt }
        : {}),
      ...(progressEmittedAt ? { progress_emitted_at: progressEmittedAt } : {}),
      ...(progressCode ? { progress_code: progressCode } : {}),
    });
    const resolveProviderToolName = (modelToolName: string): string =>
      toolExposure.modelNameToProviderName.get(modelToolName) ?? modelToolName;
    const toProviderToolCall = (toolCall: ToolCall): ToolCall => {
      const providerToolName = resolveProviderToolName(String(toolCall.tool));
      if (providerToolName === toolCall.tool) {
        return toolCall;
      }
      return { ...toolCall, tool: providerToolName as ToolCall['tool'] };
    };
    const emitAssistantProgress = async (code: AssistantProgressCode): Promise<void> => {
      if (!isStream || !onAssistantProgress || progressEmitted) {
        return;
      }

      let progressText = '';
      let progressFirstDeltaEmitted = false;
      try {
        emitProbeStage('progress_started', { code });
        progressText = await streamShortModelText(env, {
          messages: buildProgressStepPrompt(workerTool, code, userQuery),
          onDelta(_delta, fullText) {
            if (!progressFirstDeltaEmitted) {
              progressFirstDeltaEmitted = true;
              emitProbeStage('progress_first_delta', { code });
            }
            const cleaned = cleanStageText(fullText);
            if (cleaned) {
              onAssistantProgress({ code, text: cleaned });
            }
          },
        });
      } catch {
        // Fall back to a conservative factual status if the helper generation fails.
      }

      if (looksLikeEmptyStageText(progressText)) {
        progressText =
          code === 'prefetched_source_data_ready'
            ? '已获取到相关基础数据，正在继续整理。'
            : '已获取到相关有效数据，正在继续核对。';
      }

      progressEmitted = true;
      progressCode = code;
      progressEmittedAt = new Date().toISOString();
      onAssistantProgress({ code, text: progressText });
      emitProbeStage('progress_done', {
        code,
        emitted_text: !looksLikeEmptyStageText(progressText),
      });
    };
    const callToolWithStreamEvents = async (toolCall: ToolCall): Promise<ToolResult> => {
      onAgentEvent?.({
        type: 'tool_execution_started',
        id: toolCall.id,
        tool: toolCall.tool,
        args: toolCall.args,
      });
      try {
        const result = (await provider.callTool(toolCall.tool, toolCall.args)) as ToolResult;
        onAgentEvent?.({
          type: 'tool_execution_completed',
          id: toolCall.id,
          tool: toolCall.tool,
          success: result.success === true,
          resultSummary: summarizeToolResultForStream(result),
        });
        return result;
      } catch (error) {
        onAgentEvent?.({
          type: 'tool_execution_failed',
          id: toolCall.id,
          tool: toolCall.tool,
          error: error instanceof Error ? error.message : String(error),
        });
        throw error;
      }
    };

    const openingMode = suppressOpeningText ? null : resolveOpeningMode(workerTool);
    if (openingMode) {
      try {
        let openingFirstDeltaEmitted = false;
        emitProbeStage('opening_started', { opening_mode: openingMode });
        const openingText = await streamShortModelText(env, {
          messages: buildOpeningStepPrompt(env, workerTool, openingMode, userQuery, listedTools),
          suppressNone: true,
          onDelta(delta) {
            if (!openingFirstDeltaEmitted) {
              openingFirstDeltaEmitted = true;
              emitProbeStage('opening_first_delta', { opening_mode: openingMode });
            }
            leadingContent += delta;
            onAssistantDelta?.(delta);
          },
        });
        emitProbeStage('opening_done', {
          opening_mode: openingMode,
          emitted_text: !looksLikeEmptyStageText(openingText),
        });
        if (!looksLikeEmptyStageText(openingText)) {
          if (!leadingContent.endsWith('\n\n')) {
            leadingContent = `${cleanStageText(leadingContent)}\n\n`;
            onAssistantDelta?.('\n\n');
          }
          openingEmittedAt = new Date().toISOString();
          messages.push({
            role: 'assistant',
            content:
              '本轮用户已经看到一条简短开场说明。最终回答中不要重复任何前言、寒暄或过程描述。',
          });
        }
      } catch {
        // Ignore opening generation failures and continue with the main worker flow.
      }
    }

    if (prefetchedSourceData && hasMeaningfulProgressData(prefetchedSourceData)) {
      await emitAssistantProgress('prefetched_source_data_ready');
    }

    while (iteration < deps.MAX_TOOL_ITERATIONS) {
      iteration += 1;

      let streamedVisibleContent = '';
      let mainFirstDeltaEmitted = false;
      emitProbeStage('main_iteration_started', { iteration });
      const response = structuredPrefetchedMode
        ? {
            content: await deps.callOpenAIStreamText(env, {
              model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
              temperature: 0.2,
              messages,
              enableThinking: enableThinkingForMainAnswer,
            }),
            toolCalls: undefined,
          }
        : isStream && isConversationalWorkerTool(workerTool)
          ? await deps.callOpenAIWithToolsStream(env, {
              model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
              temperature: 0.2,
              messages,
              tools: openAITools,
              enableThinking: enableThinkingForMainAnswer,
              onTextDelta(delta) {
                if (!mainFirstDeltaEmitted) {
                  mainFirstDeltaEmitted = true;
                  emitProbeStage('main_first_delta', { iteration });
                }
                streamedVisibleContent += delta;
              },
              onReasoningDelta(delta) {
                onAgentEvent?.({
                  type: 'reasoning_delta',
                  field: delta.field,
                  delta: delta.delta,
                });
              },
              onToolCallDelta(delta) {
                onAgentEvent?.({
                  type: 'tool_call_delta',
                  index: delta.index,
                  id: delta.id,
                  tool: delta.tool ? resolveProviderToolName(String(delta.tool)) : delta.tool,
                  argumentsDelta: delta.argumentsDelta,
                });
              },
              onToolCallReady(toolCall) {
                const providerToolName = resolveProviderToolName(String(toolCall.tool));
                emitProbeStage('main_tool_call_ready', {
                  iteration,
                  tool: providerToolName,
                });
                onAgentEvent?.({
                  type: 'tool_call_ready',
                  id: toolCall.id,
                  tool: providerToolName,
                  args: toolCall.args,
                });
              },
            })
          : await deps.callOpenAIWithTools(env, {
              model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
              temperature: 0.2,
              messages,
              tools: openAITools,
              enableThinking: enableThinkingForMainAnswer,
            });
      emitProbeStage('main_iteration_done', {
        iteration,
        has_content: Boolean(response.content),
        tool_call_count: response.toolCalls?.length ?? 0,
      });

      if (response.content && !response.toolCalls?.length) {
        if (
          isConversationalWorkerTool(workerTool) &&
          looksLikeInternalInstructionLeak(response.content)
        ) {
          return {
            content: INTERNAL_LEAK_BLOCKED_FALLBACK,
            metadata: withToolProviderMetadata({
              tool: workerTool,
              iterations: iteration,
              internal_instruction_leak_blocked: true,
              ...buildToolUsageMetadata(),
            }),
            ...(leadingContent ? { leadingContent } : {}),
            ...(collectedSources.length ? { sources: collectedSources } : {}),
          };
        }
        if (requireDataQueryBeforeReply) {
          const totalReadCallCount = dataToolCallCount;
          const totalReadSuccessCount = dataToolSuccessCount;
          const totalDataHitCount = dataToolHitCount;
          const missingReadCall = totalReadCallCount === 0;
          const noSuccessfulRead = totalReadCallCount > 0 && totalReadSuccessCount === 0;
          const noDataHit = totalReadSuccessCount > 0 && totalDataHitCount === 0;
          if (missingReadCall || noSuccessfulRead || noDataHit) {
            const mode: 'missing_read_call' | 'read_failed' | 'no_data_hit' = missingReadCall
              ? 'missing_read_call'
              : noSuccessfulRead
                ? 'read_failed'
                : 'no_data_hit';
            missingDataQueryRetries += 1;
            if (missingDataQueryRetries > maxMissingDataQueryRetries) {
              return {
                content: deps.buildStructuredReportNoDataError(workerTool),
                metadata: withToolProviderMetadata({
                  tool: workerTool,
                  iterations: iteration,
                  error: mode,
                  ...buildToolUsageMetadata(),
                }),
                ...(leadingContent ? { leadingContent } : {}),
              };
            }
            messages.push({
              role: 'user',
              content: deps.buildStructuredReportMissingDataPrompt(workerTool, mode),
            });
            continue;
          }
        }

        let finalContent = response.content;
        if (structuredReportRuntimeConfig) {
          emitProbeStage('report_validation_started', {
            raw_content_length: finalContent?.length ?? 0,
          });
          emitProbeStage('report_raw_llm_output', {
            content: finalContent?.substring(0, 5000) ?? '',
          });
          const parsedReport = deps.safeJsonParse(finalContent);
          if (!deps.isRecord(parsedReport)) {
            if (latestExternalDataPayload) {
              const sourceOnlyReport = structuredReportRuntimeConfig.normalizeReport(
                {},
                latestExternalDataPayload
              );
              if (
                structuredReportRuntimeConfig.hasCompleteReport(sourceOnlyReport) &&
                structuredReportRuntimeConfig.hasTemplateMarkerNotation(sourceOnlyReport)
              ) {
                finalContent = JSON.stringify(sourceOnlyReport, null, 2);
              } else {
                return {
                  content: deps.buildStructuredReportFormatMismatchError(workerTool),
                  metadata: withToolProviderMetadata({
                    tool: workerTool,
                    iterations: iteration,
                    error: structuredReportRuntimeConfig.formatMismatchError,
                    structured_report_source_fallback_failed: true,
                    ...buildStructuredReportParseFailureMetadata(finalContent),
                    ...buildToolUsageMetadata(),
                  }),
                  ...(leadingContent ? { leadingContent } : {}),
                };
              }
            } else {
              return {
                content: deps.buildStructuredReportFormatMismatchError(workerTool),
                metadata: withToolProviderMetadata({
                  tool: workerTool,
                  iterations: iteration,
                  error: structuredReportRuntimeConfig.formatMismatchError,
                  ...buildStructuredReportParseFailureMetadata(finalContent),
                  ...buildToolUsageMetadata(),
                }),
                ...(leadingContent ? { leadingContent } : {}),
              };
            }
          } else {
            let normalizedReport = structuredReportRuntimeConfig.normalizeReport(
              parsedReport,
              latestExternalDataPayload
            );
            if (
              (!structuredReportRuntimeConfig.hasCompleteReport(normalizedReport) ||
                !structuredReportRuntimeConfig.hasTemplateMarkerNotation(normalizedReport)) &&
              latestExternalDataPayload
            ) {
              const sourceOnlyReport = structuredReportRuntimeConfig.normalizeReport(
                {},
                latestExternalDataPayload
              );
              if (
                structuredReportRuntimeConfig.hasCompleteReport(sourceOnlyReport) &&
                structuredReportRuntimeConfig.hasTemplateMarkerNotation(sourceOnlyReport)
              ) {
                normalizedReport = sourceOnlyReport;
              }
            }
            if (
              !structuredReportRuntimeConfig.hasCompleteReport(normalizedReport) ||
              !structuredReportRuntimeConfig.hasTemplateMarkerNotation(normalizedReport)
            ) {
              return {
                content: deps.buildStructuredReportFormatMismatchError(workerTool),
                metadata: withToolProviderMetadata({
                  tool: workerTool,
                  iterations: iteration,
                  error: structuredReportRuntimeConfig.formatMismatchError,
                  ...buildStructuredReportParseFailureMetadata(finalContent),
                  ...buildToolUsageMetadata(),
                }),
                ...(leadingContent ? { leadingContent } : {}),
              };
            }
            finalContent = JSON.stringify(normalizedReport, null, 2);
          }
        }

        if (requireRuleDraftTools && (!didGetRuleDraft || !didUpdateRuleDraft)) {
          consecutiveNoToolCalls += 1;

          if (consecutiveNoToolCalls >= maxConsecutiveNoToolCalls && !hasRestarted) {
            hasRestarted = true;
            consecutiveNoToolCalls = 0;

            const originalUserQuery = messages[messages.length - 1]?.content || userQuery;
            messages = [
              { role: 'system', content: finalSystemSkill },
              ...((historyMessages?.length
                ? buildContextFromHistory(
                    historyMessages,
                    30,
                    buildContextHistoryOptions(env, 'worker_restart')
                  )
                : []) as ChatCompletionMessage[]),
              { role: 'user', content: originalUserQuery },
              {
                role: 'user',
                content:
                  '关键要求：在回复用户之前，你必须先调用 get_rule_draft，再调用 update_rule_draft；即使没有改动，也要用 noop: true 完成 update_rule_draft。没有先调用这两个工具时，不要直接回复用户。',
              },
            ];
            continue;
          }

          if (consecutiveNoToolCalls > maxConsecutiveNoToolCalls) {
            return {
              content:
                '规则配置流程异常：必须调用 get_rule_draft 和 update_rule_draft 工具。请重试。',
              metadata: withToolProviderMetadata({
                tool: workerTool,
                iterations: iteration,
                error: 'missing_required_tools',
                ...buildToolUsageMetadata(),
              }),
              ...(leadingContent ? { leadingContent } : {}),
            };
          }

          messages.push({
            role: 'user',
            content:
              'You MUST call get_rule_draft and update_rule_draft before replying. If nothing changes, call update_rule_draft with noop: true.',
          });
          continue;
        }

        consecutiveNoToolCalls = 0;
        if (
          isStream &&
          !requireDataQueryBeforeReply &&
          !supportsClosingStep(workerTool) &&
          workerTool !== 'consult_omni' &&
          workerTool !== 'consult_vehicle_expert' &&
          workerTool !== 'consult_driver_expert' &&
          workerTool !== 'consult_unit_expert' &&
          workerTool !== 'consult_route_expert' &&
          workerTool !== 'consult_station_expert' &&
          workerTool !== 'consult_incident_expert'
        ) {
          const stream = await deps.callOpenAIStreamWithTools(env, {
            model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
            temperature: 0.2,
            messages,
            tools: openAITools,
            enableThinking: enableThinkingForMainAnswer,
          });
          return {
            content: stream,
            metadata: withToolProviderMetadata({
              tool: workerTool,
              iterations: iteration,
              stream: true,
              ...buildToolUsageMetadata(),
            }),
            ...(leadingContent ? { leadingContent } : {}),
            ...(collectedSources.length ? { sources: collectedSources } : {}),
          };
        }

        const parsed = deps.safeJsonParse(finalContent);
        const content = normalizeWorkerFinalContent(workerTool, finalContent, parsed);
        if (
          supportsClosingStep(workerTool) &&
          !suppressClosingText &&
          !(deps.isRecord(parsed) && typeof parsed.error === 'string')
        ) {
          try {
            const closingRaw = await deps.callOpenAI(env, {
              model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
              temperature: 0.2,
              messages: buildClosingStepPrompt(workerTool, userQuery, content),
              enableThinking: false,
            });
            const closingText = cleanStageText(closingRaw);
            if (!looksLikeEmptyStageText(closingText)) {
              trailingContent = `\n\n${closingText}`;
            }
          } catch {
            // Ignore closing generation failures and keep the main answer.
          }
        }
        return {
          content,
          metadata: withToolProviderMetadata({
            tool: workerTool,
            iterations: iteration,
            ...buildToolUsageMetadata(),
          }),
          ...(leadingContent ? { leadingContent } : {}),
          ...(trailingContent ? { trailingContent } : {}),
          ...(collectedSources.length ? { sources: collectedSources } : {}),
        };
      }

      if (!response.toolCalls?.length) {
        if (!response.content) {
          emptyWorkerTurnCount += 1;
          if (isConversationalWorkerTool(workerTool) && openAITools.length) {
            messages.push({
              role: 'user',
              content:
                '本轮没有产生回答或工具调用。当前问题需要业务数据时，请从当前可用工具中选择最匹配的工具发起查询；只有问题不需要业务数据时才直接回答。',
            });
          }
        }
        continue;
      }

      consecutiveNoToolCalls = 0;
      const providerToolCalls = response.toolCalls.map(toProviderToolCall);
      messages.push({
        role: 'assistant',
        content: isConversationalWorkerTool(workerTool) ? '' : response.content || '',
        tool_calls: response.toolCalls,
      });

      for (const toolCall of providerToolCalls) {
        toolUsages.push({
          id: toolCall.id,
          name: toolCall.tool,
          args: toolCall.args,
        });

        if (toolCall.tool === 'rule_exit') {
          const result = await callToolWithStreamEvents(toolCall);
          const data = (result as ToolResult).data as Record<string, unknown> | undefined;
          const reason = typeof data?.reason === 'string' ? data.reason : undefined;
          const confidence = typeof data?.confidence === 'number' ? data.confidence : undefined;
          return {
            content: '',
            metadata: withToolProviderMetadata({
              tool: workerTool,
              iterations: iteration,
              rule_exit: true,
              reason,
              confidence,
              ...buildToolUsageMetadata(),
            }),
            ...(leadingContent ? { leadingContent } : {}),
            ...(collectedSources.length ? { sources: collectedSources } : {}),
          };
        }

        if (toolCall.tool === 'request_further_info') {
          const result = await callToolWithStreamEvents(toolCall);
          const data = (result as ToolResult).data as Record<string, unknown> | undefined;
          const pendingFurtherInfo =
            data && typeof data === 'object' && !Array.isArray(data)
              ? (data.pending_further_info as Record<string, unknown> | undefined)
              : undefined;
          if (!pendingFurtherInfo) {
            return {
              content: resolveFurtherInfoDisplayMessage(response.content, toolCall.args),
              metadata: withToolProviderMetadata({
                tool: workerTool,
                iterations: iteration,
                error: 'invalid_request_further_info_payload',
                ...buildToolUsageMetadata(),
              }),
              ...(leadingContent ? { leadingContent } : {}),
            };
          }
          return {
            content: resolveFurtherInfoDisplayMessage(response.content, toolCall.args),
            metadata: withToolProviderMetadata({
              tool: workerTool,
              iterations: iteration,
              pending_further_info: pendingFurtherInfo,
              ...buildToolUsageMetadata(),
            }),
            ...(leadingContent ? { leadingContent } : {}),
            ...(collectedSources.length ? { sources: collectedSources } : {}),
          };
        }

        const toolResult = await callToolWithStreamEvents(toolCall);
        const toolSucceeded = toolResult.success === true;
        const isExternalDataTool = !isInternalNonDataToolName(toolCall.tool);
        collectedSources = mergeMessageSources(collectedSources, [
          ...(isExternalDataTool && toolSucceeded
            ? [buildMcpDataSource(toolCall.tool, toolCall.args)]
            : []),
          ...extractMessageSources(toolResult.data),
        ]);
        const externalMeaningfulDataHit =
          isExternalDataTool && toolSucceeded && hasMeaningfulProgressData(toolResult.data);
        if (externalMeaningfulDataHit && !firstMeaningfulDataHitAt) {
          firstMeaningfulDataHitAt = new Date().toISOString();
        }

        if (structuredReportRuntimeConfig && isExternalDataTool) {
          dataToolCallCount += 1;
          if (toolSucceeded) {
            dataToolSuccessCount += 1;
          }

          const requestedPayloadMatchesEntity =
            deps.isRecord(toolResult.data) &&
            structuredReportRuntimeConfig.doesGetPayloadMatchRequestedEntity
              ? structuredReportRuntimeConfig.doesGetPayloadMatchRequestedEntity(
                  requestedStructuredEntityToken,
                  toolResult.data
                )
              : true;
          const readHit =
            toolSucceeded &&
            hasMeaningfulToolData(toolResult.data) &&
            requestedPayloadMatchesEntity;

          if (readHit) {
            dataToolHitCount += 1;
            consecutiveReadNoHitCount = 0;
            if (deps.isRecord(toolResult.data)) {
              latestExternalDataPayload = toolResult.data;
            }
          } else {
            consecutiveReadNoHitCount += 1;
          }

          if (
            structuredReportRuntimeConfig.maxDataToolCallsWithoutHit != null &&
            dataToolCallCount >= structuredReportRuntimeConfig.maxDataToolCallsWithoutHit &&
            dataToolHitCount === 0
          ) {
            return {
              content: deps.buildStructuredReportNoDataError(workerTool),
              metadata: withToolProviderMetadata({
                tool: workerTool,
                iterations: iteration,
                error: 'repeated_data_tool_no_hit',
                ...buildToolUsageMetadata(),
              }),
              ...(leadingContent ? { leadingContent } : {}),
            };
          }
        }

        if (externalMeaningfulDataHit) {
          await emitAssistantProgress('first_meaningful_external_data_hit');
        }

        if (toolCall.tool === 'get_rule_draft' && toolSucceeded) {
          didGetRuleDraft = true;
        }
        if (toolCall.tool === 'update_rule_draft' && toolSucceeded) {
          didUpdateRuleDraft = true;
        }

        messages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          name: toolCall.tool,
          content: buildToolMessageContent(toolCall.tool, toolResult),
        });
      }
    }

    if (structuredReportRuntimeConfig && dataToolHitCount === 0 && dataToolCallCount > 0) {
      return {
        content: deps.buildStructuredReportNoDataError(workerTool),
        metadata: withToolProviderMetadata({
          tool: workerTool,
          iterations: iteration,
          error: 'repeated_data_tool_no_hit',
          ...buildToolUsageMetadata(),
        }),
        ...(leadingContent ? { leadingContent } : {}),
        ...(collectedSources.length ? { sources: collectedSources } : {}),
      };
    }

    if (isConversationalWorkerTool(workerTool)) {
      if (toolUsages.length === 0) {
        return {
          content: '当前未能完成真实数据查询，无法基于系统数据回答。请重试。',
          metadata: withToolProviderMetadata({
            tool: workerTool,
            iterations: iteration,
            error: 'missing_worker_tool_call',
            empty_worker_turns: emptyWorkerTurnCount,
            ...buildToolUsageMetadata(),
          }),
          ...(leadingContent ? { leadingContent } : {}),
          ...(collectedSources.length ? { sources: collectedSources } : {}),
        };
      }
      try {
        emitProbeStage('max_iterations_finalize_started', {
          worker_tool: workerTool,
          iterations: iteration,
          tool_call_count: toolUsages.length,
        });
        const finalizedContent = await deps.callOpenAIStreamText(env, {
          model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
          temperature: 0.2,
          enableThinking: enableThinkingForMainAnswer,
          messages: [
            ...messages,
            {
              role: 'user',
              content:
                '本轮工具查询轮次已经达到上限。不要再调用任何工具；请只基于当前已经取得的工具结果和对话上下文，给用户一个简洁、可核对的最终回答。如果已有结果不足以确认结论，请明确说明缺少哪些数据，而不是继续查询。',
            },
          ],
        });
        emitProbeStage('max_iterations_finalize_done', {
          emitted_text: Boolean(finalizedContent.trim()),
        });
        if (finalizedContent.trim()) {
          return {
            content: finalizedContent,
            metadata: withToolProviderMetadata({
              tool: workerTool,
              iterations: iteration,
              max_iterations_finalized: true,
              ...buildToolUsageMetadata(),
            }),
            ...(leadingContent ? { leadingContent } : {}),
            ...(collectedSources.length ? { sources: collectedSources } : {}),
          };
        }
      } catch {
        // Fall through to the explicit max-iteration error if finalization fails.
      }
    }

    return {
      content: '工具调用次数超过限制，请简化请求。',
      metadata: withToolProviderMetadata({
        tool: workerTool,
        iterations: iteration,
        error: 'max_iterations',
        ...buildToolUsageMetadata(),
      }),
      ...(leadingContent ? { leadingContent } : {}),
      ...(collectedSources.length ? { sources: collectedSources } : {}),
    };
  }

  return { runWorkerWithTools, generatePreRouterOpening };
}

export function buildWorkerPrompt(toolCall: WorkerToolCall): string {
  if (toolCall.tool === 'generate_driver_report') {
    const driverName = toolCall.args.driver_name ?? '';
    const dataSourceConfig = getStructuredReportDataSourceConfig('generate_driver_report');
    return (
      dataSourceConfig?.buildUnresolvedPrompt?.(String(driverName)) ??
      `请生成驾驶员「${driverName}」的安全报告。`
    );
  }

  if (toolCall.tool === 'generate_vehicle_report') {
    const vehicleId = toolCall.args.numberPlate ?? '';
    const dataSourceConfig = getStructuredReportDataSourceConfig('generate_vehicle_report');
    return dataSourceConfig?.buildUnresolvedPrompt?.(String(vehicleId)) ?? String(vehicleId);
  }

  if (toolCall.tool === 'generate_unit_report') {
    const organName = toolCall.args.organ_name ?? '';
    const partition =
      String(toolCall.args.ppartition ?? toolCall.args.partition ?? '').trim() || null;
    const dataSourceConfig = getStructuredReportDataSourceConfig('generate_unit_report');
    return (
      dataSourceConfig?.buildUnresolvedPrompt?.(String(organName), partition) ??
      `请生成单位「${organName}」的安全风险分析总结报告（管理人员版）。`
    );
  }

  if (toolCall.tool === 'generate_route_report') {
    const routeName = toolCall.args.route_name ?? '';
    const partition =
      String(toolCall.args.ppartition ?? toolCall.args.partition ?? '').trim() || null;
    const dataSourceConfig = getStructuredReportDataSourceConfig('generate_route_report');
    return (
      dataSourceConfig?.buildUnresolvedPrompt?.(String(routeName), partition) ??
      `请生成线路「${routeName}」的安全风险分析总结报告（管理人员版）。`
    );
  }

  if (toolCall.tool === 'generate_station_report') {
    const stationName =
      toolCall.args.station_name ?? toolCall.args.stationName ?? toolCall.args.busStationName ?? '';
    const partition =
      String(toolCall.args.ppartition ?? toolCall.args.partition ?? '').trim() || null;
    const dataSourceConfig = getStructuredReportDataSourceConfig('generate_station_report');
    return (
      dataSourceConfig?.buildUnresolvedPrompt?.(String(stationName), partition) ??
      `请生成站场“${stationName}”的安全风险分析总结报告（管理人员版）。`
    );
  }

  if (toolCall.tool === 'generate_accident_investigation_report') {
    const driverName = toolCall.args.driver_name ?? '';
    const accidentDate = toolCall.args.accident_date ?? '';
    const dataSourceConfig = getStructuredReportDataSourceConfig(
      'generate_accident_investigation_report'
    );
    return (
      dataSourceConfig?.buildUnresolvedPrompt?.(String(driverName), String(accidentDate)) ??
      `请生成事故调查情况和整改措施报告（驾驶员：「${driverName}」，日期：「${accidentDate}」）。`
    );
  }

  if (toolCall.tool === 'consult_omni') {
    return String(toolCall.args.query ?? '');
  }

  if (
    toolCall.tool === 'consult_driver_expert' ||
    toolCall.tool === 'consult_vehicle_expert' ||
    toolCall.tool === 'consult_unit_expert' ||
    toolCall.tool === 'consult_route_expert' ||
    toolCall.tool === 'consult_station_expert' ||
    toolCall.tool === 'consult_incident_expert'
  ) {
    return String(toolCall.args.query ?? '');
  }

  if (toolCall.tool === 'rule_reply') {
    const ruleId = toolCall.args.rule_id ?? '';
    const userQuery = toolCall.args.user_query ?? '';

    let prompt = `用户问题：${userQuery}\n\n`;

    if (ruleId) {
      prompt += `请根据规则 ID "${ruleId}" 生成回复。\n`;
      prompt += `1. 先调用 get_rule(rule_id: "${ruleId}") 获取规则详情\n`;
      prompt += `2. 检查用户问题是否包含规则要求的必需参数\n`;
      prompt += `3. 如果缺参则追问；参数齐全则按模板生成回复\n`;
    } else {
      prompt +=
        '当前调用缺少明确的 rule_id，说明上游路由没有完成规则选择。必须立即调用 rule_exit(reason: "missing_rule_context", confidence: 0) 并且不要输出任何用户可见文本。';
    }

    return prompt;
  }

  if (toolCall.tool === 'rule_asker') {
    const userQuery = toolCall.args.user_query ?? '';
    return `请根据用户最新输入继续推进规则配置：
${userQuery}`;
  }

  if (toolCall.tool === 'rule_builder') {
    const payload = JSON.stringify(toolCall.args, null, 2);
    return `请根据以下规则草稿生成最终规则配置 JSON：
${payload}`;
  }

  return String(toolCall.args.query ?? '');
}
