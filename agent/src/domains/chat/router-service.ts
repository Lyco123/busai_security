import { readFirstStringAtPaths } from './structured-report-normalizers';
import {
  buildStructuredReportPrefetchedPrompt,
  ACCIDENT_REPORT_SOURCE_TOOL_NAME,
  DRIVER_REPORT_SOURCE_TOOL_NAME,
  extractDriverReportPartition,
  extractUnitReportPartition,
  extractVehicleReportPartition,
  getStructuredReportDataSourceConfig,
  REPORT_SOURCE_TOOL_DEFINITIONS,
  ROUTE_REPORT_SOURCE_TOOL_NAME,
  STATION_REPORT_SOURCE_TOOL_NAME,
  UNIT_REPORT_SOURCE_TOOL_NAME,
  VEHICLE_REPORT_SOURCE_TOOL_NAME,
} from './structured-report-data-sources';
import { fetchDriverProfileByName } from '../../shared/driver-profile-mcp';
import { fetchRouteProfileByName } from '../../shared/route-profile-mcp';
import { fetchStationProfileByName } from '../../shared/station-profile-mcp';
import { fetchUnitProfileByName } from '../../shared/unit-profile-mcp';
import {
  applyEntityAliasHintToPrompt,
  resolveFleetUnitAliasInText,
  resolveRouteAlias,
  resolveRouteAliasInText,
  resolveUnitAlias,
  resolveUnitAliasInText,
} from '../../shared/entity-alias-resolver';
import { fetchVehicleProfileByNumberplate } from '../../shared/vehicle-profile-mcp';
import { normalizeVehiclePlateArg } from '../../shared/vehicle-plate-normalizer';
import {
  ACCIDENT_INVESTIGATION_MCP_TOOL_NAME,
  fetchAccidentInvestigationByDriverAndDateResult,
} from '../../shared/accident-investigation-mcp';
import {
  buildContextFromHistory,
  type ChatCompletionMessage,
  type HistoryMessage,
} from './context';
import {
  buildPendingFurtherInfoToolPayload,
  createPendingFurtherInfoState,
  type PendingFurtherInfoOption,
  resolveFurtherInfoDisplayMessage,
} from './clarification-state';
import type { StructuredLookupToolName } from './structured-lookup';
import type {
  ChatTurnContext,
  ChatTurnMetadataDetails,
  ResolveWorkerRuntimeOptionsParams,
} from './turn-context';
import {
  buildWorkerPrompt,
  type AssistantProgressUpdate,
  type ToolDefinition,
  type ToolProvider,
  type ToolResult,
  type ToolUsage,
  type StructuredReportWorkerToolName,
  type WorkerAgentStreamEvent,
  type WorkerProbeStageEvent,
  type WorkerRuntimeOptions,
  type WorkerToolName,
} from './worker-runner';
import { extractMessageSources } from '../../shared/message-sources';
import { buildServerTimeSystemPrompt } from './server-time-context';
import { safeJsonParse } from '../../shared/json';
import { isRecord } from '../../shared/guards';

export type VehicleExpertCotMode = 'direct' | 'deep';

const ROUTER_TEMPERATURE = 0.2;
const BLACKSPOT_CONFIRMED_TOOL_NAME = 'get_mcp_blackspot_adsEventBlackSpot_queryConfirmedBlackSpots';

type RouteDirectionConstraint = {
  rawRouteText: string;
  routeName: string;
  direction: '上行' | '下行';
};

function extractRouteDirectionConstraint(value: string): RouteDirectionConstraint | null {
  const normalized = value.normalize('NFKC').trim();
  const patterns = [
    /(?<raw>(?<route>[0-9A-Za-z]+)[（(](?<direction>上行|下行)[）)]路?)/u,
    /(?<raw>(?<route>[0-9A-Za-z]+)路(?<direction>上行|下行))/u,
    /(?<raw>(?<route>[0-9A-Za-z]+)(?<direction>上行|下行)路?)/u,
  ];
  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    const routeName = match?.groups?.route?.trim();
    const direction = match?.groups?.direction?.trim();
    if (
      routeName &&
      (direction === '上行' || direction === '下行') &&
      match?.groups?.raw?.trim()
    ) {
      return {
        rawRouteText: match.groups.raw.trim(),
        routeName,
        direction,
      };
    }
  }
  return null;
}

function buildRouteDirectionConstraintPrompt(
  constraint: RouteDirectionConstraint | null
): string {
  if (!constraint) return '';
  return [
    '线路限定解析提示：',
    `- 用户提到的“${constraint.rawRouteText}”表示线路“${constraint.routeName}”，方向限定为“${constraint.direction}”。`,
    `- 调用线路或黑点类工具时，routeName 必须使用“${constraint.routeName}”，不要把“${constraint.rawRouteText}”整体填入 routeName。`,
    `- 如果工具结果包含非空 direction/方向字段，应按“${constraint.direction}”筛选。`,
    `- 如果工具结果 direction/方向字段为空或缺失，不能声称已严格按“${constraint.direction}”筛选；应说明工具未返回方向字段，只能展示线路“${constraint.routeName}”的相关结果。`,
  ].join('\n');
}

function hasMeaningfulDirection(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function extractToolResultArray(data: unknown): Record<string, unknown>[] | null {
  if (Array.isArray(data)) {
    return data.filter(isRecord);
  }
  if (isRecord(data) && Array.isArray(data.result)) {
    return data.result.filter(isRecord);
  }
  return null;
}

function applyDirectionFilterToToolData(
  data: unknown,
  direction: '上行' | '下行'
): unknown {
  const rows = extractToolResultArray(data);
  if (!rows || rows.length === 0) return data;
  const rowsWithDirection = rows.filter((row) => hasMeaningfulDirection(row.direction));
  if (rowsWithDirection.length === 0) {
    if (!isRecord(data) || !Array.isArray(data.result)) return data;
    return {
      ...data,
      query_direction: direction,
      direction_filter_applied: false,
      direction_filter_note: '工具结果未返回非空 direction 字段，未执行方向过滤。',
    };
  }
  const filtered = rowsWithDirection.filter((row) => String(row.direction).includes(direction));
  if (isRecord(data) && Array.isArray(data.result)) {
    return {
      ...data,
      result: filtered,
      query_direction: direction,
      direction_filter_applied: true,
      direction_filter_before_count: rows.length,
      direction_filter_after_count: filtered.length,
    };
  }
  return filtered;
}

export interface RouteRequestOptions {
  isStream?: boolean;
  sessionId?: string;
  turnContext: ChatTurnContext;
  skipRuleId?: string;
  ruleExitFallback?: boolean;
  onAssistantDelta?: (delta: string) => void;
  onAssistantProgress?: (progress: AssistantProgressUpdate) => void;
  onAgentEvent?: (event: WorkerAgentStreamEvent) => void;
  onProbeEvent?: (event: WorkerProbeStageEvent) => void;
  suppressStageText?: boolean;
  suppressOpeningText?: boolean;
  suppressClosingText?: boolean;
  useCommandRouter?: boolean;
  reportEnvOverride?: any;
}

interface RouteRequestDeps {
  DEFAULT_MODEL: string;
  MAX_ROUTER_TOOL_ITERATIONS: number;
  getRouterSkill: () => string;
  getRouterToolAllowList: () => readonly string[];
  precomputeRuleMatchContext: (env: any, query: string) => Promise<any>;
  renderRuleMatchForPrompt: (
    ruleMatchContext: any,
    routingMode: ChatTurnContext['routingMode'],
    skipRuleId?: string
  ) => string;
  decorateRouteMetadata: (
    turnContext: ChatTurnContext,
    metadata: Record<string, unknown>,
    details?: ChatTurnMetadataDetails
  ) => Record<string, unknown>;
  listWorkScenarios: (db: any, options: { includeDisabled: boolean }) => Promise<any[]>;
  matchWorkScenarioService: (
    env: any,
    content: string,
    scenarios: any[],
    options?: { queryEmbedding?: number[] }
  ) => Promise<any>;
  extractDirectStructuredToolCall: (
    content: string
  ) => { tool: WorkerToolName; args: Record<string, unknown> } | null;
  resolveDriverLookup: (
    db: any,
    query: string,
    toolProvider?: ToolProvider,
    partition?: string
  ) => Promise<any>;
  resolveVehicleLookup: (
    db: any,
    query: string,
    toolProvider?: ToolProvider,
    partition?: string
  ) => Promise<any>;
  resolveUnitLookup: (
    db: any,
    query: string,
    toolProvider?: ToolProvider,
    partition?: string
  ) => Promise<any>;
  resolveRouteLookup: (
    db: any,
    query: string,
    toolProvider?: ToolProvider,
    partition?: string
  ) => Promise<any>;
  resolveStationLookup: (
    db: any,
    query: string,
    toolProvider?: ToolProvider,
    partition?: string
  ) => Promise<any>;
  resolveIncidentLookup: (
    db: any,
    query: string,
    partition?: string | null,
    toolProvider?: ToolProvider
  ) => Promise<any>;
  runWorkerWithTools: (
    env: any,
    workerTool: WorkerToolName,
    userQuery: string,
    isStream?: boolean,
    toolProvider?: any,
    historyMessages?: HistoryMessage[],
    runtimeOptions?: WorkerRuntimeOptions
  ) => Promise<{
    content: string | ReadableStream;
    metadata?: Record<string, unknown>;
    sources?: Array<Record<string, unknown>>;
    leadingContent?: string;
    trailingContent?: string;
  }>;
  resolveWorkerRuntimeOptions?: (
    turnContext: ChatTurnContext,
    params: ResolveWorkerRuntimeOptionsParams
  ) => WorkerRuntimeOptions | undefined;
  createToolProvider: (env: any) => ToolProvider;
  createScopedToolProvider: (
    baseProvider: ToolProvider,
    tools: Record<string, (args: Record<string, unknown>) => ToolResult | Promise<ToolResult>>,
    allowList?: Set<string>,
    toolDefinitions?: Record<string, ToolDefinition>
  ) => ToolProvider;
  getLatestAssistantRoutingContext: (db: any, sessionId: string) => Promise<any>;
  getLatestStructuredReportSource: (value: any) => StructuredReportWorkerToolName | null;
  getLatestStructuredReportFailureSource: (value: any) => StructuredReportWorkerToolName | null;
  validateToolCall: (toolCall: {
    tool: WorkerToolName;
    args: Record<string, unknown>;
  }) => { ok: true } | { ok: false; prompt: string; handling?: 'ask_user' | 'retry_router' };
  callOpenAIRouter: (
    env: any,
    options: {
      model: string;
      temperature?: number;
      messages: ChatCompletionMessage[];
      toolAllowList?: any;
      enableThinking?: boolean;
    }
  ) => Promise<{
    content?: string;
    toolCall?: { id: string; tool: string; args: Record<string, unknown> };
  }>;
  callOpenAICommandRouter: (
    env: any,
    options: {
      model: string;
      temperature?: number;
      messages: ChatCompletionMessage[];
      enableThinking?: boolean;
    }
  ) => Promise<string>;
  isRoutableWorkerToolName: (value: string) => boolean;
  extractRuleIdFromRuleReplyArgs: (args: Record<string, unknown>) => string;
  buildDriverLookupReply: (resolution: any) => string;
  buildVehicleLookupReply: (resolution: any) => string;
  buildUnitLookupReply: (resolution: any) => string;
  buildRouteLookupReply: (resolution: any) => string;
  buildStationLookupReply: (resolution: any) => string;
  buildIncidentLookupReply: (resolution: any) => string;
  buildDriverLookupWorkerPrompt: (resolution: any, partition?: string | null) => string;
  buildVehicleLookupWorkerPrompt: (resolution: any, partition?: string | null) => string;
  buildUnitLookupWorkerPrompt: (resolution: any, partition?: string | null) => string;
  buildRouteLookupWorkerPrompt: (resolution: any, partition?: string | null) => string;
  buildStationLookupWorkerPrompt: (resolution: any, partition?: string | null) => string;
  buildIncidentLookupWorkerPrompt: (resolution: any) => string;
  getStructuredLookupSummary: (
    tool: StructuredLookupToolName,
    resolution: any
  ) => Record<string, unknown>;
}

const CLARIFICATION_CANCEL_TOKENS = ['取消', '算了', '先不用', '不用了', '退出', '结束'] as const;
function normalizeVehicleExpertCotMode(value: unknown): VehicleExpertCotMode {
  return value === 'deep' ? 'deep' : 'direct';
}

function buildClarificationOptions(
  candidates: Array<Record<string, unknown>>
): PendingFurtherInfoOption[] {
  return candidates
    .map((candidate) => {
      const label = String(
        candidate.name ??
          candidate.route_name ??
          candidate.accident_date ??
          candidate.identifier ??
          candidate.id ??
          ''
      ).trim();
      const value = String(
        candidate.identifier ??
          candidate.vehicle_id ??
          candidate.route_id ??
          candidate.driver_name ??
          candidate.id ??
          candidate.name ??
          ''
      ).trim();
      if (!label || !value) return null;
      const aliases = [
        String(candidate.identifier ?? '').trim(),
        String(candidate.vehicle_id ?? '').trim(),
        String(candidate.route_id ?? '').trim(),
        String(candidate.route_name ?? '').trim(),
        String(candidate.driver_name ?? '').trim(),
        String(candidate.ppartition ?? '').trim(),
        String(candidate.accident_date ?? '').trim(),
      ].filter((item) => item.length > 0 && item !== label && item !== value);
      return {
        label,
        value,
        ...(aliases.length ? { aliases } : {}),
      };
    })
    .filter((item): item is PendingFurtherInfoOption => Boolean(item));
}

function buildPendingFurtherInfoFromLookup(
  tool: StructuredLookupToolName,
  resolution: { query: string; reason?: string; candidates?: Array<Record<string, unknown>> },
  knownArgs?: Record<string, unknown>
) {
  if (
    resolution.reason === 'permission_denied' ||
    isInfrastructureLookupFailureReason(resolution.reason)
  ) {
    return null;
  }

  const fieldMap: Record<StructuredLookupToolName, string> = {
    generate_driver_report: 'driver_name',
    generate_vehicle_report: 'numberPlate',
    generate_unit_report: 'organ_name',
    generate_route_report: 'route_name',
    generate_station_report: 'station_name',
    generate_accident_investigation_report: 'driver_name',
  };

  return createPendingFurtherInfoState({
    resume_tool: tool,
    resume_mode: 'fill_args',
    missing_fields: [fieldMap[tool]],
    known_args: knownArgs ?? {},
    options: buildClarificationOptions(
      (resolution.candidates ?? []) as Array<Record<string, unknown>>
    ),
    direct_resume: true,
  });
}

function isInfrastructureLookupFailureReason(value: unknown): boolean {
  return (
    value === 'mcp_unreachable' ||
    value === 'mcp_timeout' ||
    value === 'mcp_5xx' ||
    value === 'payload_mismatch' ||
    value === 'protocol_error' ||
    value === 'upstream_error'
  );
}

function buildStructuredLookupErrorContext(input: {
  workerTool: StructuredLookupToolName;
  lookupReason: string;
  userQuery: string;
}): Record<string, unknown> {
  const targetMap: Record<StructuredLookupToolName, string> = {
    generate_driver_report: 'driver_profile',
    generate_vehicle_report: 'vehicle_profile',
    generate_unit_report: 'unit_profile',
    generate_route_report: 'route_profile',
    generate_station_report: 'station_profile',
    generate_accident_investigation_report: 'incident_profile',
  };
  const labelMap: Partial<Record<StructuredLookupToolName, string>> = {
    generate_driver_report: '驾驶员画像',
    generate_vehicle_report: '车辆画像',
    generate_unit_report: '单位画像',
    generate_route_report: '线路画像',
    generate_accident_investigation_report: '事故案例',
  };
  const canUserFix =
    input.lookupReason === 'too_short' ||
    input.lookupReason === 'invalid_query' ||
    input.lookupReason === 'not_found' ||
    input.lookupReason === 'ambiguous' ||
    input.lookupReason === 'same_name' ||
    input.lookupReason === 'single_candidate';
  const allowedSuggestionsByReason: Record<string, string[]> = {
    too_short: ['补充完整对象标识', '提供画像日期'],
    invalid_query: ['核对名称或编号格式', '提供更准确的对象标识'],
    not_found: ['核对对象标识', '更换画像日期', '提供对象ID'],
    ambiguous: ['从候选项中选择一个对象', '提供更准确的对象标识'],
    same_name: ['提供工号或对象ID', '从候选项中选择一个对象'],
    single_candidate: ['确认候选对象', '提供更准确的对象标识'],
    permission_denied: ['联系管理员开通画像数据权限'],
    mcp_unreachable: ['稍后重试', '联系管理员检查画像服务', '先查询可用基础档案'],
    mcp_timeout: ['稍后重试', '联系管理员检查画像服务', '先查询可用基础档案'],
    mcp_5xx: ['稍后重试', '联系管理员检查画像服务', '先查询可用基础档案'],
    payload_mismatch: ['联系管理员检查画像服务数据格式', '稍后重试'],
    protocol_error: ['联系管理员检查画像服务配置', '稍后重试'],
    upstream_error: ['稍后重试', '联系管理员检查画像服务', '先查询可用基础档案'],
  };
  return {
    kind: input.lookupReason,
    target: targetMap[input.workerTool],
    target_label: labelMap[input.workerTool] ?? input.workerTool,
    user_task: 'generate_report',
    original_message: input.userQuery,
    can_user_fix: canUserFix,
    allowed_suggestions: allowedSuggestionsByReason[input.lookupReason] ?? ['稍后重试'],
    constraints: [
      '不要声称已经查询到画像数据',
      '不要编造报告内容、指标、排名或建议',
      '不要暴露工具名、MCP、路由、metadata、HTTP 状态或内部实现',
      '只基于 error_context 和对话上下文解释当前无法继续的原因',
    ],
  };
}

function buildPendingFurtherInfoFromValidation(toolCall: {
  tool: WorkerToolName;
  args: Record<string, unknown>;
}) {
  const fillArgTools: Partial<Record<WorkerToolName, string>> = {
    generate_driver_report: 'driver_name',
    generate_vehicle_report: 'numberPlate',
    generate_unit_report: 'organ_name',
    generate_route_report: 'route_name',
    generate_station_report: 'station_name',
    generate_accident_investigation_report: 'driver_name',
  };

  if (fillArgTools[toolCall.tool]) {
    return createPendingFurtherInfoState({
      resume_tool: toolCall.tool,
      resume_mode: 'fill_args',
      missing_fields: [fillArgTools[toolCall.tool]!],
      known_args: toolCall.args,
      direct_resume: true,
    });
  }

  return createPendingFurtherInfoState({
    resume_tool: toolCall.tool,
    resume_mode: 'append_user_reply',
    missing_fields: ['follow_up'],
    known_args: toolCall.args,
    direct_resume: true,
  });
}

function looksLikePendingCancellation(content: string): boolean {
  const normalized = content.normalize('NFKC').trim().toLowerCase();
  if (!normalized) return false;
  return CLARIFICATION_CANCEL_TOKENS.some((token) => normalized.startsWith(token));
}

/*
function normalizePendingVehicleToken(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .toUpperCase()
    .replace(/[\s"'`“”‘’（）()【】[\]{}<>]/g, '');
}

function extractLikelyVehiclePlate(content: string): string | null {
  const normalized = content.normalize('NFKC').toUpperCase();
  const match = normalized.match(
    /([京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼港澳使领][A-Z][A-Z0-9]{4,6})/u
  );
  return match ? normalizePendingVehicleToken(match[1]) : null;
}

function shouldForceResumePendingVehicleReport(
  pending:
    | {
        resume_tool: WorkerToolName;
        known_args: Record<string, unknown>;
      }
    | null
    | undefined,
  content: string
): { vehicleId: string } | null {
  if (!pending || pending.resume_tool !== 'generate_vehicle_report') {
    return null;
  }

  const knownVehicleId = String(pending.known_args.numberPlate ?? '').trim();
  if (!knownVehicleId) {
    return null;
  }

  const extractedVehicleId = extractLikelyVehiclePlate(content);
  const normalizedKnownVehicleId = normalizePendingVehicleToken(knownVehicleId);
  const normalizedExtractedVehicleId = extractedVehicleId
    ? normalizePendingVehicleToken(extractedVehicleId)
    : '';
  const requestedPartition = extractVehicleReportPartition(content);
  const repeatsKnownVehicle =
    normalizedExtractedVehicleId.length > 0 &&
    normalizedExtractedVehicleId === normalizedKnownVehicleId;
  const looksLikeVehicleReportRequest =
    /(车辆画像|画像数据|车辆报告|安全报告|风险分析|画像|报告)/.test(content);

  if (repeatsKnownVehicle || (requestedPartition && looksLikeVehicleReportRequest)) {
    return { vehicleId: extractedVehicleId || knownVehicleId };
  }

  return null;
}

*/
function renderPendingFurtherInfoPrompt(
  pending: {
    resume_tool: WorkerToolName;
    resume_mode: 'fill_args' | 'append_user_reply';
    missing_fields: string[];
    known_args: Record<string, unknown>;
    options: PendingFurtherInfoOption[];
    direct_resume: boolean;
  },
  latestAssistantContent?: string | null
): string {
  const candidateLines = pending.options.length
    ? pending.options
        .slice(0, 10)
        .map((option, index) => {
          const aliases = option.aliases?.length ? ` aliases=${option.aliases.join(' / ')}` : '';
          return `${index + 1}. ${option.label} => ${option.value}${aliases}`;
        })
        .join('\n')
    : '(none)';

  const latestAssistantSnippet = String(latestAssistantContent ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 300);

  return [
    'PENDING FURTHER INFO CONTEXT:',
    '- The previous assistant turn left a resumable clarification state.',
    `- resume_tool: ${pending.resume_tool}`,
    `- resume_mode: ${pending.resume_mode}`,
    `- missing_fields: ${pending.missing_fields.join(', ') || '(none)'}`,
    `- known_args: ${JSON.stringify(pending.known_args)}`,
    `- direct_resume: ${String(pending.direct_resume)}`,
    `- latest_assistant_clarification: ${latestAssistantSnippet || '(empty)'}`,
    '- candidate_options:',
    candidateLines,
    '- First decide whether the current user message is:',
    '  A. a direct answer to the pending clarification, so you should resume the pending tool;',
    '  B. a new request / topic shift, so you must ignore the pending clarification and route normally;',
    '  C. still ambiguous, so you should ask for clarification again and call request_further_info.',
    '- If the current user message only supplies part of the missing information, a short slot value, a JSON/key-value fragment, or a terse continuation that can be combined with known_args or the latest clarification, treat it as a continuation candidate rather than a brand-new request.',
    '- Resume the pending tool only when the user clearly provides the missing value or clearly selects one of the candidate options.',
    '- If the user asks a broader/new question, changes target, asks for a list/overview, or shifts topic, ignore the pending clarification and route based on the current turn.',
    '- If the user explicitly cancels, do not resume the pending task.',
    '- If uncertain, do not auto-resume. Prefer either normal routing for the current request or a fresh clarification.',
  ].join('\n');
}

function renderLatestStructuredReportPrompt(input: {
  latestStructuredReportSource: StructuredReportWorkerToolName | null;
  latestStructuredReportFailureSource: StructuredReportWorkerToolName | null;
  assistantContent?: string | null;
  reportFollowUp?: { source_tool: StructuredReportWorkerToolName } | null;
}): string {
  const latestAssistantSnippet = String(input.assistantContent ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 300);
  const status = input.latestStructuredReportFailureSource
    ? 'failed'
    : input.latestStructuredReportSource
      ? 'success'
      : 'none';
  const sourceTool =
    input.latestStructuredReportFailureSource ?? input.latestStructuredReportSource ?? '(none)';
  const reportFollowUpSource = input.reportFollowUp?.source_tool ?? '(none)';

  return [
    'LATEST STRUCTURED REPORT CONTEXT:',
    '- The previous assistant turn may have created or referenced a structured report.',
    `- latest_report_status: ${status}`,
    `- latest_report_source_tool: ${sourceTool}`,
    `- latest_report_follow_up_source: ${reportFollowUpSource}`,
    `- latest_report_assistant_snippet: ${latestAssistantSnippet || '(empty)'}`,
    '- If the current user message is clearly asking to explain, expand, verify, compare, or correct the latest report, route to a consult tool instead of regenerating a full report.',
    '- If the current user message is a short continuation such as a date, partition, target confirmation, or a terse instruction like "use this one" / "regenerate with this", you may combine it with the latest report context to recover the same target and task, unless the user clearly changed topic or target.',
    '- For vehicle-report follow-up questions, prefer consult_vehicle_expert. For driver-report follow-up questions, prefer consult_driver_expert. For unit-report follow-up questions, prefer consult_unit_expert. For route-report follow-up questions, prefer consult_route_expert. For station-report follow-up questions, prefer consult_station_expert. For accident-investigation-report follow-up questions, prefer consult_incident_expert. For other report follow-up questions, prefer consult_omni.',
    '- If the user explicitly asks to regenerate, recreate, update, or issue a fresh report, choose the corresponding generate_*_report tool.',
    '- If the user changes topic, target, or asks a fresh query, ignore this report context and route based on the current turn only.',
    '- If the latest report failed, treat that failure only as context. Do not hard-refuse and do not auto-retry unless the current turn clearly asks to regenerate the report or clearly supplies the missing report target information.',
  ].join('\n');
}

function buildCommandRouterInstruction(toolAllowList: readonly string[]): string {
  return [
    'COMMAND ROUTER OUTPUT:',
    '- 这是仅用于探针的 command router。不要使用 OpenAI tool/function calling。',
    '- 只输出一个 JSON 对象，不要输出 markdown。',
    '- JSON 结构为：{"tool":"tool_name","args":{...},"confidence":0.0,"reason_code":"short_code"}。',
    `- tool 必须是以下之一：${toolAllowList.join(', ') || '(none)'}。`,
    '- consult_* 工具必须提供 args.query；不确定时，使用用户原始消息作为 query。',
    '- generate_vehicle_report 使用 args.numberPlate；generate_driver_report 使用 args.driver_name；generate_unit_report 使用 args.organ_name；generate_route_report 使用 args.route_name；generate_station_report 使用 args.station_name；generate_accident_investigation_report 使用 args.driver_name 和 args.accident_date。',
    '- rule_reply 必须提供 args.user_query 和当前规则匹配结果中的 args.rule_id。',
    '- 仅 request_further_info 可以提供顶层 display_message，内容必须是要展示给用户的澄清问题；args 只保存可恢复状态。',
    '- 其他工具不得提供 display_message。',
  ].join('\n');
}

function normalizeCommandRouterDisplayMessage(
  record: Record<string, unknown>,
  tool: string
): string | undefined {
  if (tool !== 'request_further_info') return undefined;

  const rawMessage = record.display_message ?? record.displayMessage;
  if (typeof rawMessage !== 'string') return undefined;

  const message = rawMessage.trim();
  if (!message) return undefined;
  if (message.length > 500) return undefined;

  const parsed = safeJsonParse(message);
  if (parsed !== null && (isRecord(parsed) || Array.isArray(parsed))) {
    return undefined;
  }

  if (
    /\b(?:request_further_info|resume_tool|resume_mode|known_args|missing_fields|consult_omni|consult_[a-z_]+|generate_[a-z_]+)\b/i.test(
      message
    )
  ) {
    return undefined;
  }

  return message;
}

function parseCommandRouterToolCall(
  rawContent: string,
  allowedTools: readonly string[],
  userContent: string
): {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  displayMessage?: string;
} | null {
  const allowed = new Set(allowedTools);
  const parsed = safeJsonParse(rawContent);
  let record: Record<string, unknown> | null = isRecord(parsed) ? parsed : null;

  if (!record) {
    const routeMatch = rawContent.match(/\b(?:ROUTE|COMMAND)\s+([a-zA-Z0-9_]+)/);
    if (routeMatch?.[1]) {
      record = { tool: routeMatch[1], args: {} };
    }
  }
  if (!record) return null;

  const tool = String(record.tool ?? record.command ?? record.route ?? '').trim();
  if (!tool || !allowed.has(tool)) return null;

  const args = isRecord(record.args) ? { ...record.args } : {};
  if (
    (tool === 'consult_omni' ||
      tool === 'consult_driver_expert' ||
      tool === 'consult_vehicle_expert' ||
      tool === 'consult_unit_expert' ||
      tool === 'consult_route_expert' ||
      tool === 'consult_station_expert' ||
      tool === 'consult_incident_expert') &&
    typeof args.query !== 'string'
  ) {
    args.query = userContent;
  }
  if (tool === 'rule_reply' && typeof args.user_query !== 'string') {
    args.user_query = userContent;
  }

  return {
    id: `command_${crypto.randomUUID()}`,
    tool,
    args,
    displayMessage: normalizeCommandRouterDisplayMessage(record, tool),
  };
}

export function createRouteRequestHandler(deps: RouteRequestDeps) {
  async function routeRequest(
    env: any,
    content: string,
    historyMessages: HistoryMessage[] = [],
    options: RouteRequestOptions
  ): Promise<{
    content: string | ReadableStream;
    metadata?: Record<string, unknown>;
    sources?: Array<Record<string, unknown>>;
    leadingContent?: string;
    trailingContent?: string;
  }> {
    const reportEnv = options.reportEnvOverride || env;
    const turnContext = options.turnContext;
    const routingMode = turnContext.routingMode;
    const sharedRuntimeOptions =
      options.onAssistantDelta ||
      options.onAssistantProgress ||
      options.onAgentEvent ||
      options.onProbeEvent ||
      options.suppressStageText ||
      options.suppressOpeningText ||
      options.suppressClosingText
        ? ({
            ...(options.onAssistantDelta ? { onAssistantDelta: options.onAssistantDelta } : {}),
            ...(options.onAssistantProgress
              ? { onAssistantProgress: options.onAssistantProgress }
              : {}),
            ...(options.onAgentEvent ? { onAgentEvent: options.onAgentEvent } : {}),
            ...(options.onProbeEvent ? { onProbeEvent: options.onProbeEvent } : {}),
            ...(options.suppressStageText ? { suppressStageText: true } : {}),
            ...(options.suppressOpeningText ? { suppressOpeningText: true } : {}),
            ...(options.suppressClosingText ? { suppressClosingText: true } : {}),
          } satisfies WorkerRuntimeOptions)
        : undefined;
    let blockedRuleId = typeof options.skipRuleId === 'string' ? options.skipRuleId.trim() : '';
    let ruleExitFallbackTriggered = Boolean(options.ruleExitFallback);
    const createStructuredReportToolProvider = (
      workerTool: StructuredReportWorkerToolName
    ): ToolProvider | undefined => {
      const dataSourceConfig = getStructuredReportDataSourceConfig(workerTool);
      if (!dataSourceConfig?.toolAllowList?.length) {
        return undefined;
      }
      const overrides: Record<
        string,
        (args: Record<string, unknown>) => ToolResult | Promise<ToolResult>
      > = {};
      if (workerTool === 'generate_driver_report') {
        overrides[DRIVER_REPORT_SOURCE_TOOL_NAME] = async (args) => {
          const driverName = String(args.driverName ?? args.driver_name ?? '').trim();
          const partition = String(args.ppartition ?? args.partition ?? '').trim() || undefined;
          if (!driverName) {
            return { success: false, error: 'missing_driver_name' };
          }
          const data = await fetchDriverProfileByName(env, driverName, partition);
          if (!data) {
            return { success: false, error: 'driver_not_found' };
          }
          return { success: true, data };
        };
      }
      if (workerTool === 'generate_vehicle_report') {
        overrides[VEHICLE_REPORT_SOURCE_TOOL_NAME] = async (args) => {
          const numberplate = String(args.numberPlate ?? args.number_plate ?? '').trim();
          const partition = String(args.ppartition ?? args.partition ?? '').trim() || undefined;
          if (!numberplate) {
            return { success: false, error: 'missing_numberplate' };
          }
          const data = await fetchVehicleProfileByNumberplate(env, numberplate, partition);
          if (!data) {
            return { success: false, error: 'vehicle_not_found' };
          }
          return { success: true, data };
        };
      }
      if (workerTool === 'generate_unit_report') {
        overrides[UNIT_REPORT_SOURCE_TOOL_NAME] = async (args) => {
          const organName = String(args.organName ?? args.organ_name ?? '').trim();
          const partition = String(args.ppartition ?? args.partition ?? '').trim() || undefined;
          if (!organName) {
            return { success: false, error: 'missing_organ_name' };
          }
          const data = await fetchUnitProfileByName(env, organName, partition);
          if (!data) {
            return { success: false, error: 'unit_not_found' };
          }
          return { success: true, data };
        };
      }
      if (workerTool === 'generate_route_report') {
        overrides[ROUTE_REPORT_SOURCE_TOOL_NAME] = async (args) => {
          const routeName = String(args.routeName ?? args.route_name ?? '').trim();
          const partition = String(args.ppartition ?? args.partition ?? '').trim() || undefined;
          if (!routeName) {
            return { success: false, error: 'missing_route_name' };
          }
          const data = await fetchRouteProfileByName(env, routeName, partition);
          if (!data) {
            return { success: false, error: 'route_not_found' };
          }
          return { success: true, data };
        };
      }
      if (workerTool === 'generate_station_report') {
        overrides[STATION_REPORT_SOURCE_TOOL_NAME] = async (args) => {
          const stationName = String(
            args.busStationName ?? args.stationName ?? args.station_name ?? ''
          ).trim();
          const partition = String(args.ppartition ?? args.partition ?? '').trim() || undefined;
          if (!stationName) {
            return { success: false, error: 'missing_station_name' };
          }
          const data = await fetchStationProfileByName(env, stationName, partition);
          if (!data) {
            return { success: false, error: 'station_not_found' };
          }
          return { success: true, data };
        };
      }
      if (workerTool === 'generate_accident_investigation_report') {
        overrides[ACCIDENT_REPORT_SOURCE_TOOL_NAME] = async (args) => {
          const driverNameArg = String(args.driverName ?? args.driver_name ?? '').trim();
          const partitionArg = String(args.accidentDate ?? args.accident_date ?? '').trim();
          if (!driverNameArg) {
            return { success: false, error: 'missing_driver_name' };
          }
          const result = await fetchAccidentInvestigationByDriverAndDateResult(
            env,
            driverNameArg,
            partitionArg
          );
          if (result.success === false) {
            return {
              success: false,
              error: result.error,
              ...(result.detail ? { detail: result.detail } : {}),
            };
          }
          return { success: true, data: result.data };
        };
      }
      return deps.createScopedToolProvider(
        deps.createToolProvider(env),
        overrides,
        new Set(dataSourceConfig.toolAllowList),
        REPORT_SOURCE_TOOL_DEFINITIONS
      );
    };

    const createRouteExpertToolProvider = (
      routeConstraint: RouteDirectionConstraint | null
    ): ToolProvider => {
      const baseProvider = deps.createToolProvider(env);
      return deps.createScopedToolProvider(baseProvider, {
        [BLACKSPOT_CONFIRMED_TOOL_NAME]: async (args) => {
          const rawRouteName = String(args.routeName ?? args.route_name ?? '').trim();
          const argConstraint = extractRouteDirectionConstraint(rawRouteName);
          const effectiveConstraint = argConstraint ?? routeConstraint;
          const normalizedArgs = {
            ...args,
            ...(effectiveConstraint ? { routeName: effectiveConstraint.routeName } : {}),
          };
          const result = await baseProvider.callTool(BLACKSPOT_CONFIRMED_TOOL_NAME, normalizedArgs);
          if (!result.success || !effectiveConstraint) {
            return result;
          }
          return {
            ...result,
            data: applyDirectionFilterToToolData(result.data, effectiveConstraint.direction),
          };
        },
      });
    };

    const emitProbeStage = (stage: string, detail?: Record<string, unknown>) => {
      options.onProbeEvent?.({
        type: 'probe_stage',
        stage,
        ...(detail ? { detail } : {}),
      });
    };

    emitProbeStage('rule_match_started');
    const ruleMatchContext = await deps.precomputeRuleMatchContext(env, content);
    emitProbeStage('rule_match_done', {
      ok: ruleMatchContext.ok === true,
      total_matched: Array.isArray(ruleMatchContext.matches) ? ruleMatchContext.matches.length : 0,
    });
    const topScore =
      typeof ruleMatchContext.matches?.[0]?.score === 'number'
        ? ruleMatchContext.matches[0].score
        : undefined;
    const ruleMatchPrompt = deps.renderRuleMatchForPrompt(
      ruleMatchContext,
      routingMode,
      blockedRuleId || undefined
    );
    const ruleMatchMeta = {
      ok: ruleMatchContext.ok,
      total_matched: Array.isArray(ruleMatchContext.matches) ? ruleMatchContext.matches.length : 0,
      top: ruleMatchContext.matches?.[0]
        ? {
            rule_id: ruleMatchContext.matches[0].rule_id,
            rule_name: ruleMatchContext.matches[0].rule_name,
            score: ruleMatchContext.matches[0].score,
          }
        : undefined,
      error: ruleMatchContext.ok ? undefined : ruleMatchContext.error,
    };
    const matchedRuleIds = new Set(
      (Array.isArray(ruleMatchContext.matches) ? ruleMatchContext.matches : [])
        .map((item: { rule_id?: string }) =>
          typeof item?.rule_id === 'string' ? item.rule_id.trim() : ''
        )
        .filter(Boolean)
    );
    const extractRuleIdFromArgs = (args: Record<string, unknown>): string => {
      const direct = typeof args.rule_id === 'string' ? args.rule_id.trim() : '';
      if (direct) return direct;
      const hitRules = args.hit_rules;
      if (!Array.isArray(hitRules) || !hitRules.length) return '';
      const first = hitRules[0];
      if (!first || typeof first !== 'object' || Array.isArray(first)) return '';
      const value = (first as Record<string, unknown>).rule_id;
      return typeof value === 'string' ? value.trim() : '';
    };

    const decorateRouteMetadata = (
      metadata: Record<string, unknown>,
      selectedTool: string | null,
      selectedRuleId?: string | null,
      overrideRuleExitFallback?: boolean
    ): Record<string, unknown> => {
      return deps.decorateRouteMetadata(turnContext, metadata, {
        topScore,
        selectedTool,
        selectedRuleId: selectedRuleId ?? null,
        ruleExitFallback:
          typeof overrideRuleExitFallback === 'boolean'
            ? overrideRuleExitFallback
            : ruleExitFallbackTriggered,
        skipRuleId: blockedRuleId || null,
      });
    };

    const runConsultWorker = async (params: {
      workerTool:
        | 'consult_omni'
        | 'consult_driver_expert'
        | 'consult_vehicle_expert'
        | 'consult_unit_expert'
        | 'consult_route_expert'
        | 'consult_station_expert'
        | 'consult_incident_expert';
      prompt: string;
      metadata: Record<string, unknown>;
      selectedRuleId?: string | null;
      toolProvider?: ToolProvider;
      runtimeOptions?: WorkerRuntimeOptions;
    }): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      emitProbeStage('worker_selected', { worker_tool: params.workerTool });
      const workerOutput = await deps.runWorkerWithTools(
        env,
        params.workerTool,
        params.prompt,
        options.isStream ?? false,
        params.toolProvider,
        historyMessages,
        {
          ...sharedRuntimeOptions,
          ...params.runtimeOptions,
          onAssistantDelta: options.onAssistantDelta,
          onAssistantProgress: options.onAssistantProgress,
          onAgentEvent: options.onAgentEvent,
          onProbeEvent: options.onProbeEvent,
        }
      );
      return {
        ...workerOutput,
        sources: workerOutput.sources,
        metadata: decorateRouteMetadata(
          {
            ...workerOutput.metadata,
            ...params.metadata,
          },
          params.workerTool,
          params.selectedRuleId ?? null
        ),
      };
    };

    const runStructuredLookupClarification = async (params: {
      userQuery: string;
      workerTool: StructuredLookupToolName;
      lookupReason: string;
      fallbackContent: string;
      metadata: Record<string, unknown>;
      selectedRuleId?: string | null;
    }): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      const errorContext = buildStructuredLookupErrorContext({
        workerTool: params.workerTool,
        lookupReason: params.lookupReason,
        userQuery: params.userQuery,
      });
      const clarificationMessages: ChatCompletionMessage[] = [
        {
          role: 'system',
          content: `你是受控错误回复器，只负责把结构化错误上下文改写成自然、简洁、可执行的用户回复。

规则：
- 不要调用任何工具，不要继续路由，不要生成报告。
- 不要提及工具名、路由、metadata、HTTP、MCP、Cloudflare、内部异常或实现细节。
- 不要猜测 error_context 之外的故障原因，不要把系统侧访问失败说成用户输入错误。
- 不要声称已经查询到画像数据，不要编造报告内容、指标、排名或建议。
- 使用与用户当前消息一致的语言。
- 必须结合当前用户消息和必要的对话上下文，避免答非所问。
- 先说明当前无法完成什么，再给出 error_context.allowed_suggestions 中允许的下一步。
- 回复保持简洁，最多两行短句。`,
        },
        ...buildContextFromHistory(historyMessages),
        {
          role: 'user',
          content: [
            `当前用户消息：${params.userQuery}`,
            `error_context：${JSON.stringify(errorContext)}`,
            '请直接写出这一轮最终 assistant 回复。',
          ].join('\n'),
        },
      ];

      try {
        const routerOutput = await deps.callOpenAIRouter(env, {
          model: env.OPENAI_ROUTER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
          temperature: ROUTER_TEMPERATURE,
          messages: clarificationMessages,
          toolAllowList: [],
          enableThinking: false,
        });
        const generatedContent = String(routerOutput.content ?? '').trim();
        if (!generatedContent || routerOutput.toolCall) {
          return {
            content: params.fallbackContent,
            metadata: decorateRouteMetadata(
              {
                ...params.metadata,
                structured_lookup_clarification: {
                  mode: 'fallback',
                  error_context: errorContext,
                  reason: routerOutput.toolCall
                    ? 'unexpected_router_tool_call'
                    : 'empty_router_output',
                },
              },
              null,
              params.selectedRuleId ?? null
            ),
          };
        }
        return {
          content: generatedContent,
          metadata: decorateRouteMetadata(
            {
              ...params.metadata,
              structured_lookup_clarification: {
                mode: 'error_responder_llm',
                error_context: errorContext,
              },
            },
            null,
            params.selectedRuleId ?? null
          ),
        };
      } catch (error) {
        return {
          content: params.fallbackContent,
          metadata: decorateRouteMetadata(
            {
              ...params.metadata,
              structured_lookup_clarification: {
                mode: 'fallback',
                error_context: errorContext,
                reason: error instanceof Error ? error.message : 'unknown_error',
              },
            },
            null,
            params.selectedRuleId ?? null
          ),
        };
      }
    };

    const scenarios = await deps.listWorkScenarios(env.DB, { includeDisabled: false });
    if (!scenarios.length) {
      return {
        content: 'No work scenarios configured yet; cannot process this request.',
        metadata: decorateRouteMetadata(
          { scenario: { matched: false, reason: 'empty' }, rule_match: ruleMatchMeta },
          null
        ),
      };
    }

    const sharedQueryEmbedding = Array.isArray(ruleMatchContext.queryEmbedding)
      ? ruleMatchContext.queryEmbedding
      : undefined;
    const scenarioMatch = await deps.matchWorkScenarioService(
      env,
      content,
      scenarios,
      sharedQueryEmbedding ? { queryEmbedding: sharedQueryEmbedding } : undefined
    );

    if (!scenarioMatch.candidates.length) {
      return {
        content: 'No available work scenario candidates at this time.',
        metadata: decorateRouteMetadata(
          {
            scenario: { matched: false, reason: 'no_candidates', method: scenarioMatch.method },
            rule_match: ruleMatchMeta,
          },
          null
        ),
      };
    }

    const scenarioMeta = {
      method: scenarioMatch.method,
      candidates_count: scenarioMatch.candidates.length,
      best_score: scenarioMatch.best?.score,
      reason: scenarioMatch.reason,
    };
    const latestRoutingContext = options.sessionId
      ? await deps.getLatestAssistantRoutingContext(env.DB, options.sessionId)
      : null;
    const pendingFurtherInfo = latestRoutingContext?.pendingFurtherInfo ?? null;
    const latestStructuredReportSource = deps.getLatestStructuredReportSource(latestRoutingContext);
    const latestStructuredReportFailureSource =
      deps.getLatestStructuredReportFailureSource(latestRoutingContext);
    let directToolCall = deps.extractDirectStructuredToolCall(content);
    if (directToolCall?.tool === 'rule_reply') {
      const selectedRuleId = extractRuleIdFromArgs(directToolCall.args);
      if (!selectedRuleId || !matchedRuleIds.has(selectedRuleId)) {
        directToolCall = null;
      }
    }
    const structuredLookupTools = new Set<StructuredLookupToolName>([
      'generate_driver_report',
      'generate_vehicle_report',
      'generate_unit_report',
      'generate_route_report',
      'generate_station_report',
      'generate_accident_investigation_report',
    ]);
    const preRouterFleetUnitAlias = await resolveFleetUnitAliasInText(env.DB, content);
    const preRouterUnitAlias = await resolveUnitAliasInText(env.DB, content);
    const preRouterRouteAlias = await resolveRouteAliasInText(env.DB, content);
    const routerAliasGuide = [
      (preRouterFleetUnitAlias ?? preRouterUnitAlias)?.hint,
      preRouterRouteAlias?.hint,
    ]
      .filter(Boolean)
      .join('\n\n');
    const buildShortcutScenarioMeta = () => ({
      ...scenarioMeta,
      matched: true,
      shortcut: true,
      scenario_id: scenarioMatch.best?.scenario.id,
      scenario_name: scenarioMatch.best?.scenario.name,
      score: scenarioMatch.best?.score,
    });
    const routerToolUsages: ToolUsage[] = [];

    const handleDriverReportResolution = async (
      driverNameRaw: string,
      requestedPartitionArg?: string | null,
      selectedRuleId?: string | null
    ): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      const requestedPartition =
        extractDriverReportPartition(String(requestedPartitionArg ?? '')) ||
        extractDriverReportPartition(content) ||
        undefined;
      const baseProvider = deps.createToolProvider(env);
      const driverResolution = await deps.resolveDriverLookup(
        env.DB,
        driverNameRaw,
        baseProvider,
        requestedPartition
      );
      if (driverResolution.kind === 'resolved') {
        const toolOutput = await deps.runWorkerWithTools(
          reportEnv,
          'generate_driver_report',
          buildStructuredReportPrefetchedPrompt({
            workerTool: 'generate_driver_report',
            displayName:
              readFirstStringAtPaths(driverResolution.data, ['basic.driver_name', 'name']) ??
              driverResolution.candidate.name,
            entityId:
              readFirstStringAtPaths(driverResolution.data, [
                'basic.driver_id',
                'identifier',
                'id',
              ]) ??
              driverResolution.candidate.identifier ??
              null,
            partition: requestedPartition ?? null,
            sourceData: driverResolution.data,
          }),
          options.isStream ?? false,
          deps.createScopedToolProvider(baseProvider, {}, new Set()),
          historyMessages,
          { ...sharedRuntimeOptions, prefetchedSourceData: driverResolution.data }
        );
        return {
          ...toolOutput,
          sources: extractMessageSources(driverResolution.data),
          metadata: decorateRouteMetadata(
            {
              ...toolOutput.metadata,
              driver_lookup: {
                kind: driverResolution.kind,
                query: driverResolution.query,
                match_type: driverResolution.matchType,
                candidate: driverResolution.candidate,
                requested_partition: requestedPartition ?? null,
              },
              scenario: {
                ...scenarioMeta,
                matched: true,
                shortcut: true,
                scenario_id: scenarioMatch.best?.scenario.id,
                scenario_name: scenarioMatch.best?.scenario.name,
                score: scenarioMatch.best?.score,
              },
              rule_match: ruleMatchMeta,
            },
            'generate_driver_report',
            selectedRuleId ?? null
          ),
        };
      }

      return runStructuredLookupClarification({
        userQuery: content,
        workerTool: 'generate_driver_report',
        lookupReason: String(driverResolution.reason ?? 'not_found'),
        fallbackContent: deps.buildDriverLookupReply(driverResolution),
        metadata: {
          driver_lookup: {
            kind: driverResolution.kind,
            query: driverResolution.query,
            reason: driverResolution.reason,
            candidates: driverResolution.candidates,
          },
          pending_further_info: buildPendingFurtherInfoFromLookup(
            'generate_driver_report',
            driverResolution
          ),
          scenario: {
            ...scenarioMeta,
            matched: true,
            shortcut: true,
            scenario_id: scenarioMatch.best?.scenario.id,
            scenario_name: scenarioMatch.best?.scenario.name,
            score: scenarioMatch.best?.score,
          },
          rule_match: ruleMatchMeta,
        },
        selectedRuleId: selectedRuleId ?? null,
      });
    };

    const handleVehicleReportResolution = async (
      vehicleIdRaw: string,
      requestedPartitionArg?: string | null,
      selectedRuleId?: string | null
    ): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      const requestedPartition =
        extractVehicleReportPartition(String(requestedPartitionArg ?? '')) ||
        extractVehicleReportPartition(content) ||
        undefined;
      const baseProvider = deps.createToolProvider(env);
      const vehicleResolution = await deps.resolveVehicleLookup(
        env.DB,
        vehicleIdRaw,
        baseProvider,
        requestedPartition
      );
      if (vehicleResolution.kind === 'resolved') {
        const toolOutput = await deps.runWorkerWithTools(
          reportEnv,
          'generate_vehicle_report',
          buildStructuredReportPrefetchedPrompt({
            workerTool: 'generate_vehicle_report',
            displayName:
              String(
                vehicleResolution.candidate.identifier ?? vehicleResolution.candidate.name
              ).trim() || vehicleResolution.candidate.name,
            entityId:
              String(
                vehicleResolution.candidate.identifier ?? vehicleResolution.candidate.name
              ).trim() || null,
            partition: requestedPartition ?? null,
            sourceData: vehicleResolution.data,
          }),
          options.isStream ?? false,
          deps.createScopedToolProvider(baseProvider, {}, new Set()),
          historyMessages,
          { ...sharedRuntimeOptions, prefetchedSourceData: vehicleResolution.data }
        );
        return {
          ...toolOutput,
          sources: extractMessageSources(vehicleResolution.data),
          metadata: decorateRouteMetadata(
            {
              ...toolOutput.metadata,
              vehicle_lookup: {
                kind: vehicleResolution.kind,
                query: vehicleResolution.query,
                match_type: vehicleResolution.matchType,
                candidate: vehicleResolution.candidate,
                partition: requestedPartition,
              },
              scenario: {
                ...scenarioMeta,
                matched: true,
                shortcut: true,
                scenario_id: scenarioMatch.best?.scenario.id,
                scenario_name: scenarioMatch.best?.scenario.name,
                score: scenarioMatch.best?.score,
              },
              rule_match: ruleMatchMeta,
            },
            'generate_vehicle_report',
            selectedRuleId ?? null
          ),
        };
      }

      return runStructuredLookupClarification({
        userQuery: content,
        workerTool: 'generate_vehicle_report',
        lookupReason: String(vehicleResolution.reason ?? 'not_found'),
        fallbackContent: deps.buildVehicleLookupReply(vehicleResolution),
        metadata: {
          vehicle_lookup: {
            kind: vehicleResolution.kind,
            query: vehicleResolution.query,
            reason: vehicleResolution.reason,
            candidates: vehicleResolution.candidates,
            partition: requestedPartition,
          },
          pending_further_info: buildPendingFurtherInfoFromLookup(
            'generate_vehicle_report',
            vehicleResolution,
            {
              numberPlate: vehicleIdRaw,
              ...(requestedPartition ? { ppartition: requestedPartition } : {}),
            }
          ),
          scenario: {
            ...scenarioMeta,
            matched: true,
            shortcut: true,
            scenario_id: scenarioMatch.best?.scenario.id,
            scenario_name: scenarioMatch.best?.scenario.name,
            score: scenarioMatch.best?.score,
          },
          rule_match: ruleMatchMeta,
        },
        selectedRuleId: selectedRuleId ?? null,
      });
    };

    const handleUnitReportResolution = async (
      organNameRaw: string,
      requestedPartitionArg?: string | null,
      selectedRuleId?: string | null
    ): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      const requestedPartition =
        extractUnitReportPartition(String(requestedPartitionArg ?? '')) ||
        extractUnitReportPartition(content) ||
        undefined;
      const contentFleetUnitAlias = await resolveFleetUnitAliasInText(env.DB, content);
      const contentUnitAlias = await resolveUnitAliasInText(env.DB, content);
      const requestedOrganName = contentFleetUnitAlias?.standardName ?? organNameRaw;
      const directUnitAlias = await resolveUnitAlias(env.DB, requestedOrganName);
      const aliasResolution = directUnitAlias ?? contentFleetUnitAlias ?? contentUnitAlias;
      const lookupOrganName = aliasResolution?.standardName ?? requestedOrganName;
      const baseProvider = deps.createToolProvider(env);
      const unitResolution = await deps.resolveUnitLookup(
        env.DB,
        lookupOrganName,
        baseProvider,
        requestedPartition
      );
      if (unitResolution.kind === 'resolved') {
        const toolOutput = await deps.runWorkerWithTools(
          reportEnv,
          'generate_unit_report',
          applyEntityAliasHintToPrompt(
            buildStructuredReportPrefetchedPrompt({
              workerTool: 'generate_unit_report',
              displayName:
                readFirstStringAtPaths(unitResolution.data, ['basic.organ_name', 'name']) ??
                unitResolution.candidate.name,
              entityId:
                readFirstStringAtPaths(unitResolution.data, [
                  'basic.organ_id',
                  'identifier',
                  'id',
                ]) ??
                unitResolution.candidate.identifier ??
                null,
              partition: requestedPartition ?? null,
              sourceData: unitResolution.data,
            }),
            aliasResolution
          ),
          options.isStream ?? false,
          deps.createScopedToolProvider(baseProvider, {}, new Set()),
          historyMessages,
          { ...sharedRuntimeOptions, prefetchedSourceData: unitResolution.data }
        );
        return {
          ...toolOutput,
          sources: extractMessageSources(unitResolution.data),
          metadata: decorateRouteMetadata(
            {
              ...toolOutput.metadata,
              unit_lookup: {
                kind: unitResolution.kind,
                query: unitResolution.query,
                match_type: unitResolution.matchType,
                candidate: unitResolution.candidate,
                alias: aliasResolution,
                requested_partition: requestedPartition ?? null,
              },
              scenario: buildShortcutScenarioMeta(),
              rule_match: ruleMatchMeta,
            },
            'generate_unit_report',
            selectedRuleId ?? null
          ),
        };
      }

      return runStructuredLookupClarification({
        userQuery: content,
        workerTool: 'generate_unit_report',
        lookupReason: String(unitResolution.reason ?? 'not_found'),
        fallbackContent: deps.buildUnitLookupReply(unitResolution),
        metadata: {
          unit_lookup: deps.getStructuredLookupSummary('generate_unit_report', unitResolution),
          pending_further_info: buildPendingFurtherInfoFromLookup(
            'generate_unit_report',
            unitResolution,
            {
              organ_name: organNameRaw,
              ...(requestedPartition ? { ppartition: requestedPartition } : {}),
            }
          ),
          scenario: buildShortcutScenarioMeta(),
          rule_match: ruleMatchMeta,
        },
        selectedRuleId: selectedRuleId ?? null,
      });
    };

    const handleRouteReportResolution = async (
      routeNameRaw: string,
      requestedPartitionRaw?: string,
      selectedRuleId?: string | null
    ): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      const requestedPartition = String(requestedPartitionRaw ?? '').trim() || undefined;
      const aliasResolution =
        (await resolveRouteAlias(env.DB, routeNameRaw)) ??
        (await resolveRouteAliasInText(env.DB, content));
      const lookupRouteName = aliasResolution?.standardName ?? routeNameRaw;
      const baseProvider = deps.createToolProvider(env);
      const routeResolution = await deps.resolveRouteLookup(
        env.DB,
        lookupRouteName,
        baseProvider,
        requestedPartition
      );
      if (routeResolution.kind === 'resolved') {
        const resolvedRouteName =
          readFirstStringAtPaths(routeResolution.data, [
            'basic.route_name',
            'route_name',
            'name',
          ]) ??
          routeResolution.candidate.route_name ??
          routeResolution.candidate.name;
        const resolvedRouteId =
          readFirstStringAtPaths(routeResolution.data, [
            'basic.route_id',
            'route_id',
            'identifier',
            'id',
          ]) ??
          routeResolution.candidate.route_id ??
          routeResolution.candidate.identifier ??
          routeResolution.candidate.id;
        const toolOutput = await deps.runWorkerWithTools(
          reportEnv,
          'generate_route_report',
          applyEntityAliasHintToPrompt(
            buildStructuredReportPrefetchedPrompt({
              workerTool: 'generate_route_report',
              displayName: resolvedRouteName,
              entityId: resolvedRouteId,
              partition: requestedPartition ?? null,
              sourceData: routeResolution.data,
            }),
            aliasResolution
          ),
          options.isStream ?? false,
          deps.createScopedToolProvider(baseProvider, {}, new Set()),
          historyMessages,
          {
            ...sharedRuntimeOptions,
            prefetchedSourceData: routeResolution.data,
          }
        );
        return {
          ...toolOutput,
          sources: extractMessageSources(routeResolution.data),
          metadata: decorateRouteMetadata(
            {
              ...toolOutput.metadata,
              route_lookup: {
                ...deps.getStructuredLookupSummary('generate_route_report', routeResolution),
                alias: aliasResolution,
                partition: requestedPartition,
              },
              scenario: buildShortcutScenarioMeta(),
              rule_match: ruleMatchMeta,
            },
            'generate_route_report',
            selectedRuleId ?? null
          ),
        };
      }

      return runStructuredLookupClarification({
        userQuery: content,
        workerTool: 'generate_route_report',
        lookupReason: String(routeResolution.reason ?? 'not_found'),
        fallbackContent: deps.buildRouteLookupReply(routeResolution),
        metadata: {
          route_lookup: {
            ...deps.getStructuredLookupSummary('generate_route_report', routeResolution),
            partition: requestedPartition,
          },
          pending_further_info: buildPendingFurtherInfoFromLookup(
            'generate_route_report',
            routeResolution,
            {
              route_name: routeNameRaw,
              ...(requestedPartition ? { ppartition: requestedPartition } : {}),
            }
          ),
          scenario: buildShortcutScenarioMeta(),
          rule_match: ruleMatchMeta,
        },
        selectedRuleId: selectedRuleId ?? null,
      });
    };

    const handleStationReportResolution = async (
      stationNameRaw: string,
      requestedPartitionRaw?: string | null,
      selectedRuleId?: string | null
    ): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      const requestedPartition = String(requestedPartitionRaw ?? '').trim() || undefined;
      const baseProvider = deps.createToolProvider(env);
      const stationResolution = await deps.resolveStationLookup(
        env.DB,
        stationNameRaw,
        baseProvider,
        requestedPartition
      );
      if (stationResolution.kind === 'resolved') {
        const resolvedStationName =
          readFirstStringAtPaths(stationResolution.data, [
            'basic.station_name',
            'station_name',
            'name',
          ]) ??
          stationResolution.candidate.station_name ??
          stationResolution.candidate.name;
        const resolvedStationId =
          readFirstStringAtPaths(stationResolution.data, [
            'basic.station_id',
            'station_id',
            'identifier',
            'id',
          ]) ??
          stationResolution.candidate.station_id ??
          stationResolution.candidate.identifier ??
          stationResolution.candidate.id;
        const toolOutput = await deps.runWorkerWithTools(
          reportEnv,
          'generate_station_report',
          buildStructuredReportPrefetchedPrompt({
            workerTool: 'generate_station_report',
            displayName: resolvedStationName,
            entityId: resolvedStationId,
            partition: requestedPartition ?? null,
            sourceData: stationResolution.data,
          }),
          options.isStream ?? false,
          deps.createScopedToolProvider(baseProvider, {}, new Set()),
          historyMessages,
          {
            ...sharedRuntimeOptions,
            prefetchedSourceData: stationResolution.data,
          }
        );
        return {
          ...toolOutput,
          sources: extractMessageSources(stationResolution.data),
          metadata: decorateRouteMetadata(
            {
              ...toolOutput.metadata,
              station_lookup: {
                ...deps.getStructuredLookupSummary('generate_station_report', stationResolution),
                partition: requestedPartition,
              },
              scenario: buildShortcutScenarioMeta(),
              rule_match: ruleMatchMeta,
            },
            'generate_station_report',
            selectedRuleId ?? null
          ),
        };
      }

      return runStructuredLookupClarification({
        userQuery: content,
        workerTool: 'generate_station_report',
        lookupReason: String(stationResolution.reason ?? 'not_found'),
        fallbackContent: deps.buildStationLookupReply(stationResolution),
        metadata: {
          station_lookup: {
            ...deps.getStructuredLookupSummary('generate_station_report', stationResolution),
            partition: requestedPartition,
          },
          pending_further_info: buildPendingFurtherInfoFromLookup(
            'generate_station_report',
            stationResolution,
            {
              station_name: stationNameRaw,
              ...(requestedPartition ? { ppartition: requestedPartition } : {}),
            }
          ),
          scenario: buildShortcutScenarioMeta(),
          rule_match: ruleMatchMeta,
        },
        selectedRuleId: selectedRuleId ?? null,
      });
    };

    const handleIncidentReportResolution = async (
      driverNameRaw: string,
      accidentDateRaw?: string | null,
      selectedRuleId?: string | null
    ): Promise<{
      content: string | ReadableStream;
      metadata: Record<string, unknown>;
      sources?: Array<Record<string, unknown>>;
      leadingContent?: string;
      trailingContent?: string;
    }> => {
      const incidentLookupProvider = deps.createScopedToolProvider(
        deps.createToolProvider(env),
        {
          [ACCIDENT_INVESTIGATION_MCP_TOOL_NAME]: async (args) => {
            const driverNameArg = String(args.driverName ?? args.driver_name ?? '').trim();
            const partitionArg = String(args.accidentDate ?? args.accident_date ?? '').trim();
            if (!driverNameArg) {
              return { success: false, error: 'missing_driver_name' };
            }
            const result = await fetchAccidentInvestigationByDriverAndDateResult(
              env,
              driverNameArg,
              partitionArg
            );
            if (result.success === false) {
              return {
                success: false,
                error: result.error,
                ...(result.detail ? { detail: result.detail } : {}),
              };
            }
            return { success: true, data: result.data };
          },
        },
        new Set([ACCIDENT_INVESTIGATION_MCP_TOOL_NAME])
      );
      const partitionArg = accidentDateRaw ?? '';
      const incidentResolution = await deps.resolveIncidentLookup(
        env.DB,
        driverNameRaw,
        partitionArg,
        incidentLookupProvider
      );
      if (incidentResolution.kind === 'resolved') {
        const incidentLookupKey =
          String(
            incidentResolution.candidate.identifier ??
              incidentResolution.candidate.driver_name ??
              incidentResolution.candidate.id ??
              incidentResolution.candidate.name
          ).trim() || incidentResolution.candidate.name;
        const accidentData = incidentResolution.data;
        const toolOutput = await deps.runWorkerWithTools(
          reportEnv,
          'generate_accident_investigation_report',
          buildStructuredReportPrefetchedPrompt({
            workerTool: 'generate_accident_investigation_report',
            displayName: incidentResolution.candidate.name,
            entityId: incidentLookupKey,
            partition: partitionArg ?? null,
            sourceData: accidentData,
          }),
          options.isStream ?? false,
          deps.createScopedToolProvider(deps.createToolProvider(env), {}, new Set()),
          historyMessages,
          { ...sharedRuntimeOptions, prefetchedSourceData: accidentData }
        );
        return {
          ...toolOutput,
          sources: extractMessageSources(accidentData),
          metadata: decorateRouteMetadata(
            {
              ...toolOutput.metadata,
              incident_lookup: deps.getStructuredLookupSummary(
                'generate_accident_investigation_report',
                incidentResolution
              ),
              scenario: buildShortcutScenarioMeta(),
              rule_match: ruleMatchMeta,
            },
            'generate_accident_investigation_report',
            selectedRuleId ?? null
          ),
        };
      }

      return runStructuredLookupClarification({
        userQuery: content,
        workerTool: 'generate_accident_investigation_report',
        lookupReason: String(incidentResolution.reason ?? 'not_found'),
        fallbackContent: deps.buildIncidentLookupReply(incidentResolution),
        metadata: {
          incident_lookup: deps.getStructuredLookupSummary(
            'generate_accident_investigation_report',
            incidentResolution
          ),
          pending_further_info: buildPendingFurtherInfoFromLookup(
            'generate_accident_investigation_report',
            incidentResolution
          ),
          scenario: buildShortcutScenarioMeta(),
          rule_match: ruleMatchMeta,
        },
        selectedRuleId: selectedRuleId ?? null,
      });
    };

    if (!directToolCall && pendingFurtherInfo && looksLikePendingCancellation(content)) {
      return {
        content: '已取消上一轮待补充信息，本轮不会继续之前的任务。若有新需求，请直接告诉我。',
        metadata: decorateRouteMetadata(
          {
            scenario: scenarioMeta,
            rule_match: ruleMatchMeta,
            pending_further_info: pendingFurtherInfo,
            pending_further_info_decision: 'cancelled',
          },
          null
        ),
      };
    }

    /*
    if (typeof latestStructuredReportFailureSource === 'string' && false) {
      const reportLabelMap: Record<StructuredReportWorkerToolName, string> = {
        generate_driver_report: '驾驶员报告',
        generate_vehicle_report: '车辆报告',
        generate_route_report: '线路报告',
        generate_accident_investigation_report: '事故调查报告',
      };
      return {
        content: `上一轮${reportLabelMap[latestStructuredReportFailureSource]}未成功生成，当前没有可继续追问的报告内容。请先重新生成报告，或直接提供更具体的对象标识后再继续。`,
        metadata: decorateRouteMetadata(
          { scenario: scenarioMeta, rule_match: ruleMatchMeta },
          null
        ),
      };
    }

    if (typeof latestStructuredReportSource === 'string' && false) {
      return runConsultWorker({
        workerTool:
          latestStructuredReportSource === 'generate_vehicle_report'
            ? 'consult_vehicle_expert'
            : 'consult_omni',
        prompt: content,
        metadata: {
          report_follow_up: {
            kind: 'structured_report_follow_up',
            source_tool: latestStructuredReportSource,
          },
          scenario: {
            ...scenarioMeta,
            matched: true,
            shortcut: true,
            scenario_id: scenarioMatch.best?.scenario.id,
            scenario_name: scenarioMatch.best?.scenario.name,
            score: scenarioMatch.best?.score,
          },
          rule_match: ruleMatchMeta,
        },
      });
    }

    */
    if (
      directToolCall?.tool === 'generate_unit_report' &&
      (preRouterFleetUnitAlias || preRouterUnitAlias)
    ) {
      directToolCall = {
        ...directToolCall,
        args: {
          ...directToolCall.args,
          organ_name: (preRouterFleetUnitAlias ?? preRouterUnitAlias)?.standardName,
        },
      };
    } else if (directToolCall?.tool === 'generate_route_report' && preRouterRouteAlias) {
      directToolCall = {
        ...directToolCall,
        args: { ...directToolCall.args, route_name: preRouterRouteAlias.standardName },
      };
    }

    if (directToolCall) {
      if (directToolCall.tool === 'generate_vehicle_report') {
        directToolCall = {
          ...directToolCall,
          args: normalizeVehiclePlateArg(directToolCall.args, 'numberPlate'),
        };
      }
      const validation = deps.validateToolCall(directToolCall);
      if ('prompt' in validation) {
        if (validation.handling !== 'retry_router') {
          const prompt = validation.prompt;
          return {
            content: prompt,
            metadata: decorateRouteMetadata(
              {
                scenario: {
                  ...scenarioMeta,
                  matched: true,
                  shortcut: true,
                  scenario_id: scenarioMatch.best?.scenario.id,
                  scenario_name: scenarioMatch.best?.scenario.name,
                  score: scenarioMatch.best?.score,
                },
                rule_match: ruleMatchMeta,
              },
              structuredLookupTools.has(directToolCall.tool as StructuredLookupToolName)
                ? null
                : directToolCall.tool
            ),
          };
        }
      } else if (directToolCall.tool === 'generate_driver_report') {
        return handleDriverReportResolution(
          String(directToolCall.args.driver_name ?? ''),
          String(directToolCall.args.ppartition ?? directToolCall.args.partition ?? ''),
          null
        );
      } else if (directToolCall.tool === 'generate_vehicle_report') {
        return handleVehicleReportResolution(
          String(directToolCall.args.numberPlate ?? ''),
          String(directToolCall.args.ppartition ?? directToolCall.args.partition ?? ''),
          null
        );
      } else if (directToolCall.tool === 'generate_unit_report') {
        return handleUnitReportResolution(
          String(directToolCall.args.organ_name ?? ''),
          String(directToolCall.args.ppartition ?? directToolCall.args.partition ?? ''),
          null
        );
      } else if (directToolCall.tool === 'generate_route_report') {
        return handleRouteReportResolution(
          String(directToolCall.args.route_name ?? directToolCall.args.routeName ?? ''),
          String(directToolCall.args.ppartition ?? directToolCall.args.partition ?? ''),
          null
        );
      } else if (directToolCall.tool === 'generate_station_report') {
        return handleStationReportResolution(
          String(
            directToolCall.args.station_name ??
              directToolCall.args.stationName ??
              directToolCall.args.busStationName ??
              ''
          ),
          String(directToolCall.args.ppartition ?? directToolCall.args.partition ?? ''),
          null
        );
      } else if (directToolCall.tool === 'generate_accident_investigation_report') {
        return handleIncidentReportResolution(
          String(directToolCall.args.driver_name ?? directToolCall.args.driverName ?? ''),
          String(directToolCall.args.accident_date ?? directToolCall.args.accidentDate ?? '') ?? null
        );
      } else {
        const toolOutput = await deps.runWorkerWithTools(
          reportEnv,
          directToolCall.tool,
          buildWorkerPrompt(directToolCall),
          options.isStream ?? false,
          undefined,
          historyMessages,
          sharedRuntimeOptions
        );
        return {
          ...toolOutput,
          metadata: decorateRouteMetadata(
            {
              ...toolOutput.metadata,
              scenario: {
                ...scenarioMeta,
                matched: true,
                shortcut: true,
                scenario_id: scenarioMatch.best?.scenario.id,
                scenario_name: scenarioMatch.best?.scenario.name,
                score: scenarioMatch.best?.score,
              },
              rule_match: ruleMatchMeta,
            },
            directToolCall.tool
          ),
        };
      }
    }

    const contextMessages = buildContextFromHistory(historyMessages);
    const clarificationGuide =
      '\n\nCLARIFICATION TOOL:\n- If the current turn cannot continue because key information is missing or ambiguous, first write the exact user-facing clarification in the assistant message content for this turn.\n- Then call request_further_info only to persist resumable pending state.\n- Do not repeat the clarification text inside request_further_info args.\n- resume_tool must be the worker tool that should continue after the next user reply.\n- For report args use resume_mode=fill_args; for conversational carry-over you may use resume_mode=append_user_reply.';
    const pendingFurtherInfoGuide = pendingFurtherInfo
      ? `\n\n${renderPendingFurtherInfoPrompt(
          pendingFurtherInfo,
          latestRoutingContext?.assistantContent
        )}`
      : '';
    const latestStructuredReportGuide =
      latestStructuredReportSource ||
      latestStructuredReportFailureSource ||
      latestRoutingContext?.reportFollowUp
        ? `\n\n${renderLatestStructuredReportPrompt({
            latestStructuredReportSource,
            latestStructuredReportFailureSource,
            assistantContent: latestRoutingContext?.assistantContent,
            reportFollowUp: latestRoutingContext?.reportFollowUp ?? null,
          })}`
        : '';
    const basicDataIntentGuide = [
      '',
      '',
      'BASIC DATA INTENT ROUTING:',
      '- When the user says “基础数据”, “基础信息”, “运营基础数据”, “基础运营数据”, “档案”, or “台账”, treat the head intent as basic data / basic information.',
      '- In phrases like “运营基础数据” or “基础运营数据”, “运营” is a scope qualifier for bus-operation entities; it does not by itself request operational KPI fields.',
      '- Do not expand a basic-data request into unmentioned metrics such as 日均发班次数、日均客运量、日运营里程、平均速度、能耗、风险评分、管理效果, unless the user explicitly asks for those fields.',
      '- For basic data requests, preserve the user wording in the worker query. If forwarding to consult_omni, pass the original request or a minimal paraphrase; do not add example metrics that the user did not ask for.',
      '- If the user asks for a count/total together with basic data, route to consult_omni and let the worker answer only counts supported by total/count fields or explain that reliable totals are unavailable.',
    ].join('\n');
    const serverTimeGuide = buildServerTimeSystemPrompt();
    const routerMessages: ChatCompletionMessage[] = [
      {
        role: 'system',
        content: `${serverTimeGuide}

${deps.getRouterSkill()}${clarificationGuide}${pendingFurtherInfoGuide}${latestStructuredReportGuide}${basicDataIntentGuide}

${routerAliasGuide}

${ruleMatchPrompt}`,
      },
      ...contextMessages,
      { role: 'user', content },
    ];

    const routerToolAllowList = (
      ruleMatchContext.ok && ruleMatchContext.matches.length
        ? deps.getRouterToolAllowList()
        : deps.getRouterToolAllowList().filter((tool) => tool !== 'rule_reply')
    ) as readonly string[];

    let routerIterations = 0;
    while (routerIterations < deps.MAX_ROUTER_TOOL_ITERATIONS) {
      routerIterations += 1;
      let routerResult: {
        content?: string;
        toolCall?: {
          id: string;
          tool: string;
          args: Record<string, unknown>;
          displayMessage?: string;
        };
      };
      const useCommandRouter = Boolean(options.useCommandRouter && routerIterations === 1);
      let routerMode: 'command' | 'function' = 'function';
      if (useCommandRouter) {
        emitProbeStage('command_router_call_started', { iteration: routerIterations });
        const commandRouterMessages: ChatCompletionMessage[] = [
          {
            role: 'system',
            content: `${routerMessages[0]?.content ?? ''}

${buildCommandRouterInstruction(routerToolAllowList)}`,
          },
          ...contextMessages,
          { role: 'user', content },
        ];
        const commandContent = await deps.callOpenAICommandRouter(env, {
          model: env.OPENAI_ROUTER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
          temperature: ROUTER_TEMPERATURE,
          messages: commandRouterMessages,
          enableThinking: false,
        });
        const commandToolCall = parseCommandRouterToolCall(
          commandContent,
          routerToolAllowList,
          content
        );
        emitProbeStage('command_router_call_done', {
          iteration: routerIterations,
          selected_tool: commandToolCall?.tool ?? null,
          preview: commandContent.replace(/\s+/g, ' ').trim().slice(0, 180),
        });
        if (commandToolCall) {
          routerMode = 'command';
          routerResult = { content: commandContent, toolCall: commandToolCall };
        } else {
          emitProbeStage('command_router_fallback_to_function_router', {
            iteration: routerIterations,
          });
          emitProbeStage('router_call_started', {
            iteration: routerIterations,
            fallback_from: 'command_router',
          });
          routerResult = await deps.callOpenAIRouter(env, {
            model: env.OPENAI_ROUTER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
            temperature: ROUTER_TEMPERATURE,
            messages: routerMessages,
            toolAllowList: routerToolAllowList,
            enableThinking: false,
          });
        }
      } else {
        emitProbeStage('router_call_started', { iteration: routerIterations });
        routerResult = await deps.callOpenAIRouter(env, {
          model: env.OPENAI_ROUTER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
          temperature: ROUTER_TEMPERATURE,
          messages: routerMessages,
          toolAllowList: routerToolAllowList,
          enableThinking: false,
        });
      }

      const toolCall = routerResult.toolCall;
      emitProbeStage('router_call_done', {
        iteration: routerIterations,
        selected_tool: toolCall?.tool ?? null,
        router_mode: routerMode,
      });
      if (!toolCall) {
        return runConsultWorker({
          workerTool: 'consult_omni',
          prompt: applyEntityAliasHintToPrompt(
            content,
            preRouterFleetUnitAlias ?? preRouterUnitAlias ?? preRouterRouteAlias
          ),
          metadata: {
            scenario: scenarioMeta,
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            router_no_tool_fallback: true,
            entity_alias: preRouterFleetUnitAlias ?? preRouterUnitAlias ?? preRouterRouteAlias,
            ...(pendingFurtherInfo
              ? {
                  pending_further_info: pendingFurtherInfo,
                  pending_further_info_decision: 'ignored',
                }
              : {}),
          },
        });
      }

      routerToolUsages.push({
        id: toolCall.id,
        name: toolCall.tool,
        args: toolCall.args,
      });

      if (toolCall.tool === 'match_rules') {
        routerMessages.push({
          role: 'assistant',
          content: '',
          tool_calls: [
            {
              id: toolCall.id,
              tool: 'match_rules',
              args: toolCall.args,
            },
          ],
        });
        routerMessages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          name: 'match_rules',
          content: JSON.stringify(ruleMatchContext.toolResult, null, 2),
        });
        continue;
      }

      if (toolCall.tool === 'request_further_info') {
        const payload = buildPendingFurtherInfoToolPayload(toolCall.args);
        const furtherInfoDisplayContent =
          routerMode === 'command' ? toolCall.displayMessage : routerResult.content;
        if (!payload) {
          return {
            content: resolveFurtherInfoDisplayMessage(furtherInfoDisplayContent, toolCall.args),
            metadata: decorateRouteMetadata(
              {
                scenario: scenarioMeta,
                rule_match: ruleMatchMeta,
                router_tools: routerToolUsages,
                error: 'invalid_request_further_info_payload',
              },
              null
            ),
          };
        }
        return {
          content: resolveFurtherInfoDisplayMessage(furtherInfoDisplayContent, toolCall.args),
          metadata: decorateRouteMetadata(
            {
              scenario: scenarioMeta,
              rule_match: ruleMatchMeta,
              router_tools: routerToolUsages,
              pending_further_info: payload.pending_further_info,
              ...(pendingFurtherInfo ? { pending_further_info_previous: pendingFurtherInfo } : {}),
            },
            null
          ),
        };
      }

      if (!deps.isRoutableWorkerToolName(toolCall.tool)) {
        return {
          content: 'Blocked tool call.',
          metadata: decorateRouteMetadata(
            {
              scenario: scenarioMeta,
              blocked_tool: toolCall.tool,
              rule_match: ruleMatchMeta,
              router_tools: routerToolUsages,
            },
            toolCall.tool
          ),
        };
      }

      const nextArgs = { ...toolCall.args };
      if (toolCall.tool === 'generate_vehicle_report') {
        Object.assign(nextArgs, normalizeVehiclePlateArg(nextArgs, 'numberPlate'));
      }
      if (toolCall.tool === 'rule_reply' && !nextArgs.user_query) {
        nextArgs.user_query = content;
      }

      const selectedRuleId =
        toolCall.tool === 'rule_reply' ? deps.extractRuleIdFromRuleReplyArgs(nextArgs) : '';

      if (
        toolCall.tool === 'rule_reply' &&
        (!selectedRuleId || !matchedRuleIds.has(selectedRuleId))
      ) {
        routerMessages.push({
          role: 'assistant',
          content: '',
          tool_calls: [
            {
              id: toolCall.id,
              tool: toolCall.tool as any,
              args: nextArgs,
            },
          ],
        });
        routerMessages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          name: toolCall.tool,
          content: JSON.stringify(
            {
              success: false,
              error:
                'rule_reply requires a rule_id from the current turn match results. Choose another tool if no matched rule exists.',
            },
            null,
            2
          ),
        });
        continue;
      }

      if (
        toolCall.tool === 'rule_reply' &&
        blockedRuleId &&
        selectedRuleId &&
        selectedRuleId === blockedRuleId
      ) {
        routerMessages.push({
          role: 'assistant',
          content: '',
          tool_calls: [
            {
              id: toolCall.id,
              tool: 'rule_reply',
              args: nextArgs,
            },
          ],
        });
        routerMessages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          name: 'rule_reply',
          content: JSON.stringify(
            {
              success: false,
              error: `rule_reply for rule_id=${blockedRuleId} is blocked for this turn`,
            },
            null,
            2
          ),
        });
        continue;
      }

      const validation = deps.validateToolCall({
        tool: toolCall.tool as WorkerToolName,
        args: nextArgs,
      });
      if ('prompt' in validation) {
        if (validation.handling === 'retry_router') {
          routerMessages.push({
            role: 'assistant',
            content: '',
            tool_calls: [
              {
                id: toolCall.id,
                tool: toolCall.tool as any,
                args: nextArgs,
              },
            ],
          });
          routerMessages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            name: toolCall.tool,
            content: JSON.stringify(
              {
                success: false,
                error: validation.prompt,
              },
              null,
              2
            ),
          });
          continue;
        }
        const prompt = validation.prompt;
        return {
          content: prompt,
          metadata: decorateRouteMetadata(
            {
              scenario: scenarioMeta,
              rule_match: ruleMatchMeta,
              router_tools: routerToolUsages,
              pending_further_info: buildPendingFurtherInfoFromValidation({
                tool: toolCall.tool as WorkerToolName,
                args: nextArgs,
              }),
              ...(pendingFurtherInfo ? { pending_further_info_previous: pendingFurtherInfo } : {}),
            },
            structuredLookupTools.has(toolCall.tool as StructuredLookupToolName)
              ? null
              : toolCall.tool,
            selectedRuleId || null
          ),
        };
      }

      if (toolCall.tool === 'generate_driver_report') {
        return handleDriverReportResolution(
          String(nextArgs.driver_name ?? ''),
          String(nextArgs.ppartition ?? nextArgs.partition ?? ''),
          selectedRuleId || null
        );
      }

      if (toolCall.tool === 'generate_vehicle_report') {
        return handleVehicleReportResolution(
          String(nextArgs.numberPlate ?? ''),
          String(nextArgs.ppartition ?? nextArgs.partition ?? ''),
          selectedRuleId || null
        );
      }

      if (toolCall.tool === 'generate_unit_report') {
        return handleUnitReportResolution(
          String(nextArgs.organ_name ?? ''),
          String(nextArgs.ppartition ?? nextArgs.partition ?? ''),
          selectedRuleId || null
        );
      }

      if (toolCall.tool === 'generate_route_report') {
        return handleRouteReportResolution(
          String(nextArgs.route_name ?? nextArgs.routeName ?? ''),
          String(nextArgs.ppartition ?? nextArgs.partition ?? ''),
          selectedRuleId || null
        );
      }

      if (toolCall.tool === 'generate_station_report') {
        return handleStationReportResolution(
          String(nextArgs.station_name ?? nextArgs.stationName ?? nextArgs.busStationName ?? ''),
          String(nextArgs.ppartition ?? nextArgs.partition ?? ''),
          selectedRuleId || null
        );
      }

      if (toolCall.tool === 'generate_accident_investigation_report') {
        return handleIncidentReportResolution(
          String(nextArgs.driver_name ?? ''),
          String(nextArgs.accident_date ?? '') ?? null,
          selectedRuleId || null
        );
      }

      if (toolCall.tool === 'consult_omni') {
        const omniQuery = String(nextArgs.query ?? content);
        const aliasResolution =
          (await resolveFleetUnitAliasInText(env.DB, omniQuery)) ??
          (await resolveUnitAliasInText(env.DB, omniQuery)) ??
          (await resolveRouteAliasInText(env.DB, omniQuery));
        return runConsultWorker({
          workerTool: 'consult_omni',
          prompt: applyEntityAliasHintToPrompt(
            buildWorkerPrompt({ tool: 'consult_omni', args: nextArgs }),
            aliasResolution
          ),
          selectedRuleId: selectedRuleId || null,
          metadata: {
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: scenarioMatch.best?.scenario.id,
              scenario_name: scenarioMatch.best?.scenario.name,
              score: scenarioMatch.best?.score,
            },
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            entity_alias: aliasResolution,
          },
        });
      }

      if (toolCall.tool === 'consult_driver_expert') {
        const driverExpertCotMode = normalizeVehicleExpertCotMode(nextArgs.cot_mode);
        const driverExpertRuntimeOptions = deps.resolveWorkerRuntimeOptions?.(turnContext, {
          workerTool: 'consult_driver_expert',
          cotMode: driverExpertCotMode,
          historyMessages,
          userQuery: content,
        });
        return runConsultWorker({
          workerTool: 'consult_driver_expert',
          prompt: buildWorkerPrompt({ tool: 'consult_driver_expert', args: nextArgs }),
          selectedRuleId: selectedRuleId || null,
          runtimeOptions: driverExpertRuntimeOptions,
          metadata: {
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: scenarioMatch.best?.scenario.id,
              scenario_name: scenarioMatch.best?.scenario.name,
              score: scenarioMatch.best?.score,
            },
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            llm: {
              agent: 'driver_expert',
              cot_mode: driverExpertCotMode,
              cot_enabled: Boolean(driverExpertRuntimeOptions?.systemPromptPrefix),
            },
          },
        });
      }

      if (toolCall.tool === 'consult_vehicle_expert') {
        const vehicleExpertCotMode = normalizeVehicleExpertCotMode(nextArgs.cot_mode);
        const vehicleExpertRuntimeOptions = deps.resolveWorkerRuntimeOptions?.(turnContext, {
          workerTool: 'consult_vehicle_expert',
          cotMode: vehicleExpertCotMode,
          historyMessages,
          userQuery: content,
        });
        return runConsultWorker({
          workerTool: 'consult_vehicle_expert',
          prompt: buildWorkerPrompt({ tool: 'consult_vehicle_expert', args: nextArgs }),
          selectedRuleId: selectedRuleId || null,
          runtimeOptions: vehicleExpertRuntimeOptions,
          metadata: {
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: scenarioMatch.best?.scenario.id,
              scenario_name: scenarioMatch.best?.scenario.name,
              score: scenarioMatch.best?.score,
            },
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            llm: {
              agent: 'vehicle_expert',
              cot_mode: vehicleExpertCotMode,
              cot_enabled: Boolean(vehicleExpertRuntimeOptions?.systemPromptPrefix),
            },
          },
        });
      }

      if (toolCall.tool === 'consult_unit_expert') {
        const unitExpertCotMode = normalizeVehicleExpertCotMode(nextArgs.cot_mode);
        const unitQuery = String(nextArgs.query ?? content);
        const aliasResolution =
          (await resolveFleetUnitAliasInText(env.DB, unitQuery)) ??
          (await resolveUnitAliasInText(env.DB, unitQuery));
        const unitExpertRuntimeOptions = deps.resolveWorkerRuntimeOptions?.(turnContext, {
          workerTool: 'consult_unit_expert',
          cotMode: unitExpertCotMode,
          historyMessages,
          userQuery: content,
        });
        return runConsultWorker({
          workerTool: 'consult_unit_expert',
          prompt: applyEntityAliasHintToPrompt(
            buildWorkerPrompt({ tool: 'consult_unit_expert', args: nextArgs }),
            aliasResolution
          ),
          selectedRuleId: selectedRuleId || null,
          runtimeOptions: unitExpertRuntimeOptions,
          metadata: {
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: scenarioMatch.best?.scenario.id,
              scenario_name: scenarioMatch.best?.scenario.name,
              score: scenarioMatch.best?.score,
            },
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            unit_alias: aliasResolution,
            llm: {
              agent: 'unit_expert',
              cot_mode: unitExpertCotMode,
              cot_enabled: Boolean(unitExpertRuntimeOptions?.systemPromptPrefix),
            },
          },
        });
      }

      if (toolCall.tool === 'consult_route_expert') {
        const routeExpertCotMode = normalizeVehicleExpertCotMode(nextArgs.cot_mode);
        const routeQuery = String(nextArgs.query ?? content);
        const routeDirectionSource = [content, routeQuery]
          .map((value) => String(value ?? '').trim())
          .filter(Boolean)
          .join('\n');
        const routeDirectionConstraint = extractRouteDirectionConstraint(routeDirectionSource);
        const routeDirectionConstraintPrompt =
          buildRouteDirectionConstraintPrompt(routeDirectionConstraint);
        const aliasResolution = await resolveRouteAliasInText(
          env.DB,
          routeDirectionSource || routeQuery
        );
        const routeExpertRuntimeOptions = deps.resolveWorkerRuntimeOptions?.(turnContext, {
          workerTool: 'consult_route_expert',
          cotMode: routeExpertCotMode,
          historyMessages,
          userQuery: content,
        });
        const routeExpertPrompt = [
          routeDirectionConstraintPrompt,
          buildWorkerPrompt({ tool: 'consult_route_expert', args: nextArgs }),
        ]
          .filter(Boolean)
          .join('\n\n');
        return runConsultWorker({
          workerTool: 'consult_route_expert',
          prompt: applyEntityAliasHintToPrompt(
            routeExpertPrompt,
            aliasResolution
          ),
          selectedRuleId: selectedRuleId || null,
          toolProvider: createRouteExpertToolProvider(routeDirectionConstraint),
          runtimeOptions: routeExpertRuntimeOptions,
          metadata: {
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: scenarioMatch.best?.scenario.id,
              scenario_name: scenarioMatch.best?.scenario.name,
              score: scenarioMatch.best?.score,
            },
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            route_alias: aliasResolution,
            route_direction_constraint: routeDirectionConstraint,
            llm: {
              agent: 'route_expert',
              cot_mode: routeExpertCotMode,
              cot_enabled: Boolean(routeExpertRuntimeOptions?.systemPromptPrefix),
            },
          },
        });
      }

      if (toolCall.tool === 'consult_station_expert') {
        const stationExpertCotMode = normalizeVehicleExpertCotMode(nextArgs.cot_mode);
        const stationExpertRuntimeOptions = deps.resolveWorkerRuntimeOptions?.(turnContext, {
          workerTool: 'consult_station_expert',
          cotMode: stationExpertCotMode,
          historyMessages,
          userQuery: content,
        });
        return runConsultWorker({
          workerTool: 'consult_station_expert',
          prompt: buildWorkerPrompt({ tool: 'consult_station_expert', args: nextArgs }),
          selectedRuleId: selectedRuleId || null,
          runtimeOptions: stationExpertRuntimeOptions,
          metadata: {
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: scenarioMatch.best?.scenario.id,
              scenario_name: scenarioMatch.best?.scenario.name,
              score: scenarioMatch.best?.score,
            },
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            llm: {
              agent: 'station_expert',
              cot_mode: stationExpertCotMode,
              cot_enabled: Boolean(stationExpertRuntimeOptions?.systemPromptPrefix),
            },
          },
        });
      }

      if (toolCall.tool === 'consult_incident_expert') {
        const incidentExpertCotMode = normalizeVehicleExpertCotMode(nextArgs.cot_mode);
        const incidentExpertRuntimeOptions = deps.resolveWorkerRuntimeOptions?.(turnContext, {
          workerTool: 'consult_incident_expert',
          cotMode: incidentExpertCotMode,
          historyMessages,
          userQuery: content,
        });
        return runConsultWorker({
          workerTool: 'consult_incident_expert',
          prompt: buildWorkerPrompt({ tool: 'consult_incident_expert', args: nextArgs }),
          selectedRuleId: selectedRuleId || null,
          runtimeOptions: incidentExpertRuntimeOptions,
          metadata: {
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: scenarioMatch.best?.scenario.id,
              scenario_name: scenarioMatch.best?.scenario.name,
              score: scenarioMatch.best?.score,
            },
            rule_match: ruleMatchMeta,
            router_tools: routerToolUsages,
            llm: {
              agent: 'incident_expert',
              cot_mode: incidentExpertCotMode,
              cot_enabled: Boolean(incidentExpertRuntimeOptions?.systemPromptPrefix),
            },
          },
        });
      }

      const toolOutput = await deps.runWorkerWithTools(
        env,
        toolCall.tool as WorkerToolName,
        buildWorkerPrompt({ tool: toolCall.tool as WorkerToolName, args: nextArgs }),
        options.isStream ?? false,
        undefined,
        historyMessages,
        sharedRuntimeOptions
      );

      const isRuleReply = toolCall.tool === 'rule_reply';

      if (isRuleReply && toolOutput.metadata?.rule_exit) {
        ruleExitFallbackTriggered = true;
        if (selectedRuleId) {
          blockedRuleId = selectedRuleId;
        }

        routerMessages.push({
          role: 'assistant',
          content: '',
          tool_calls: [
            {
              id: toolCall.id,
              tool: 'rule_reply',
              args: nextArgs,
            },
          ],
        });
        routerMessages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          name: 'rule_reply',
          content: JSON.stringify(
            {
              success: false,
              error: 'rule_exit_triggered',
              data: {
                reason: toolOutput.metadata?.reason,
                confidence: toolOutput.metadata?.confidence,
                blocked_rule_id: blockedRuleId || null,
              },
            },
            null,
            2
          ),
        });

        if (blockedRuleId) {
          routerMessages.push({
            role: 'user',
            content: `[RULE_EXIT_GUARD] You must NOT call rule_reply with rule_id "${blockedRuleId}" again in this turn.`,
          });
        }
        continue;
      }

      const bestScenario = scenarioMatch.best;

      return {
        ...toolOutput,
        metadata: decorateRouteMetadata(
          {
            ...toolOutput.metadata,
            router_tools: routerToolUsages,
            scenario: {
              ...scenarioMeta,
              matched: true,
              scenario_id: bestScenario?.scenario.id,
              scenario_name: bestScenario?.scenario.name,
              score: bestScenario?.score,
            },
            rule_match: ruleMatchMeta,
          },
          toolCall.tool,
          selectedRuleId || null
        ),
      };
    }

    return {
      content: 'Router exceeded max tool iterations.',
      metadata: decorateRouteMetadata(
        {
          scenario: scenarioMeta,
          error: 'router_max_iterations',
          rule_match: ruleMatchMeta,
          router_tools: routerToolUsages,
        },
        null,
        null,
        ruleExitFallbackTriggered
      ),
    };
  }

  return { routeRequest };
}
