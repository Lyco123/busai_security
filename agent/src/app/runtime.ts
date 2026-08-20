import routerSkill from '../../skills/router/SKILL.md';
import driverSkill from '../../skills/structured/generate_driver_report/SKILL.md';
import vehicleSkill from '../../skills/structured/generate_vehicle_report/SKILL.md';
import unitSkill from '../../skills/structured/generate_unit_report/SKILL.md';
import routeSkill from '../../skills/structured/generate_route_report/SKILL.md';
import stationSkill from '../../skills/structured/generate_station_report/SKILL.md';
import accidentInvestigationSkill from '../../skills/structured/generate_accident_investigation_report/SKILL.md';
import omniSkill from '../../skills/conversational/omni/SKILL.md';
import driverExpertSkill from '../../skills/conversational/driver_expert/SKILL.md';
import vehicleExpertSkill from '../../skills/conversational/vehicle_expert/SKILL.md';
import unitExpertSkill from '../../skills/conversational/unit_expert/SKILL.md';
import routeExpertSkill from '../../skills/conversational/route_expert/SKILL.md';
import stationExpertSkill from '../../skills/conversational/station_expert/SKILL.md';
import incidentExpertSkill from '../../skills/conversational/incident_expert/SKILL.md';
import ruleAskerSkill from '../../skills/conversational/rule_asker/SKILL.md';
import ruleReplySkill from '../../skills/conversational/rule_reply/SKILL.md';
import ruleBuilderSkill from '../../skills/structured/rule_builder/SKILL.md';
import { createAbChatExperimentAdapter } from '../domains/ab-test/adapter';
import { createHttpRequestHandler } from './http-router';
import {
  buildDriverLookupReply as buildDriverLookupReplyModule,
  buildDriverLookupWorkerPrompt as buildDriverLookupWorkerPromptModule,
  buildIncidentLookupReply as buildIncidentLookupReplyModule,
  buildIncidentLookupWorkerPrompt as buildIncidentLookupWorkerPromptModule,
  buildRouteLookupReply as buildRouteLookupReplyModule,
  buildRouteLookupWorkerPrompt as buildRouteLookupWorkerPromptModule,
  buildStationLookupReply as buildStationLookupReplyModule,
  buildStationLookupWorkerPrompt as buildStationLookupWorkerPromptModule,
  buildUnitLookupReply as buildUnitLookupReplyModule,
  buildUnitLookupWorkerPrompt as buildUnitLookupWorkerPromptModule,
  buildVehicleLookupReply as buildVehicleLookupReplyModule,
  buildVehicleLookupWorkerPrompt as buildVehicleLookupWorkerPromptModule,
  extractStructuredReportToolCall as extractStructuredReportToolCallModule,
  getStructuredLookupSummary as getStructuredLookupSummaryModule,
  resolveDriverLookup as resolveDriverLookupModule,
  resolveIncidentLookup as resolveIncidentLookupModule,
  resolveRouteLookup as resolveRouteLookupModule,
  resolveStationLookup as resolveStationLookupModule,
  resolveUnitLookup as resolveUnitLookupModule,
  resolveVehicleLookup as resolveVehicleLookupModule,
} from '../domains/chat/structured-lookup';
import { buildPendingFurtherInfoToolPayload as buildPendingFurtherInfoToolPayloadModule } from '../domains/chat/clarification-state';
import type {
  ChatTurnContext,
  ResolveWorkerRuntimeOptionsParams,
} from '../domains/chat/turn-context';
import {
  buildStructuredReportFormatMismatchError,
  buildStructuredReportMissingDataPrompt,
  buildStructuredReportNoDataError,
  getStructuredManagementReportRuntimeConfig,
} from '../domains/chat/structured-report-runtime';
import { createChatService } from '../domains/chat/chat-service';
import { formatContextMessage } from '../domains/chat/context';
import { createRouteRequestHandler } from '../domains/chat/router-service';
import {
  ROUTER_SKILL_RUNTIME_SUPPLEMENT,
  renderRuleMatchForPrompt as renderRuleMatchForPromptModule,
} from '../domains/chat/router-prompts';
import {
  buildRouterTools,
  type RouterDispatchToolName,
  type RouterToolName,
} from '../domains/chat/router-tools';
import { validateToolCall as validateToolCallModule } from '../domains/chat/router-tool-validation';
import {
  DRIVER_EXPERT_COT_SYSTEM_PROMPT,
  VEHICLE_EXPERT_COT_SYSTEM_PROMPT,
} from '../domains/chat/vehicle-expert-prompts';
import {
  buildWorkerPrompt,
  createWorkerRunner,
  type WorkerRuntimeOptions,
} from '../domains/chat/worker-runner';
import { buildExpertRuntimeContext } from '../domains/experts/context-builder';
import { getExpertRegistryItemByWorkerTool } from '../domains/experts/registry';
import {
  normalizeIssuePriority,
  normalizeIssueSeverity,
  normalizeIssueStatus,
  parsePagination,
  parseResearchFilters,
} from '../domains/research/filters';
import {
  createEvalRecord,
  createIssueRecord,
  ensureIssueTypeByName,
  getEvalRecordById,
  getIssueRecordById,
  getResearchOptions,
  getResearchOverview,
  listIssueEventsByIssueId,
  listIssueTypes,
  listResearchEvals,
  listResearchIssues,
  mergeIssueTypes,
  resolveResearchFilterIssueTypes,
  updateEvalRecord,
  updateIssueRecord,
  updateIssueTypeRecord,
} from '../domains/research/service';
import {
  detectRuleConflict as detectRuleConflictService,
  executeMatchRules as executeMatchRulesService,
} from '../domains/rules/match-service';
import {
  executeRuleTest as executeRuleTestService,
  normalizeExamples,
} from '../domains/rules/rule-test-service';
import { createRuleToolAdapter } from '../domains/rules/tool-adapter';
import { createRuleDraftRepository } from '../domains/rules/rule-config/draft-repository';
import { createRuleConfigService } from '../domains/rules/rule-config/service';
import type {
  LegacyRuleDraftStatus,
  RuleConfigState,
  RuleDraftMode,
} from '../domains/rules/rule-config/types';
import { listWorkScenarios } from '../domains/scenarios/repository';
import { matchWorkScenario as matchWorkScenarioService } from '../domains/scenarios/match-service';
import { createSessionRepository } from '../domains/sessions/repository';
import {
  getLatestAssistantRoutingContext,
  getLatestStructuredReportFailureSource,
  getLatestStructuredReportSource,
} from '../domains/sessions/routing-context';
import { createSessionTitleService } from '../domains/sessions/title-service';
import { executeQueryKb, type QueryKbArgs } from '../infra/kb-query-tool';
import {
  callOpenAI,
  callOpenAIRouter as callOpenAIRouterBase,
  callOpenAIStream,
  callOpenAIStreamWithTools,
  callOpenAIWithToolsStream as callOpenAIWithToolsStreamBase,
  callOpenAIWithTools as callOpenAIWithToolsBase,
} from '../infra/llm/chat-completions';
import { processOpenAIStream } from '../infra/llm/stream';
import { callOpenAIEmbedding } from '../infra/llm/openai-client';
import { getToolDescription } from '../shared/errors';
import { isRecord } from '../shared/guards';
import { safeJsonParse } from '../shared/json';
import { callMcpToolForAgent, listMcpToolsForAgent } from '../shared/mcp';
import { collapseWhitespace, truncateText } from '../shared/text';
import {
  ScopedToolProvider,
  createToolProvider as createToolProviderBase,
  type ToolDefinition,
  type ToolProvider,
  type ToolResult,
} from '../tools/provider';

type AgentRole = 'user' | 'assistant' | 'system' | 'tool';

type WorkerToolName =
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
type DataToolName =
  | 'get_rule'
  | 'update_rule_draft'
  | 'get_rule_draft'
  | 'submit_rule_turn'
  | 'rule_exit'
  | 'request_further_info';
type ToolName = WorkerToolName | DataToolName | 'match_rules';

interface AgentMessage {
  id: string;
  role: AgentRole;
  content: string;
  createdAt: string;
  status?: 'complete' | 'error';
  sources?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

interface Env {
  DB: D1Database;
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  OPENAI_ROUTER_MODEL?: string;
  OPENAI_WORKER_MODEL?: string;
  OPENAI_LOCAL_BASE_URL?: string;
  OPENAI_LOCAL_MODEL?: string;
  OPENAI_LOCAL_REPORT_BASE_URL?: string;
  OPENAI_LOCAL_REPORT_MODEL?: string;
  OPENAI_REPORT_URL?: string;
  OPENAI_REPORT_BASE_URL?: string;
  OPENAI_REPORT_API_KEY?: string;
  OPENAI_REPORT_MODEL?: string;
  OPENAI_EMBEDDING_MODEL?: string;
  EMBEDDING_MODEL?: string;
  OPENAI_TITLE_MODEL?: string;
  OPENAI_STREAM_DIAGNOSTICS?: string;
  CORS_ALLOWED_ORIGINS?: string;
  KB_API_BASE_URL?: string;
  KB_API_TIMEOUT_MS?: string;
  KB_DEFAULT_ID?: string;
  KB_TOOL_ENABLED?: string;
  KB_TENANT_ID?: string;
  RULE_CONFIG_STATE_MACHINE_V2?: string;
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
}

type D1Database = {
  prepare: (query: string) => D1PreparedStatement;
  batch: (statements: D1PreparedStatement[]) => Promise<unknown>;
};

type D1PreparedStatement = {
  bind: (...values: unknown[]) => D1PreparedStatement;
  first: <T = Record<string, unknown>>() => Promise<T | null>;
  all: <T = Record<string, unknown>>() => Promise<{ results: T[] }>;
  run: () => Promise<unknown>;
};

type WorkerExecutionContext = {
  waitUntil: (promise: Promise<unknown>) => void;
};

interface WorkScenario {
  id: string;
  name: string;
  description: string;
  keywords?: string[];
  embedding?: number[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

type ScenarioMatchMethod = 'vector' | 'none';

interface ScenarioMatchCandidate {
  scenario: WorkScenario;
  score: number;
  method: ScenarioMatchMethod;
}

interface ScenarioMatchResult {
  matched: boolean;
  method: ScenarioMatchMethod;
  best?: ScenarioMatchCandidate;
  candidates: ScenarioMatchCandidate[];
  reason?: string;
}

interface RuleMatchItem {
  rule_id?: string;
  rule_name?: string;
  score?: number;
  metadata?: { match_text?: string; tone?: string };
}

interface RuleMatchContext {
  ok: boolean;
  matches: RuleMatchItem[];
  toolResult: ToolResult;
  queryEmbedding?: number[];
  error?: string;
}

const WORKER_SKILLS: Record<WorkerToolName, string> = {
  generate_driver_report: driverSkill,
  generate_vehicle_report: vehicleSkill,
  generate_unit_report: unitSkill,
  generate_route_report: routeSkill,
  generate_station_report: stationSkill,
  generate_accident_investigation_report: accidentInvestigationSkill,
  consult_omni: omniSkill,
  consult_driver_expert: driverExpertSkill,
  consult_vehicle_expert: vehicleExpertSkill,
  consult_unit_expert: unitExpertSkill,
  consult_route_expert: routeExpertSkill,
  consult_station_expert: stationExpertSkill,
  consult_incident_expert: incidentExpertSkill,
  rule_reply: ruleReplySkill,
  rule_asker: ruleAskerSkill,
  rule_builder: ruleBuilderSkill,
};

const ROUTER_SKILL = routerSkill;
const DEFAULT_MODEL = 'gpt-4o-mini';
const CONTEXT_WINDOW_MESSAGES = 30;
const LOW_RISK_BUILDER_FIELDS = [
  'examples',
  'template',
  'safe_defaults',
  'key_points',
  'required_info',
] as const;
const TOOL_SUMMARY_LIMIT = 6;
const TOOL_OUTPUT_PREVIEW_CHARS = 220;
const MESSAGE_PREVIEW_CHARS = 600;
const DEFAULT_SESSION_TITLE = '新会话';
const TITLE_MAX_CN_CHARS = 12;
const TITLE_MAX_EN_WORDS = 6;
const TITLE_SOURCE_USER_MESSAGES = 2;
const TITLE_SOURCE_MAX_CHARS = 320;
const DEFAULT_EMBEDDING_MODEL = 'text-embedding-v1';
const SCENARIO_MATCH_TOP_K = 6;
const SCENARIO_LIST_LIMIT = 200;
const RULE_MATCH_TOP_K = 5;
const RULE_MATCH_MIN_SCORE = 0.3;
const RULE_MATCH_THRESHOLD = 0.7;
const ROUTER_TOOL_ALLOW_LIST_BASE: RouterDispatchToolName[] = [
  'generate_driver_report',
  'generate_vehicle_report',
  'generate_unit_report',
  'generate_route_report',
  'generate_station_report',
  'generate_accident_investigation_report',
  'consult_omni',
  'consult_driver_expert',
  'consult_vehicle_expert',
  'consult_unit_expert',
  'consult_route_expert',
  'consult_station_expert',
  'consult_incident_expert',
  'rule_reply',
  'request_further_info',
];
const ROUTER_TOOL_ALLOW_LIST = [...ROUTER_TOOL_ALLOW_LIST_BASE] as const;
const STRUCTURED_REPORT_WORKER_TOOLS = new Set<WorkerToolName>([
  'generate_driver_report',
  'generate_vehicle_report',
  'generate_unit_report',
  'generate_route_report',
  'generate_station_report',
  'generate_accident_investigation_report',
]);

const MAX_TOOL_ITERATIONS = 5; // Worker 最大调用工具的次数
const MAX_ROUTER_TOOL_ITERATIONS = 3;

// ============================================
// ============================================

/**
 * 工具定义格式，兼容 OpenAI Function Calling 和 MCP
 */
function createToolProvider(env: Env): ToolProvider {
  return createToolProviderBase({
    env,
    executors: {
      executeGetRule: (db, args) => ruleToolAdapter.executeGetRule(db as D1Database, args),
      executeGetRuleDraft: (db, args) =>
        ruleToolAdapter.executeGetRuleDraft(db as D1Database, args),
      executeUpdateRuleDraft: (db, args) =>
        ruleToolAdapter.executeUpdateRuleDraft(
          db as D1Database,
          args as {
            session_id: string;
            status: RuleConfigState | LegacyRuleDraftStatus;
            mode: RuleDraftMode;
            rule_id?: string | null;
            draft: Record<string, unknown>;
          }
        ),
      executeSubmitRuleTurn: (db, args) =>
        ruleToolAdapter.executeSubmitRuleTurn(db as D1Database, args),
      executeQueryKb: (providerEnv, args) =>
        executeQueryKb(providerEnv as Env, args as unknown as QueryKbArgs),
      buildPendingFurtherInfoToolPayload: buildPendingFurtherInfoToolPayloadModule,
    },
    mcpClient: {
      listTools: listMcpToolsForAgent,
      callTool: callMcpToolForAgent,
    },
  });
}

function createScopedToolProvider(
  baseProvider: ToolProvider,
  tools: Record<string, (args: Record<string, unknown>) => Promise<ToolResult> | ToolResult>,
  allowList?: Set<string>,
  toolDefinitions: Record<string, ToolDefinition> = {}
): ToolProvider {
  return new ScopedToolProvider(baseProvider, tools, allowList, toolDefinitions);
}

// Scenario repository functions are provided by ../domains/scenarios/repository

// ============================================
// Rules & Drafts
// ============================================

function isRuleConfigStateMachineV2Enabled(env: Env): boolean {
  return (
    String(env.RULE_CONFIG_STATE_MACHINE_V2 ?? 'true')
      .trim()
      .toLowerCase() !== 'false'
  );
}

function executeRuleTest(
  env: Env,
  ruleId: string,
  payload?: {
    queries?: string[];
    top_k?: number;
    min_score?: number;
    preview_reply?: boolean;
  }
): Promise<ToolResult> {
  return executeRuleTestService(
    env,
    ruleId,
    {
      createToolProvider,
      createScopedToolProvider,
      async runWorkerWithTools(env, tool, prompt, stream, toolProvider) {
        const result = await runWorkerWithTools(env, tool, prompt, stream, toolProvider);
        return {
          content: typeof result.content === 'string' ? result.content : undefined,
        };
      },
      ruleMatchThreshold: RULE_MATCH_THRESHOLD,
    },
    payload
  );
}

// ============================================
// ============================================

function extractRuleIdFromRuleReplyArgs(args: Record<string, unknown>): string {
  const direct = typeof args.rule_id === 'string' ? args.rule_id.trim() : '';
  if (direct) return direct;
  const hitRules = args.hit_rules;
  if (!Array.isArray(hitRules) || !hitRules.length) return '';
  const first = hitRules[0];
  if (!first || typeof first !== 'object' || Array.isArray(first)) return '';
  const fromHitValue = (first as Record<string, unknown>).rule_id;
  const fromHit = typeof fromHitValue === 'string' ? fromHitValue : '';
  return fromHit.trim();
}

async function precomputeRuleMatchContext(env: Env, query: string): Promise<RuleMatchContext> {
  let toolResult: ToolResult;
  let queryEmbedding: number[] | undefined;
  try {
    toolResult = await executeMatchRulesService(
      env,
      {
        query,
        top_k: RULE_MATCH_TOP_K,
        min_score: RULE_MATCH_MIN_SCORE,
      },
      {
        onQueryEmbedding(embedding) {
          queryEmbedding = embedding;
        },
      }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn('Rule match failed, fallback to router:', error);
    return {
      ok: false,
      matches: [],
      toolResult: { success: false, error: message || 'match_rules_failed' },
      error: message || 'match_rules_failed',
    };
  }

  if (!toolResult.success || !toolResult.data || typeof toolResult.data !== 'object') {
    return {
      ok: false,
      matches: [],
      toolResult,
      error: toolResult.error || 'match_rules_failed',
    };
  }

  const matches = (toolResult.data as { matches?: RuleMatchItem[] }).matches;
  return {
    ok: true,
    matches: Array.isArray(matches) ? matches : [],
    toolResult,
    queryEmbedding,
  };
}

/**
 * 灏?ToolDefinition 杞崲涓?OpenAI Function Calling 格式
 */
function toOpenAIToolSchema(tool: ToolDefinition): { type: 'function'; function: ToolDefinition } {
  return {
    type: 'function',
    function: tool,
  };
}

// ============================================
// ============================================

const { runWorkerWithTools, generatePreRouterOpening } = createWorkerRunner({
  DEFAULT_MODEL,
  MAX_TOOL_ITERATIONS,
  WORKER_SKILLS,
  STRUCTURED_REPORT_WORKER_TOOLS,
  createToolProvider,
  getStructuredManagementReportRuntimeConfig,
  toOpenAIToolSchema,
  callOpenAI,
  async callOpenAIStreamText(env, options) {
    const stream = await callOpenAIStream(env, options);
    return processOpenAIStream(stream, () => {});
  },
  callOpenAIWithTools(env, options) {
    return callOpenAIWithToolsBase<ToolName>(env, {
      ...options,
      tools: options.tools as Array<{
        type: 'function';
        function: ToolDefinition & { name: ToolName };
      }>,
      createToolCallId: createId,
    });
  },
  callOpenAIWithToolsStream(env, options) {
    return callOpenAIWithToolsStreamBase<ToolName>(env, {
      ...options,
      tools: options.tools as Array<{
        type: 'function';
        function: ToolDefinition & { name: ToolName };
      }>,
      createToolCallId: createId,
    });
  },
  callOpenAIStreamWithTools,
  safeJsonParse,
  isRecord,
  buildStructuredReportNoDataError,
  buildStructuredReportFormatMismatchError,
  buildStructuredReportMissingDataPrompt,
});

function resolveWorkerRuntimeOptions(
  turnContext: ChatTurnContext,
  params: ResolveWorkerRuntimeOptionsParams
): WorkerRuntimeOptions | undefined {
  if (
    params.workerTool === 'consult_driver_expert' ||
    params.workerTool === 'consult_vehicle_expert'
  ) {
    return chatExperimentAdapter.resolveWorkerRuntimeOptions?.(turnContext, params);
  }

  const registryItem = getExpertRegistryItemByWorkerTool(params.workerTool);
  if (
    params.cotMode === 'deep' &&
    registryItem?.supportsDeepCot &&
    registryItem.deepCotSystemPrompt
  ) {
    return {
      systemPromptPrefix: registryItem.deepCotSystemPrompt,
    };
  }
  return undefined;
}

async function runWorkerWithExpertContext(
  env: Env,
  workerTool: WorkerToolName,
  userQuery: string,
  isStream = false,
  toolProvider?: ToolProvider,
  historyMessages?: Array<{ role: string; content: string }>,
  runtimeOptions?: WorkerRuntimeOptions
): Promise<{
  content: string | ReadableStream;
  metadata?: Record<string, unknown>;
  sources?: Array<Record<string, unknown>>;
  leadingContent?: string;
  trailingContent?: string;
}> {
  const nextRuntimeOptions = await buildExpertRuntimeContext(env, {
    workerTool,
    userQuery,
    historyMessages,
    baseRuntimeOptions: runtimeOptions,
  });

  return runWorkerWithTools(
    env,
    workerTool,
    userQuery,
    isStream,
    toolProvider,
    historyMessages,
    nextRuntimeOptions
  );
}

const chatExperimentAdapter = createAbChatExperimentAdapter({
  vehicleExpertCotSystemPrompt: VEHICLE_EXPERT_COT_SYSTEM_PROMPT,
  driverExpertCotSystemPrompt: DRIVER_EXPERT_COT_SYSTEM_PROMPT,
});

const sessionRepository = createSessionRepository({ createId });
const {
  listAgentSessions,
  getAgentSession,
  getAgentSessionMeta,
  createAgentSession,
  deleteAgentSession,
  saveMessage,
  updateSessionPreview,
  updateSessionTitle,
  getSessionMessageCounts,
  listUserMessagesForTitle,
} = sessionRepository;

const { sanitizeGeneratedTitle, maybeGenerateSessionTitle, scheduleSessionTitleGeneration } =
  createSessionTitleService({
    DEFAULT_MODEL,
    DEFAULT_SESSION_TITLE,
    TITLE_MAX_CN_CHARS,
    TITLE_MAX_EN_WORDS,
    TITLE_SOURCE_USER_MESSAGES,
    TITLE_SOURCE_MAX_CHARS,
    getAgentSessionMeta,
    getSessionMessageCounts,
    listUserMessagesForTitle,
    updateSessionTitle,
  });

const { routeRequest } = createRouteRequestHandler({
  DEFAULT_MODEL,
  MAX_ROUTER_TOOL_ITERATIONS,
  getRouterSkill() {
    return `${ROUTER_SKILL}\n\n${ROUTER_SKILL_RUNTIME_SUPPLEMENT}`;
  },
  getRouterToolAllowList() {
    return ROUTER_TOOL_ALLOW_LIST;
  },
  precomputeRuleMatchContext,
  renderRuleMatchForPrompt(ruleMatch, routingMode, skipRuleId) {
    return renderRuleMatchForPromptModule(ruleMatch, routingMode, skipRuleId, RULE_MATCH_THRESHOLD);
  },
  decorateRouteMetadata: chatExperimentAdapter.decorateRouteMetadata,
  listWorkScenarios,
  matchWorkScenarioService,
  extractDirectStructuredToolCall: extractStructuredReportToolCallModule,
  resolveDriverLookup: resolveDriverLookupModule,
  resolveVehicleLookup: resolveVehicleLookupModule,
  resolveUnitLookup: resolveUnitLookupModule,
  resolveRouteLookup: resolveRouteLookupModule,
  resolveStationLookup: resolveStationLookupModule,
  resolveIncidentLookup: resolveIncidentLookupModule,
  runWorkerWithTools: runWorkerWithExpertContext,
  createToolProvider,
  createScopedToolProvider,
  resolveWorkerRuntimeOptions,
  getLatestAssistantRoutingContext,
  getLatestStructuredReportSource,
  getLatestStructuredReportFailureSource,
  validateToolCall(toolCall) {
    return validateToolCallModule(toolCall, extractRuleIdFromRuleReplyArgs);
  },
  callOpenAIRouter(env, options) {
    return callOpenAIRouterBase(env, {
      ...options,
      tools: buildRouterTools(options.toolAllowList),
      isRouterToolName,
      createToolCallId: createId,
    });
  },
  callOpenAICommandRouter(env, options) {
    return callOpenAI(env, options);
  },
  isRoutableWorkerToolName,
  extractRuleIdFromRuleReplyArgs,
  buildDriverLookupReply: buildDriverLookupReplyModule,
  buildVehicleLookupReply: buildVehicleLookupReplyModule,
  buildUnitLookupReply: buildUnitLookupReplyModule,
  buildRouteLookupReply: buildRouteLookupReplyModule,
  buildStationLookupReply: buildStationLookupReplyModule,
  buildIncidentLookupReply: buildIncidentLookupReplyModule,
  buildDriverLookupWorkerPrompt: buildDriverLookupWorkerPromptModule,
  buildVehicleLookupWorkerPrompt: buildVehicleLookupWorkerPromptModule,
  buildUnitLookupWorkerPrompt: buildUnitLookupWorkerPromptModule,
  buildRouteLookupWorkerPrompt: buildRouteLookupWorkerPromptModule,
  buildStationLookupWorkerPrompt: buildStationLookupWorkerPromptModule,
  buildIncidentLookupWorkerPrompt: buildIncidentLookupWorkerPromptModule,
  getStructuredLookupSummary: getStructuredLookupSummaryModule,
});

const ruleDraftRepository = createRuleDraftRepository(createId);
const { clearRuleDraft, getRuleDraft, upsertRuleDraft } = ruleDraftRepository;
const ruleToolAdapter = createRuleToolAdapter({ createId, getRuleDraft, upsertRuleDraft });

const ruleConfigService = createRuleConfigService({
  DEFAULT_MODEL,
  LOW_RISK_BUILDER_FIELDS,
  RULE_MATCH_THRESHOLD,
  MAX_TOOL_ITERATIONS,
  createId,
  normalizeExamples,
  createAgentSession,
  getAgentSession,
  getRuleDraft,
  upsertRuleDraft,
  clearRuleDraft,
  isRuleConfigStateMachineV2Enabled,
  createToolProvider,
  createScopedToolProvider,
  toOpenAIToolSchema,
  runWorkerWithTools,
});

const {
  handleChat,
  handleChatStream,
  handleDirectStreamProbe,
  handlePipelineStreamProbe,
  handleReportSummary,
} = createChatService({
  TOOL_OUTPUT_PREVIEW_CHARS,
  createId,
  async getHistoryMessages(db, sessionId) {
    const session = await getAgentSession(db, sessionId);
    if (!session?.messages?.length) {
      return [];
    }
    return session.messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map((message) =>
        formatContextMessage(
          {
            role: message.role,
            content: String(message.content || ''),
          },
          message.metadata,
          {
            toolOutputPreviewChars: TOOL_OUTPUT_PREVIEW_CHARS,
            messagePreviewChars: MESSAGE_PREVIEW_CHARS,
          }
        )
      )
      .filter((message): message is { role: 'user' | 'assistant'; content: string } =>
        Boolean(message)
      );
  },
  saveMessage,
  updateSessionPreview,
  createTurnContext: chatExperimentAdapter.createTurnContext,
  tryHandleRuleConfig: ruleConfigService.tryHandleRuleConfig,
  routeRequest,
  generatePreRouterOpening,
  decorateAssistantMetadata: chatExperimentAdapter.decorateAssistantMetadata,
  hasDecoratedAssistantMetadata: chatExperimentAdapter.hasDecoratedAssistantMetadata,
  maybeGenerateSessionTitle,
  scheduleSessionTitleGeneration,
  async openDirectProbeStream(env, content) {
    return callOpenAIStream(env, {
      model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || DEFAULT_MODEL,
      temperature: 0.2,
      messages: [{ role: 'user', content }],
    });
  },
});

const { handleRequest } = createHttpRequestHandler({
  createId,
  defaultSessionTitle: DEFAULT_SESSION_TITLE,
  ruleConfigService,
  normalizeExamples,
  executeRuleTest,
  parseResearchFilters,
  resolveResearchFilterIssueTypes,
  parsePagination,
  listIssueTypes,
  ensureIssueTypeByName,
  updateIssueTypeRecord,
  mergeIssueTypes,
  getResearchOptions,
  getResearchOverview,
  listResearchEvals,
  createEvalRecord,
  getEvalRecordById,
  normalizeIssueSeverity,
  normalizeIssuePriority,
  normalizeIssueStatus,
  updateEvalRecord,
  listResearchIssues,
  createIssueRecord,
  getIssueRecordById,
  listIssueEventsByIssueId,
  updateIssueRecord,
  listAgentSessions,
  createAgentSession,
  getAgentSession,
  getAgentSessionMeta,
  sanitizeGeneratedTitle,
  updateSessionTitle,
  deleteAgentSession,
  handleChatStream,
  handleDirectStreamProbe,
  handlePipelineStreamProbe,
  handleChat,
  handleReportSummary,
});

export default {
  fetch(request: Request, env: Env, ctx?: WorkerExecutionContext): Promise<Response> {
    return handleRequest(request, env, ctx);
  },
};

// ============================================
// ============================================

// ============================================
// ============================================

function isRoutableWorkerToolName(value: string): value is RouterDispatchToolName {
  return (
    value === 'generate_driver_report' ||
    value === 'generate_vehicle_report' ||
    value === 'generate_unit_report' ||
    value === 'generate_route_report' ||
    value === 'generate_station_report' ||
    value === 'generate_accident_investigation_report' ||
    value === 'consult_omni' ||
    value === 'consult_driver_expert' ||
    value === 'consult_vehicle_expert' ||
    value === 'consult_unit_expert' ||
    value === 'consult_route_expert' ||
    value === 'consult_station_expert' ||
    value === 'consult_incident_expert' ||
    value === 'rule_reply' ||
    value === 'request_further_info'
  );
}

function isRouterToolName(value: string): value is RouterToolName {
  return value === 'match_rules' || isRoutableWorkerToolName(value);
}

// ============================================
// ============================================

function createId(prefix: string): string {
  return `${prefix}_${crypto.randomUUID()}`;
}
