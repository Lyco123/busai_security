import { isRecord } from '../../shared/guards';
import { safeJsonParse } from '../../shared/json';
import { getNestedValue } from '../../shared/object-path';
import {
  buildMcpDataSource,
  mergeMessageSources,
  withMessageSources,
  type MessageSource,
} from '../../shared/message-sources';
import { adaptDriverProfileToolResult } from '../../shared/driver-profile-mcp';
import { adaptVehicleProfileToolResult } from '../../shared/vehicle-profile-mcp';
import {
  isMissingGuangdongVehiclePlateSeries,
  normalizeGuangdongVehiclePlate,
} from '../../shared/vehicle-plate-normalizer';
import { getStandardRouteName, getStandardUnitName } from '../../shared/entity-alias-resolver';
import { adaptUnitProfileToolResult } from '../../shared/unit-profile-mcp';
import { adaptRouteProfileToolResult } from '../../shared/route-profile-mcp';
import { adaptStationProfileToolResult } from '../../shared/station-profile-mcp';
import { getStructuredReportDataSourceConfig } from './structured-report-data-sources';
import { readFirstStringAtPaths } from './structured-report-normalizers';
import type { ToolProvider, ToolResult, WorkerToolCall } from './worker-runner';
import {
  DRIVER_PROFILE_MCP_TOOL_NAME,
  ROUTE_PROFILE_MCP_TOOL_NAME,
  STATION_PROFILE_MCP_TOOL_NAME,
  UNIT_PROFILE_MCP_TOOL_NAME,
  VEHICLE_PROFILE_MCP_TOOL_NAME,
} from './structured-report-data-sources';
import {
  ACCIDENT_INVESTIGATION_MCP_TOOL_NAME,
  getDefaultAccidentPartition,
} from '../../shared/accident-investigation-mcp';

const VEHICLE_SUGGESTION_MCP_TOOL_NAME = 'get_mcp_suggest_absBusSuggestedSub_queryByBusNameAndDate';
const VEHICLE_RISK_SCORE_MCP_TOOL_NAME = 'get_mcp_base_absBusProfileMain_busRiskScore';
const DRIVER_SUGGESTION_MCP_TOOL_NAME =
  'get_mcp_suggest_absDriverSuggestedSub_queryByDriverNameAndDate';
const DRIVER_TREND_MCP_TOOL_NAME = 'get_mcp_base_absDriverProfileMain_quotaScoreTrend';
const DRIVER_RISK_SCORE_MCP_TOOL_NAME = 'get_mcp_base_absDriverProfileMain_driverRiskScore';
const ROUTE_SUGGESTION_MCP_TOOL_NAME =
  'get_mcp_suggest_absRouteSuggestedSub_queryByRouteNameAndDate';
const ROUTE_RISK_SCORE_MCP_TOOL_NAME = 'get_mcp_base_absRouteProfileMain_routeRiskScore';
const STATION_SUGGESTION_MCP_TOOL_NAME =
  'get_mcp_suggest_absBusStationSuggestedSub_queryByBusStationNameAndDate';
const STATION_RISK_SCORE_MCP_TOOL_NAME = 'get_mcp_base_absBusStationProfileMain_stationRiskScore';
const UNIT_SUGGESTION_MCP_TOOL_NAME =
  'get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate';
const UNIT_TREND_MCP_TOOL_NAME = 'get_mcp_base_absCompanyProfileMain_quotaScoreTrend';
const UNIT_KEY_RISK_MCP_TOOL_NAME = 'get_mcp_base_absCompanyProfileMain_getKeyRisk';

function mergeSuccessfulMcpDataSources(
  items: Array<{
    tool: string;
    args: Record<string, unknown>;
    result: ToolResult | null | undefined;
  }>
): MessageSource[] {
  return items.reduce<MessageSource[]>((sources, item) => {
    if (item.result?.success !== true) return sources;
    return mergeMessageSources(sources, [buildMcpDataSource(item.tool, item.args)]);
  }, []);
}

function withSuccessfulMcpDataSources<T extends Record<string, unknown>>(
  payload: T,
  items: Array<{
    tool: string;
    args: Record<string, unknown>;
    result: ToolResult | null | undefined;
  }>
): T {
  return withMessageSources(payload, mergeSuccessfulMcpDataSources(items));
}

async function callToolWithFallbackArgs(
  toolProvider: ToolProvider,
  toolName: string,
  primaryArgs: Record<string, unknown>,
  fallbackArgs: Record<string, unknown> | null
): Promise<{ result: ToolResult; args: Record<string, unknown> }> {
  const primaryResult = await toolProvider.callTool(toolName, primaryArgs);
  if (primaryResult.success || fallbackArgs == null) {
    return { result: primaryResult, args: primaryArgs };
  }
  const fallbackResult = await toolProvider.callTool(toolName, fallbackArgs);
  if (fallbackResult.success) {
    return { result: fallbackResult, args: fallbackArgs };
  }
  return { result: primaryResult, args: primaryArgs };
}

export type StructuredLookupToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_unit_report'
  | 'generate_route_report'
  | 'generate_station_report'
  | 'generate_accident_investigation_report';

export type DriverLookupCandidate = {
  id: string;
  name: string;
  identifier: string | null;
};

export type VehicleLookupCandidate = {
  id: string;
  name: string;
  identifier: string | null;
  vehicle_id: string | null;
};

export type UnitLookupCandidate = {
  id: string;
  name: string;
  identifier: string | null;
  organ_id: string | null;
};

export type RouteLookupCandidate = {
  id: string;
  name: string;
  identifier: string | null;
  route_id: string | null;
  route_name: string | null;
};

export type StationLookupCandidate = {
  id: string;
  name: string;
  identifier: string | null;
  station_id: string | null;
  station_name: string | null;
};

export type IncidentLookupCandidate = {
  id: string;
  name: string;
  identifier: string | null;
  driver_name: string | null;
  ppartition: string | null;
  accident_date: string | null;
};

type LookupFailureReason =
  | 'not_found'
  | 'invalid_query'
  | 'permission_denied'
  | 'mcp_unreachable'
  | 'mcp_timeout'
  | 'mcp_5xx'
  | 'payload_mismatch'
  | 'protocol_error'
  | 'upstream_error';
type DriverLookupClarifyReason =
  | 'too_short'
  | 'ambiguous'
  | 'same_name'
  | 'single_candidate'
  | LookupFailureReason;
type CommonLookupClarifyReason =
  | 'too_short'
  | 'ambiguous'
  | 'single_candidate'
  | LookupFailureReason;

export type DriverLookupResolution =
  | {
      kind: 'resolved';
      query: string;
      candidate: DriverLookupCandidate;
      data: Record<string, unknown>;
      matchType: 'exact';
    }
  | {
      kind: 'clarify';
      query: string;
      reason: DriverLookupClarifyReason;
      candidates: DriverLookupCandidate[];
    };

export type VehicleLookupResolution =
  | {
      kind: 'resolved';
      query: string;
      candidate: VehicleLookupCandidate;
      data: Record<string, unknown>;
      matchType: 'exact';
    }
  | {
      kind: 'clarify';
      query: string;
      reason: CommonLookupClarifyReason;
      candidates: VehicleLookupCandidate[];
    };

export type UnitLookupResolution =
  | {
      kind: 'resolved';
      query: string;
      candidate: UnitLookupCandidate;
      data: Record<string, unknown>;
      matchType: 'exact';
    }
  | {
      kind: 'clarify';
      query: string;
      reason: CommonLookupClarifyReason;
      candidates: UnitLookupCandidate[];
    };

export type RouteLookupResolution =
  | {
      kind: 'resolved';
      query: string;
      candidate: RouteLookupCandidate;
      data: Record<string, unknown>;
      matchType: 'exact' | 'normalized';
    }
  | {
      kind: 'clarify';
      query: string;
      reason: CommonLookupClarifyReason;
      candidates: RouteLookupCandidate[];
    };

export type StationLookupResolution =
  | {
      kind: 'resolved';
      query: string;
      candidate: StationLookupCandidate;
      data: Record<string, unknown>;
      matchType: 'exact';
    }
  | {
      kind: 'clarify';
      query: string;
      reason: CommonLookupClarifyReason;
      candidates: StationLookupCandidate[];
    };

export type IncidentLookupResolution =
  | {
      kind: 'resolved';
      query: string;
      candidate: IncidentLookupCandidate;
      data: Record<string, unknown>;
      matchType: 'exact' | 'normalized';
    }
  | {
      kind: 'clarify';
      query: string;
      reason: CommonLookupClarifyReason;
      candidates: IncidentLookupCandidate[];
    };

export type PendingDriverLookupState = {
  kind: 'driver_report_lookup';
  reason: 'missing_name' | DriverLookupClarifyReason;
  query: string;
  candidates: DriverLookupCandidate[];
};

export type PendingVehicleLookupState = {
  kind: 'vehicle_report_lookup';
  reason: 'missing_vehicle' | CommonLookupClarifyReason;
  query: string;
  candidates: VehicleLookupCandidate[];
};

export type PendingUnitLookupState = {
  kind: 'unit_report_lookup';
  reason: 'missing_unit' | CommonLookupClarifyReason;
  query: string;
  candidates: UnitLookupCandidate[];
};

export type PendingRouteLookupState = {
  kind: 'route_report_lookup';
  reason: 'missing_route' | CommonLookupClarifyReason;
  query: string;
  candidates: RouteLookupCandidate[];
};

export type PendingStationLookupState = {
  kind: 'station_report_lookup';
  reason: 'missing_station' | CommonLookupClarifyReason;
  query: string;
  candidates: StationLookupCandidate[];
};

export type PendingIncidentLookupState = {
  kind: 'incident_report_lookup';
  reason: 'missing_driver_name' | CommonLookupClarifyReason;
  query: string;
  candidates: IncidentLookupCandidate[];
};

export type PendingStructuredLookupState =
  | PendingDriverLookupState
  | PendingVehicleLookupState
  | PendingUnitLookupState
  | PendingRouteLookupState
  | PendingStationLookupState
  | PendingIncidentLookupState;

const INTERNAL_WORKER_TOOL_PREFIX = '__worker_tool__:';
const LEGACY_INTERNAL_STRUCTURED_TOOL_PREFIX = '__structured_report__:';

const GENERIC_PLACEHOLDER_ARGS = new Set([
  'unknown',
  'none',
  'null',
  'na',
  'n/a',
  'xxx',
  'xxxx',
  '待确认',
  '未知',
  '某人',
  '某车',
  '某线路',
  '某事故',
]);

const DRIVER_PLACEHOLDER_ARGS = new Set([
  'driver',
  'drivername',
  'driver_name',
  '驾驶员',
  '司机',
  '姓名',
  '名字',
  '工号',
]);

const VEHICLE_PLACEHOLDER_ARGS = new Set([
  'vehicle',
  'vehicleid',
  'vehicle_id',
  '车辆',
  '车牌',
  '车牌号',
  '车辆id',
  '车辆编号',
]);

const UNIT_PLACEHOLDER_ARGS = new Set([
  'unit',
  'organ',
  'organization',
  'company',
  'organname',
  'organ_name',
  '单位',
  '公司',
  '分公司',
  '集团',
  '单位名称',
  '机构',
  '机构名称',
]);

const ROUTE_PLACEHOLDER_ARGS = new Set([
  'route',
  'routename',
  'route_name',
  'routeid',
  'route_id',
  '线路',
  '线路名称',
  '线路编号',
]);

const INCIDENT_PLACEHOLDER_ARGS = new Set([
  'drivername',
  'driver_name',
  '驾驶员',
  '驾驶员姓名',
  'incident',
  'incidentid',
  'incident_id',
  'accident',
  '事故',
  '事故编号',
  '事故id',
  '事件id',
]);

const AFFIRMATIVE_TOKENS = new Set([
  '是',
  '是的',
  '对',
  '对的',
  '没错',
  '确认',
  '确认是',
  '就这个',
  '就是这个',
  '可以',
  '好的',
  'yes',
  'ok',
]);

function normalizeArgToken(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/[\s"'`“”‘’《》〈〉「」『』【】[\]{}()<>·,，。:：;；、/\\|]+/g, '')
    .replace(/[-_]/g, '');
}

function cleanExtractedEntityToken(value: string): string {
  return value
    .trim()
    .replace(/^[\s"'`“”‘’《》〈〉「」『』【】[(<]+/u, '')
    .replace(/[\s"'`“”‘’》〉」』】)>.,，。:：;；、]+$/u, '')
    .trim();
}

function looksLikeIntentPhrase(value: string): boolean {
  return /(请|帮我|生成|查看|查询|分析|报告|画像|调查|整改|look up|report|analysis)/i.test(
    value.trim()
  );
}

function isGenericPlaceholderArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  const normalized = normalizeArgToken(trimmed);
  if (!normalized) return true;
  if (GENERIC_PLACEHOLDER_ARGS.has(normalized)) return true;
  if (/^x{2,}$/i.test(normalized)) return true;
  if (/^\{.+\}$/.test(trimmed) || /^<.+>$/.test(trimmed) || /^\[.+\]$/.test(trimmed)) return true;
  return false;
}

function isSupportedInternalWorkerTool(value: unknown): value is WorkerToolCall['tool'] {
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
    value === 'rule_asker' ||
    value === 'rule_builder'
  );
}

function parseStructuredToolCallRecord(value: unknown): WorkerToolCall | null {
  if (!isRecord(value)) return null;
  const tool = value.tool;
  const args = value.args;
  if (!isSupportedInternalWorkerTool(tool)) return null;
  if (!isRecord(args)) return null;
  return { tool, args };
}

function parseInternalStructuredToolCall(content: string): WorkerToolCall | null {
  if (content.startsWith(INTERNAL_WORKER_TOOL_PREFIX)) {
    return parseStructuredToolCallRecord(
      safeJsonParse(content.slice(INTERNAL_WORKER_TOOL_PREFIX.length))
    );
  }
  if (content.startsWith(LEGACY_INTERNAL_STRUCTURED_TOOL_PREFIX)) {
    return parseStructuredToolCallRecord(
      safeJsonParse(content.slice(LEGACY_INTERNAL_STRUCTURED_TOOL_PREFIX.length))
    );
  }
  return null;
}

export function encodeInternalWorkerToolCall(call: WorkerToolCall): string {
  return `${INTERNAL_WORKER_TOOL_PREFIX}${JSON.stringify(call)}`;
}

function startsWithIntentLead(value: string): boolean {
  return /^(?:请帮我|帮我|生成|查看|分析|查询|请查询|请查看|请生成|look\s*up|report|analysis)/i.test(
    value.trim()
  );
}

function isInvalidDriverNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) return true;
  if (DRIVER_PLACEHOLDER_ARGS.has(normalized)) return true;
  if (startsWithIntentLead(trimmed)) return true;
  if (looksLikeIntentPhrase(trimmed) && !/^[\u4e00-\u9fa5]{2,4}$/.test(trimmed)) return true;
  return false;
}

function isInvalidVehicleIdArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) return true;
  if (VEHICLE_PLACEHOLDER_ARGS.has(normalized)) return true;
  if (
    /(\u96c6\u56e2|\u516c\u53f8|\u603b\u516c\u53f8|\u5206\u516c\u53f8|\u8f66\u961f|\u8f66\u961f\u96c6\u56e2)/.test(
      trimmed
    ) ||
    normalized.includes('group') ||
    normalized.includes('company') ||
    normalized.includes('fleet')
  ) {
    return true;
  }
  if (
    normalized.includes('vehicletype') ||
    normalized.includes('bustype') ||
    normalized.includes('usenature') ||
    normalized.includes('vehicletypelist') ||
    normalized === 'type' ||
    normalized === 'list' ||
    normalized === 'count' ||
    normalized === 'stat' ||
    normalized === 'stats' ||
    trimmed.includes('类型') ||
    trimmed.includes('使用性质') ||
    trimmed.includes('统计') ||
    trimmed.includes('列表')
  ) {
    return true;
  }
  if (startsWithIntentLead(trimmed)) return true;
  if (looksLikeIntentPhrase(trimmed) && !/^[A-Za-z0-9\u4e00-\u9fa5-]{2,20}$/.test(trimmed))
    return true;
  return false;
}

function isInvalidUnitNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) return true;
  if (UNIT_PLACEHOLDER_ARGS.has(normalized)) return true;
  if (startsWithIntentLead(trimmed)) return true;
  if (looksLikeIntentPhrase(trimmed) && !/^[A-Za-z0-9\u4e00-\u9fa5-]{2,40}$/.test(trimmed))
    return true;
  return false;
}

function isInvalidRouteNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) return true;
  if (ROUTE_PLACEHOLDER_ARGS.has(normalized)) return true;
  if (startsWithIntentLead(trimmed)) return true;
  if (looksLikeIntentPhrase(trimmed) && !/^[A-Za-z0-9\u4e00-\u9fa5-]{2,32}$/.test(trimmed))
    return true;
  return false;
}

function isInvalidStationNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) return true;
  if (startsWithIntentLead(trimmed)) return true;
  if (normalized === 'station' || normalized === 'busstation' || normalized === '站场') return true;
  if (looksLikeIntentPhrase(trimmed) && !/^[A-Za-z0-9\u4e00-\u9fa5-]{2,40}$/.test(trimmed))
    return true;
  return false;
}

function isInvalidIncidentArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) return true;
  if (INCIDENT_PLACEHOLDER_ARGS.has(normalized)) return true;
  if (startsWithIntentLead(trimmed)) return true;
  if (
    looksLikeIntentPhrase(trimmed) &&
    !/^[A-Za-z0-9\u4e00-\u9fa5/_-]{2,64}$/.test(trimmed) &&
    !/^\d{4}-\d{2}-\d{2}$/.test(trimmed)
  ) {
    return true;
  }
  return false;
}

function isLikelyIncompleteDriverArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  if (/^[\u4e00-\u9fa5]$/.test(trimmed)) return true;
  const normalized = normalizeArgToken(trimmed);
  return /^\d{1,3}$/.test(normalized) || /^[a-z]\d{0,2}$/i.test(normalized);
}

function isLikelyIncompleteVehicleArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  const normalized = normalizeArgToken(trimmed);
  if (isMissingGuangdongVehiclePlateSeries(trimmed)) return true;
  if (normalized.length <= 1) return true;
  if (/^\d{1,3}$/.test(normalized)) return true;
  if (/^[a-z]{1,2}\d{0,2}$/i.test(normalized)) return true;
  return false;
}

function isLikelyIncompleteUnitArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  const normalized = normalizeArgToken(trimmed);
  if (normalized.length <= 1) return true;
  if (isStandaloneFleetNameArg(trimmed)) return true;
  return UNIT_PLACEHOLDER_ARGS.has(normalized);
}

function isStandaloneFleetNameArg(value: string): boolean {
  return /^(?:(?:第)?(?:\d+|[一二三四五六七八九十]+)(?:车队|队)|车(?:\d+|[一二三四五六七八九十]+)队)$/u.test(
    value.normalize('NFKC').replace(/\s+/g, '').trim()
  );
}

function hasHyphenNumberFleetSuffix(value: string): boolean {
  return /-\s*(?:\d+|[一二三四五六七八九十]+)\s*车队/u.test(value.normalize('NFKC'));
}

function normalizeUnitLookupMatchToken(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/[“”"'`]/g, '')
    .replace(/[（）()【】\[\]<>《》]/g, '')
    .replace(/\s+/g, '');
}

function doesUnitPayloadMatchQuery(
  query: string,
  payload: Record<string, unknown>,
  candidateName: string,
  candidateId: string
): boolean {
  if (!hasHyphenNumberFleetSuffix(query)) return true;
  const requested = normalizeUnitLookupMatchToken(query);
  if (!requested) return true;
  const candidates = [
    candidateName,
    candidateId,
    readFirstStringAtPaths(payload, ['basic.organ_name', 'name']),
    readFirstStringAtPaths(payload, ['basic.organ_id', 'identifier', 'id']),
  ]
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => normalizeUnitLookupMatchToken(item));
  return candidates.some((item) => item === requested || item.includes(requested));
}

function isLikelyIncompleteRouteArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  const normalized = normalizeArgToken(trimmed);
  if (normalized.length <= 1) return true;
  return normalized === '线路' || normalized === 'route' || normalized === 'line';
}

function isLikelyIncompleteStationArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  const normalized = normalizeArgToken(trimmed);
  if (normalized.length <= 1) return true;
  return normalized === 'station' || normalized === 'busstation' || normalized === '站场';
}

function isLikelyIncompleteIncidentArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  const normalized = normalizeArgToken(trimmed);
  if (/^\d{1,3}$/.test(normalized)) return true;
  return normalized.length <= 1;
}

export function extractStructuredReportToolCall(content: string): WorkerToolCall | null {
  const internal = parseInternalStructuredToolCall(content);
  if (internal) {
    return internal;
  }

  const parsedJson = parseStructuredToolCallRecord(safeJsonParse(content));
  if (parsedJson) {
    return parsedJson;
  }

  return null;
}

function levenshteinDistance(left: string, right: string): number {
  if (left === right) return 0;
  if (!left) return right.length;
  if (!right) return left.length;

  const rows = left.length + 1;
  const cols = right.length + 1;
  const dp: number[][] = Array.from({ length: rows }, () => Array<number>(cols).fill(0));

  for (let row = 0; row < rows; row += 1) dp[row][0] = row;
  for (let col = 0; col < cols; col += 1) dp[0][col] = col;

  for (let row = 1; row < rows; row += 1) {
    for (let col = 1; col < cols; col += 1) {
      const cost = left[row - 1] === right[col - 1] ? 0 : 1;
      dp[row][col] = Math.min(
        dp[row - 1][col] + 1,
        dp[row][col - 1] + 1,
        dp[row - 1][col - 1] + cost
      );
    }
  }

  return dp[left.length][right.length];
}

function scoreByTokens(query: string, tokens: string[], fuzzyThreshold = 3): number {
  const normalizedQuery = normalizeArgToken(query);
  if (!normalizedQuery) return Number.NEGATIVE_INFINITY;

  let score = 0;
  for (const token of tokens.map((item) => normalizeArgToken(item)).filter(Boolean)) {
    if (token === normalizedQuery) return 1000;
    if (token.startsWith(normalizedQuery)) score = Math.max(score, 220);
    if (token.includes(normalizedQuery)) score = Math.max(score, 180);
    if (normalizedQuery.includes(token) && token.length >= 2) score = Math.max(score, 150);
    if (normalizedQuery.length >= fuzzyThreshold && token.length >= fuzzyThreshold) {
      const distance = levenshteinDistance(normalizedQuery, token);
      if (distance === 1) score = Math.max(score, 140);
      if (distance === 2 && normalizedQuery.length >= 4) score = Math.max(score, 90);
    }
  }
  return score;
}

function dedupeCandidates<T extends { id: string }>(candidates: T[]): T[] {
  const seen = new Set<string>();
  const next: T[] = [];
  for (const candidate of candidates) {
    const key = candidate.id.trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    next.push(candidate);
  }
  return next;
}

function parseProfileData(raw: string): Record<string, unknown> {
  const parsed = safeJsonParse(raw);
  return isRecord(parsed) ? parsed : {};
}

function buildDriverData(row: {
  id: string;
  name: string;
  identifier: string | null;
  data: string;
}): Record<string, unknown> {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    ...parseProfileData(row.data),
  };
}

function buildVehicleData(row: {
  id: string;
  name: string;
  identifier: string | null;
  vehicle_id: string | null;
  data: string;
}): Record<string, unknown> {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    vehicle_id: row.vehicle_id,
    ...parseProfileData(row.data),
  };
}

function buildRouteData(row: {
  id: string;
  name: string;
  identifier: string | null;
  route_id: string | null;
  route_name: string | null;
  data: string;
}): Record<string, unknown> {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    route_id: row.route_id,
    route_name: row.route_name,
    ...parseProfileData(row.data),
  };
}

function buildIncidentData(row: {
  id: string;
  name: string;
  identifier: string | null;
  driver_name: string | null;
  ppartition: string | null;
  accident_date: string | null;
  data: string;
}): Record<string, unknown> {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    driver_name: row.driver_name,
    ppartition: row.ppartition,
    accident_date: row.accident_date,
    ...parseProfileData(row.data),
  };
}

function buildDriverCandidate(row: {
  id: string;
  name: string;
  identifier: string | null;
}): DriverLookupCandidate {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
  };
}

function buildVehicleCandidate(row: {
  id: string;
  name: string;
  identifier: string | null;
  vehicle_id: string | null;
}): VehicleLookupCandidate {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    vehicle_id: row.vehicle_id,
  };
}

function buildUnitCandidate(row: {
  id: string;
  name: string;
  identifier: string | null;
  organ_id?: string | null;
}): UnitLookupCandidate {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    organ_id: row.organ_id ?? row.identifier,
  };
}

function buildRouteCandidate(row: {
  id: string;
  name: string;
  identifier: string | null;
  route_id: string | null;
  route_name: string | null;
}): RouteLookupCandidate {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    route_id: row.route_id,
    route_name: row.route_name,
  };
}

function buildStationCandidate(row: {
  id: string;
  name: string;
  identifier: string | null;
  station_id: string | null;
  station_name: string | null;
}): StationLookupCandidate {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    station_id: row.station_id,
    station_name: row.station_name,
  };
}

function buildIncidentCandidate(row: {
  id: string;
  name: string;
  identifier: string | null;
  driver_name?: string | null;
  ppartition?: string | null;
  accident_date: string | null;
}): IncidentLookupCandidate {
  return {
    id: row.id,
    name: row.name,
    identifier: row.identifier,
    driver_name: row.driver_name ?? row.name ?? row.identifier ?? row.id,
    ppartition: row.ppartition ?? null,
    accident_date: row.accident_date,
  };
}

function normalizeLookupErrorCode(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = value.trim();
  if (!/^\d+$/.test(normalized)) {
    return null;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function hasExplicitNullResultPayload(value: unknown): boolean {
  return (
    isRecord(value) && Object.prototype.hasOwnProperty.call(value, 'result') && value.result == null
  );
}

function isLookupNotFoundErrorMessage(message: string): boolean {
  const normalized = message.normalize('NFKC').trim();
  if (!normalized) {
    return false;
  }
  return (
    normalized.includes('查询条件不存在') ||
    normalized.includes('未找到') ||
    normalized.includes('无画像数据') ||
    normalized.includes('不存在对应数据') ||
    normalized.includes('没有对应数据')
  );
}

function classifyLookupToolFailure(result: ToolResult | null | undefined): LookupFailureReason {
  const message = typeof result?.error === 'string' ? result.error.trim() : '';
  const code = normalizeLookupErrorCode(result?.error_code);

  if (
    code === 403 ||
    /^HTTP\s*403\b/i.test(message) ||
    /权限不足|无权限|forbidden|access denied/i.test(message)
  ) {
    return 'permission_denied';
  }
  if (isLookupNotFoundErrorMessage(message)) {
    return 'not_found';
  }
  if (code === 400 || /^HTTP\s*400\b/i.test(message)) {
    return 'invalid_query';
  }
  if (/timeout|timed\s*out|超时/i.test(message)) {
    return 'mcp_timeout';
  }
  if (
    /ECONNREFUSED|connection refused|ECONNRESET|ENOTFOUND|EHOSTUNREACH|network unreachable|fetch failed|MCP_SERVER_URL is not configured/i.test(
      message
    )
  ) {
    return 'mcp_unreachable';
  }
  if (/initialize|tools\/list|jsonrpc|protocol|session/i.test(message)) {
    return 'protocol_error';
  }
  if ((code != null && code >= 500 && code < 600) || /^HTTP\s*5\d{2}\b/i.test(message)) {
    return 'mcp_5xx';
  }
  return 'upstream_error';
}

export async function resolveDriverLookup(
  db: any,
  rawQuery: string,
  toolProvider?: ToolProvider,
  partition?: string
): Promise<DriverLookupResolution> {
  void db;
  const query = cleanExtractedEntityToken(rawQuery);
  if (isLikelyIncompleteDriverArg(query)) {
    return { kind: 'clarify', query, reason: 'too_short', candidates: [] };
  }

  const result = toolProvider
    ? await toolProvider.callTool(DRIVER_PROFILE_MCP_TOOL_NAME, {
        driverName: query,
        ...(partition ? { ppartition: partition } : {}),
      })
    : null;
  if (toolProvider && result && !result.success) {
    return { kind: 'clarify', query, reason: classifyLookupToolFailure(result), candidates: [] };
  }
  const trendResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(DRIVER_TREND_MCP_TOOL_NAME, {
          driverName: query,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const riskScoreResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(DRIVER_RISK_SCORE_MCP_TOOL_NAME, {
          driverName: query,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const suggestionResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(DRIVER_SUGGESTION_MCP_TOOL_NAME, {
          driverName: query,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const mcpDriverProfile = result?.success
    ? adaptDriverProfileToolResult(
        result.data,
        query,
        partition,
        trendResult?.success ? trendResult.data : null,
        riskScoreResult?.success ? riskScoreResult.data : null,
        suggestionResult?.success ? suggestionResult.data : null
      )
    : null;
  if (mcpDriverProfile) {
    const resolvedDriverName =
      readFirstStringAtPaths(mcpDriverProfile, ['basic.driver_name', 'name']) ?? query;
    const resolvedDriverId =
      readFirstStringAtPaths(mcpDriverProfile, ['basic.driver_id', 'identifier', 'id']) ?? null;
    const resolvedEntityId = resolvedDriverId ?? resolvedDriverName;
    return {
      kind: 'resolved',
      query,
      candidate: {
        id: resolvedEntityId,
        name: resolvedDriverName,
        identifier: resolvedDriverId,
      },
      data: withSuccessfulMcpDataSources({
        id: resolvedEntityId,
        name: resolvedDriverName,
        identifier: resolvedDriverId,
        ...mcpDriverProfile,
      }, [
        {
          tool: DRIVER_PROFILE_MCP_TOOL_NAME,
          args: { driverName: query, ...(partition ? { ppartition: partition } : {}) },
          result,
        },
        {
          tool: DRIVER_TREND_MCP_TOOL_NAME,
          args: { driverName: query, ...(partition ? { ppartition: partition } : {}) },
          result: trendResult,
        },
        {
          tool: DRIVER_RISK_SCORE_MCP_TOOL_NAME,
          args: { driverName: query, ...(partition ? { ppartition: partition } : {}) },
          result: riskScoreResult,
        },
        {
          tool: DRIVER_SUGGESTION_MCP_TOOL_NAME,
          args: { driverName: query, ...(partition ? { ppartition: partition } : {}) },
          result: suggestionResult,
        },
      ]),
      matchType: 'exact',
    };
  }

  if (result?.success && !hasExplicitNullResultPayload(result.data)) {
    return { kind: 'clarify', query, reason: 'payload_mismatch', candidates: [] };
  }
  return { kind: 'clarify', query, reason: 'not_found', candidates: [] };
}

export async function resolveVehicleLookup(
  db: any,
  rawQuery: string,
  toolProvider?: ToolProvider,
  partition?: string
): Promise<VehicleLookupResolution> {
  const query = normalizeGuangdongVehiclePlate(cleanExtractedEntityToken(rawQuery));
  if (isLikelyIncompleteVehicleArg(query)) {
    return { kind: 'clarify', query, reason: 'too_short', candidates: [] };
  }

  const result = toolProvider
    ? await toolProvider.callTool(VEHICLE_PROFILE_MCP_TOOL_NAME, {
        numberPlate: query,
        ...(partition ? { ppartition: partition } : {}),
      })
    : null;
  if (toolProvider && result && !result.success) {
    return { kind: 'clarify', query, reason: classifyLookupToolFailure(result), candidates: [] };
  }
  const suggestionResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(VEHICLE_SUGGESTION_MCP_TOOL_NAME, {
          numberPlate: query,
          ...(partition ? { partition } : {}),
        })
      : null;
  const riskScoreResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(VEHICLE_RISK_SCORE_MCP_TOOL_NAME, {
          numberplate: query,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const mcpVehicleProfile = result?.success
    ? adaptVehicleProfileToolResult(
        result.data,
        query,
        partition,
        suggestionResult?.success ? suggestionResult.data : null,
        riskScoreResult?.success ? riskScoreResult.data : null
      )
    : null;
  if (mcpVehicleProfile) {
    const resolvedPlateNumber =
      readFirstStringAtPaths(mcpVehicleProfile, ['basic.plate_number', 'identifier']) ?? query;
    const resolvedVehicleId =
      readFirstStringAtPaths(mcpVehicleProfile, ['basic.vehicle_id', 'id']) ?? resolvedPlateNumber;
    return {
      kind: 'resolved',
      query,
      candidate: {
        id: resolvedPlateNumber,
        name: resolvedPlateNumber,
        identifier: resolvedPlateNumber,
        vehicle_id: resolvedVehicleId,
      },
      data: withSuccessfulMcpDataSources({
        id: resolvedVehicleId,
        name: resolvedPlateNumber,
        identifier: resolvedPlateNumber,
        vehicle_id: resolvedVehicleId,
        ...mcpVehicleProfile,
      }, [
        {
          tool: VEHICLE_PROFILE_MCP_TOOL_NAME,
          args: { numberPlate: query, ...(partition ? { ppartition: partition } : {}) },
          result,
        },
        {
          tool: VEHICLE_SUGGESTION_MCP_TOOL_NAME,
          args: { numberPlate: query, ...(partition ? { partition } : {}) },
          result: suggestionResult,
        },
        {
          tool: VEHICLE_RISK_SCORE_MCP_TOOL_NAME,
          args: { numberplate: query, ...(partition ? { ppartition: partition } : {}) },
          result: riskScoreResult,
        },
      ]),
      matchType: 'exact',
    };
  }

  if (result?.success && !hasExplicitNullResultPayload(result.data)) {
    return { kind: 'clarify', query, reason: 'payload_mismatch', candidates: [] };
  }
  return {
    kind: 'clarify',
    query,
    reason: 'not_found',
    candidates: [],
  };
}

export async function resolveUnitLookup(
  db: any,
  rawQuery: string,
  toolProvider?: ToolProvider,
  partition?: string
): Promise<UnitLookupResolution> {
  const query = cleanExtractedEntityToken(rawQuery);
  if (isLikelyIncompleteUnitArg(query) || isInvalidUnitNameArg(query)) {
    return { kind: 'clarify', query, reason: 'too_short', candidates: [] };
  }
  const lookupName = await getStandardUnitName(db, query);

  const result = toolProvider
    ? await toolProvider.callTool(UNIT_PROFILE_MCP_TOOL_NAME, {
        organName: lookupName,
        ...(partition ? { ppartition: partition } : {}),
      })
    : null;
  if (toolProvider && result && !result.success) {
    return { kind: 'clarify', query, reason: classifyLookupToolFailure(result), candidates: [] };
  }
  const trendResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(UNIT_TREND_MCP_TOOL_NAME, {
          organName: lookupName,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const keyRiskResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(UNIT_KEY_RISK_MCP_TOOL_NAME, {
          organName: lookupName,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const suggestionResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(UNIT_SUGGESTION_MCP_TOOL_NAME, {
          organName: lookupName,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const mcpUnitProfile = result?.success
    ? adaptUnitProfileToolResult(
        result.data,
        lookupName,
        partition,
        trendResult?.success ? trendResult.data : null,
        keyRiskResult?.success ? keyRiskResult.data : null,
        suggestionResult?.success ? suggestionResult.data : null
      )
    : null;
  if (mcpUnitProfile) {
    const resolvedOrganName =
      readFirstStringAtPaths(mcpUnitProfile, ['basic.organ_name', 'name']) ?? query;
    const resolvedOrganId =
      readFirstStringAtPaths(mcpUnitProfile, ['basic.organ_id', 'identifier', 'id']) ??
      resolvedOrganName;
    if (!doesUnitPayloadMatchQuery(query, mcpUnitProfile, resolvedOrganName, resolvedOrganId)) {
      return { kind: 'clarify', query, reason: 'payload_mismatch', candidates: [] };
    }
    return {
      kind: 'resolved',
      query,
      candidate: {
        id: resolvedOrganId,
        name: resolvedOrganName,
        identifier: resolvedOrganId,
        organ_id: resolvedOrganId,
      },
      data: withSuccessfulMcpDataSources({
        id: resolvedOrganId,
        name: resolvedOrganName,
        identifier: resolvedOrganId,
        organ_id: resolvedOrganId,
        ...mcpUnitProfile,
      }, [
        {
          tool: UNIT_PROFILE_MCP_TOOL_NAME,
          args: { organName: lookupName, ...(partition ? { ppartition: partition } : {}) },
          result,
        },
        {
          tool: UNIT_TREND_MCP_TOOL_NAME,
          args: { organName: lookupName, ...(partition ? { ppartition: partition } : {}) },
          result: trendResult,
        },
        {
          tool: UNIT_KEY_RISK_MCP_TOOL_NAME,
          args: { organName: lookupName, ...(partition ? { ppartition: partition } : {}) },
          result: keyRiskResult,
        },
        {
          tool: UNIT_SUGGESTION_MCP_TOOL_NAME,
          args: { organName: lookupName, ...(partition ? { ppartition: partition } : {}) },
          result: suggestionResult,
        },
      ]),
      matchType: 'exact',
    };
  }

  if (result?.success) {
    return { kind: 'clarify', query, reason: 'payload_mismatch', candidates: [] };
  }
  return {
    kind: 'clarify',
    query,
    reason: 'not_found',
    candidates: [],
  };
}

export async function resolveRouteLookup(
  db: any,
  rawQuery: string,
  toolProvider?: ToolProvider,
  partition?: string
): Promise<RouteLookupResolution> {
  const query = cleanExtractedEntityToken(rawQuery);
  if (isLikelyIncompleteRouteArg(query)) {
    return { kind: 'clarify', query, reason: 'too_short', candidates: [] };
  }
  const lookupName = await getStandardRouteName(db, query);

  const result = toolProvider
    ? await toolProvider.callTool(ROUTE_PROFILE_MCP_TOOL_NAME, {
        routeName: lookupName,
        ...(partition ? { ppartition: partition } : {}),
      })
    : null;
  if (toolProvider && result && !result.success) {
    return { kind: 'clarify', query, reason: classifyLookupToolFailure(result), candidates: [] };
  }
  const suggestionResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(ROUTE_SUGGESTION_MCP_TOOL_NAME, {
          routeName: lookupName,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const routePayload =
    result?.success && isRecord(result.data) && isRecord(result.data.result)
      ? (result.data.result as Record<string, unknown>)
      : result?.success && isRecord(result.data)
        ? result.data
        : null;
  const routeId = routePayload && isRecord(routePayload.main)
    ? readFirstStringAtPaths(routePayload.main, ['routeId', 'route_id', 'id', 'identifier'])
    : null;
  const riskScoreLookup =
    result?.success && toolProvider
      ? await callToolWithFallbackArgs(
          toolProvider,
          ROUTE_RISK_SCORE_MCP_TOOL_NAME,
          {
            ...(routeId ? { routeId } : { routeName: lookupName }),
            ...(partition ? { ppartition: partition } : {}),
          },
          routeId
            ? { routeName: lookupName, ...(partition ? { ppartition: partition } : {}) }
            : null
        )
      : null;
  const routeProfile = result?.success
    ? adaptRouteProfileToolResult(
        result.data,
        lookupName,
        partition,
        suggestionResult?.success ? suggestionResult.data : null,
        riskScoreLookup?.result.success ? riskScoreLookup.result.data : null
      )
    : null;
  const resolvedRouteName =
    routeProfile == null
      ? null
      : readFirstStringAtPaths(routeProfile, ['basic.route_name', 'route_name', 'name']);
  if (routeProfile && resolvedRouteName) {
    const resolvedRouteId =
      readFirstStringAtPaths(routeProfile, ['basic.route_id', 'route_id', 'identifier', 'id']) ??
      resolvedRouteName;
    return {
      kind: 'resolved',
      query,
      candidate: {
        id: resolvedRouteId,
        name: resolvedRouteName,
        identifier: resolvedRouteId,
        route_id: resolvedRouteId,
        route_name: resolvedRouteName,
      },
      data: withSuccessfulMcpDataSources({
        id: resolvedRouteId,
        name: resolvedRouteName,
        identifier: resolvedRouteId,
        route_id: resolvedRouteId,
        route_name: resolvedRouteName,
        ...routeProfile,
      }, [
        {
          tool: ROUTE_PROFILE_MCP_TOOL_NAME,
          args: { routeName: lookupName, ...(partition ? { ppartition: partition } : {}) },
          result,
        },
        {
          tool: ROUTE_SUGGESTION_MCP_TOOL_NAME,
          args: { routeName: lookupName, ...(partition ? { ppartition: partition } : {}) },
          result: suggestionResult,
        },
        {
          tool: ROUTE_RISK_SCORE_MCP_TOOL_NAME,
          args:
            riskScoreLookup?.args ?? {
              ...(routeId ? { routeId } : { routeName: lookupName }),
              ...(partition ? { ppartition: partition } : {}),
            },
          result: riskScoreLookup?.result,
        },
      ]),
      matchType: lookupName === query ? 'exact' : 'normalized',
    };
  }

  if (result?.success && !hasExplicitNullResultPayload(result.data)) {
    return { kind: 'clarify', query, reason: 'payload_mismatch', candidates: [] };
  }

  return {
    kind: 'clarify',
    query,
    reason: 'not_found',
    candidates: [],
  };
}

export async function resolveStationLookup(
  db: any,
  rawQuery: string,
  toolProvider?: ToolProvider,
  partition?: string
): Promise<StationLookupResolution> {
  void db;
  const query = cleanExtractedEntityToken(rawQuery);
  if (isLikelyIncompleteStationArg(query) || isInvalidStationNameArg(query)) {
    return { kind: 'clarify', query, reason: 'too_short', candidates: [] };
  }

  const result = toolProvider
    ? await toolProvider.callTool(STATION_PROFILE_MCP_TOOL_NAME, {
        busStationName: query,
        ...(partition ? { ppartition: partition } : {}),
      })
    : null;
  if (toolProvider && result && !result.success) {
    return { kind: 'clarify', query, reason: classifyLookupToolFailure(result), candidates: [] };
  }
  const suggestionResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(STATION_SUGGESTION_MCP_TOOL_NAME, {
          busStationName: query,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const riskScoreResult =
    result?.success && toolProvider
      ? await toolProvider.callTool(STATION_RISK_SCORE_MCP_TOOL_NAME, {
          busStationName: query,
          ...(partition ? { ppartition: partition } : {}),
        })
      : null;
  const stationProfile = result?.success
    ? adaptStationProfileToolResult(
        result.data,
        query,
        partition,
        suggestionResult?.success ? suggestionResult.data : null,
        riskScoreResult?.success ? riskScoreResult.data : null
      )
    : null;
  const resolvedStationName =
    stationProfile == null
      ? null
      : readFirstStringAtPaths(stationProfile, ['basic.station_name', 'station_name', 'name']);
  if (stationProfile && resolvedStationName) {
    const resolvedStationId =
      readFirstStringAtPaths(stationProfile, [
        'basic.station_id',
        'station_id',
        'identifier',
        'id',
      ]) ?? resolvedStationName;
    return {
      kind: 'resolved',
      query,
      candidate: buildStationCandidate({
        id: resolvedStationId,
        name: resolvedStationName,
        identifier: resolvedStationId,
        station_id: resolvedStationId,
        station_name: resolvedStationName,
      }),
      data: withSuccessfulMcpDataSources({
        id: resolvedStationId,
        name: resolvedStationName,
        identifier: resolvedStationId,
        station_id: resolvedStationId,
        station_name: resolvedStationName,
        ...stationProfile,
      }, [
        {
          tool: STATION_PROFILE_MCP_TOOL_NAME,
          args: { busStationName: query, ...(partition ? { ppartition: partition } : {}) },
          result,
        },
        {
          tool: STATION_SUGGESTION_MCP_TOOL_NAME,
          args: { busStationName: query, ...(partition ? { ppartition: partition } : {}) },
          result: suggestionResult,
        },
        {
          tool: STATION_RISK_SCORE_MCP_TOOL_NAME,
          args: { busStationName: query, ...(partition ? { ppartition: partition } : {}) },
          result: riskScoreResult,
        },
      ]),
      matchType: 'exact',
    };
  }

  if (result?.success && !hasExplicitNullResultPayload(result.data)) {
    return { kind: 'clarify', query, reason: 'payload_mismatch', candidates: [] };
  }

  return {
    kind: 'clarify',
    query,
    reason: 'not_found',
    candidates: [],
  };
}

export async function resolveIncidentLookup(
  db: any,
  rawQuery: string,
  partition?: string | null,
  toolProvider?: ToolProvider
): Promise<IncidentLookupResolution> {
  void db;
  const query = cleanExtractedEntityToken(rawQuery);
  if (isLikelyIncompleteIncidentArg(query)) {
    return { kind: 'clarify', query, reason: 'too_short', candidates: [] };
  }

  const result = toolProvider
    ? await toolProvider.callTool(ACCIDENT_INVESTIGATION_MCP_TOOL_NAME, {
        driverName: query,
        accidentDate: partition ?? getDefaultAccidentPartition(),
      })
    : null;
  if (toolProvider && result && !result.success) {
    return { kind: 'clarify', query, reason: classifyLookupToolFailure(result), candidates: [] };
  }
  const incidentPayload =
    result?.success && isRecord(result.data)
      ? isRecord(result.data.result)
        ? (result.data.result as Record<string, unknown>)
        : result.data
      : null;

  if (incidentPayload) {
    const resolvedDriverName =
      readFirstStringAtPaths(incidentPayload, [
        'basic.driver_name',
        'driver_name',
        'name',
        'identifier',
        'id',
      ]) ?? query;
    const resolvedTitle =
      readFirstStringAtPaths(incidentPayload, [
        'report_title',
        'name',
        'title',
        'basic.report_title',
      ]) ?? resolvedDriverName;
    const accidentDate =
      readFirstStringAtPaths(incidentPayload, ['basic.accident_date', 'accident_date']) ?? null;
    const resolvedPartition =
      readFirstStringAtPaths(incidentPayload, ['basic.ppartition', 'ppartition', 'partition']) ??
      partition ??
      getDefaultAccidentPartition();
    return {
      kind: 'resolved',
      query,
      candidate: {
        id: resolvedDriverName,
        name: resolvedTitle,
        identifier: resolvedDriverName,
        driver_name: resolvedDriverName,
        ppartition: resolvedPartition,
        accident_date: accidentDate,
      },
      data: withSuccessfulMcpDataSources({
        id: resolvedDriverName,
        name: resolvedTitle,
        identifier: resolvedDriverName,
        driver_name: resolvedDriverName,
        ppartition: resolvedPartition,
        accident_date: accidentDate,
        ...incidentPayload,
      }, [
        {
          tool: ACCIDENT_INVESTIGATION_MCP_TOOL_NAME,
          args: {
            driverName: query,
            accidentDate: partition ?? getDefaultAccidentPartition(),
          },
          result,
        },
      ]),
      matchType: 'exact',
    };
  }

  if (result?.success && !hasExplicitNullResultPayload(result.data)) {
    return { kind: 'clarify', query, reason: 'payload_mismatch', candidates: [] };
  }
  return { kind: 'clarify', query, reason: 'not_found', candidates: [] };
}

function formatDriverLookupCandidate(candidate: DriverLookupCandidate): string {
  const identifier = candidate.identifier?.trim() || candidate.id;
  return `${candidate.name}（工号 ${identifier}）`;
}

function formatVehicleLookupCandidate(candidate: VehicleLookupCandidate): string {
  const plateNumber = candidate.identifier?.trim() || candidate.name;
  const vehicleId = candidate.vehicle_id?.trim() || candidate.id;
  return `${plateNumber}（车辆ID ${vehicleId}）`;
}

function formatUnitLookupCandidate(candidate: UnitLookupCandidate): string {
  const organId = candidate.organ_id?.trim() || candidate.identifier?.trim() || candidate.id;
  return `${candidate.name}（单位ID ${organId}）`;
}

function formatRouteLookupCandidate(candidate: RouteLookupCandidate): string {
  const routeName = candidate.route_name?.trim() || candidate.name;
  const routeId = candidate.route_id?.trim() || candidate.identifier?.trim() || candidate.id;
  return `${routeName}（线路ID ${routeId}）`;
}

function formatIncidentLookupCandidate(candidate: IncidentLookupCandidate): string {
  const driverName = candidate.driver_name?.trim() || candidate.identifier?.trim() || candidate.id;
  const dateText = candidate.accident_date?.trim()
    ? `，日期 ${candidate.accident_date.trim()}`
    : '';
  const partitionText = candidate.ppartition?.trim() ? `，分区 ${candidate.ppartition.trim()}` : '';
  return `${candidate.name}（驾驶员 ${driverName}${dateText}${partitionText}）`;
}

function formatStationLookupCandidate(candidate: StationLookupCandidate): string {
  const stationName = candidate.station_name?.trim() || candidate.name;
  const stationId = candidate.station_id?.trim() || candidate.identifier?.trim() || candidate.id;
  return `${stationName}（站场ID ${stationId}）`;
}

function buildTooShortReply(label: string, examples: string[], actionExample: string): string {
  return [
    `要生成${label}，需要先确认具体对象；当前提供的信息还不够。`,
    '可以直接回复更完整的标识，例如：',
    ...examples.map((item, index) => `${index + 1}. ${item}`),
    `也可以直接说：${actionExample}`,
  ].join('\n');
}

function buildAmbiguousReply(label: string, query: string, candidates: string[]): string {
  return [
    `我找到了多个可能匹配 ${query ? `“${query}”` : '该输入'} 的${label}，请确认具体对象：`,
    ...candidates.map((item, index) => `${index + 1}. ${item}`),
    '可以直接回复序号，或直接回复完整名称/编号。',
  ].join('\n');
}

function buildSingleCandidateReply(label: string, query: string, candidate: string): string {
  return [
    `我只找到一个较可能匹配 ${query ? `“${query}”` : '该输入'} 的${label}：`,
    `1. ${candidate}`,
    '如果就是它，直接回复“是”或回复完整名称/编号即可。',
  ].join('\n');
}

function buildNotFoundReply(
  label: string,
  query: string,
  hint: string,
  mode: 'named' | 'matched' = 'named'
): string {
  const headline = query
    ? mode === 'named'
      ? `未找到名为“${query}”的${label}信息。`
      : `未找到与“${query}”对应的${label}信息。`
    : `未找到对应的${label}信息。`;
  return [headline, hint].join('\n');
}

function buildInvalidQueryReply(label: string, hint: string): string {
  return [`当前查询条件无法用于查询${label}信息。`, hint].join('\n');
}

function buildPermissionDeniedReply(label: string): string {
  return [
    `当前无法查询${label}信息，权限不足。`,
    '请联系管理员确认当前账号是否具备对应画像数据的访问权限。',
  ].join('\n');
}

function buildUpstreamErrorReply(label: string): string {
  return [`当前查询${label}信息时服务异常。`, '请稍后重试。'].join('\n');
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

export function buildDriverLookupReply(resolution: DriverLookupResolution): string {
  if (resolution.kind === 'resolved') return '';
  if (resolution.reason === 'too_short') {
    return buildTooShortReply(
      '驾驶员报告',
      ['驾驶员姓名：张三', '工号：203019'],
      '生成驾驶员报告，驾驶员：张三'
    );
  }
  if (resolution.reason === 'same_name' || resolution.reason === 'ambiguous') {
    return buildAmbiguousReply(
      '驾驶员',
      resolution.query,
      resolution.candidates.map(formatDriverLookupCandidate)
    );
  }
  if (resolution.reason === 'single_candidate') {
    return buildSingleCandidateReply(
      '驾驶员',
      resolution.query,
      formatDriverLookupCandidate(resolution.candidates[0])
    );
  }
  if (resolution.reason === 'invalid_query') {
    return buildInvalidQueryReply('驾驶员', '请提供该驾驶员的准确姓名或工号。');
  }
  if (resolution.reason === 'permission_denied') {
    return buildPermissionDeniedReply('驾驶员');
  }
  if (isInfrastructureLookupFailureReason(resolution.reason)) {
    return buildUpstreamErrorReply('驾驶员');
  }
  return buildNotFoundReply('驾驶员', resolution.query, '请提供该驾驶员的准确姓名或工号。');
}

export function buildVehicleLookupReply(resolution: VehicleLookupResolution): string {
  if (resolution.kind === 'resolved') return '';
  if (resolution.reason === 'too_short') {
    return buildTooShortReply(
      '车辆报告',
      ['车牌号：沪A12345', '车牌号：粤A12345D'],
      '生成车辆报告，车辆：沪A12345'
    );
  }
  if (resolution.reason === 'ambiguous') {
    return buildAmbiguousReply(
      '车辆',
      resolution.query,
      resolution.candidates.map(formatVehicleLookupCandidate)
    );
  }
  if (resolution.reason === 'single_candidate') {
    return buildSingleCandidateReply(
      '车辆',
      resolution.query,
      formatVehicleLookupCandidate(resolution.candidates[0])
    );
  }
  if (resolution.reason === 'invalid_query') {
    return buildInvalidQueryReply(
      '车辆',
      '请提供该车辆的完整准确车牌号，例如“粤A12345”或“粤A12345D”。'
    );
  }
  if (resolution.reason === 'permission_denied') {
    return buildPermissionDeniedReply('车辆');
  }
  if (isInfrastructureLookupFailureReason(resolution.reason)) {
    return buildUpstreamErrorReply('车辆');
  }
  return buildNotFoundReply(
    '车辆',
    resolution.query,
    '请提供该车辆的完整准确车牌号，例如“粤A12345”或“粤A12345D”。',
    'matched'
  );
}

export function buildUnitLookupReply(resolution: UnitLookupResolution): string {
  if (resolution.kind === 'resolved') return '';
  if (resolution.reason === 'too_short') {
    if (isStandaloneFleetNameArg(resolution.query)) {
      return buildTooShortReply(
        '车队安全报告',
        ['完整单位名称：二分公司-二车队', '完整单位名称：巴集二分第二车队'],
        '生成单位报告，单位：二分公司-二车队'
      );
    }
    return buildTooShortReply(
      '单位报告',
      ['单位名称：二巴公司', '单位名称：广州公交第一分公司'],
      '生成单位报告，单位：二巴公司'
    );
  }
  if (resolution.reason === 'ambiguous') {
    return buildAmbiguousReply(
      '单位',
      resolution.query,
      resolution.candidates.map(formatUnitLookupCandidate)
    );
  }
  if (resolution.reason === 'single_candidate') {
    return buildSingleCandidateReply(
      '单位',
      resolution.query,
      formatUnitLookupCandidate(resolution.candidates[0])
    );
  }
  if (resolution.reason === 'invalid_query') {
    return buildInvalidQueryReply('单位', '请核对单位名称，必要时补充正确的查询日期后重试。');
  }
  if (resolution.reason === 'permission_denied') {
    return buildPermissionDeniedReply('单位');
  }
  if (isInfrastructureLookupFailureReason(resolution.reason)) {
    return buildUpstreamErrorReply('单位');
  }
  return buildNotFoundReply(
    '单位',
    resolution.query,
    '请提供该单位的准确名称，例如“二巴公司”或“广州公交第一分公司”。'
  );
}

export function buildRouteLookupReply(resolution: RouteLookupResolution): string {
  if (resolution.kind === 'resolved') return '';
  if (resolution.reason === 'too_short') {
    return buildTooShortReply(
      '线路报告',
      ['线路名称：K1', '线路编号：route-001'],
      '生成线路报告，线路：K1'
    );
  }
  if (resolution.reason === 'ambiguous') {
    return buildAmbiguousReply(
      '线路',
      resolution.query,
      resolution.candidates.map(formatRouteLookupCandidate)
    );
  }
  if (resolution.reason === 'single_candidate') {
    return buildSingleCandidateReply(
      '线路',
      resolution.query,
      formatRouteLookupCandidate(resolution.candidates[0])
    );
  }
  if (resolution.reason === 'invalid_query') {
    return buildInvalidQueryReply('线路', '请提供该线路的准确名称或线路编号。');
  }
  if (resolution.reason === 'permission_denied') {
    return buildPermissionDeniedReply('线路');
  }
  if (isInfrastructureLookupFailureReason(resolution.reason)) {
    return buildUpstreamErrorReply('线路');
  }
  return buildNotFoundReply('线路', resolution.query, '请提供该线路的准确名称或线路编号。');
}

export function buildStationLookupReply(resolution: StationLookupResolution): string {
  if (resolution.kind === 'resolved') return '';
  if (resolution.reason === 'too_short') {
    return buildTooShortReply(
      '站场报告',
      ['站场名称：体育中心站场', '站场名称：大学城南站场'],
      '生成站场报告，站场：体育中心站场'
    );
  }
  if (resolution.reason === 'ambiguous') {
    return buildAmbiguousReply(
      '站场',
      resolution.query,
      resolution.candidates.map(formatStationLookupCandidate)
    );
  }
  if (resolution.reason === 'single_candidate') {
    return buildSingleCandidateReply(
      '站场',
      resolution.query,
      formatStationLookupCandidate(resolution.candidates[0])
    );
  }
  if (resolution.reason === 'invalid_query') {
    return buildInvalidQueryReply('站场', '请提供该站场的准确名称。');
  }
  if (resolution.reason === 'permission_denied') {
    return buildPermissionDeniedReply('站场');
  }
  if (isInfrastructureLookupFailureReason(resolution.reason)) {
    return buildUpstreamErrorReply('站场');
  }
  return buildNotFoundReply('站场', resolution.query, '请提供该站场的准确名称。');
}

export function buildIncidentLookupReply(resolution: IncidentLookupResolution): string {
  if (resolution.kind === 'resolved') return '';
  if (resolution.reason === 'too_short') {
    return buildTooShortReply(
      '事故调查报告',
      [
        '驾驶员姓名：张三，事故日期：20260310',
        '驾驶员：张三，日期：2026-03-10',
        '事故日期：2026-03-10',
      ],
      '生成事故调查报告，驾驶员：张三，日期：20260310'
    );
  }
  if (resolution.reason === 'ambiguous') {
    return buildAmbiguousReply(
      '事故',
      resolution.query,
      resolution.candidates.map(formatIncidentLookupCandidate)
    );
  }
  if (resolution.reason === 'single_candidate') {
    return buildSingleCandidateReply(
      '事故',
      resolution.query,
      formatIncidentLookupCandidate(resolution.candidates[0])
    );
  }
  if (resolution.reason === 'invalid_query') {
    return buildInvalidQueryReply('事故', '请提供肇事驾驶员姓名和事故发生日期。');
  }
  if (resolution.reason === 'permission_denied') {
    return buildPermissionDeniedReply('事故');
  }
  if (isInfrastructureLookupFailureReason(resolution.reason)) {
    return buildUpstreamErrorReply('事故');
  }
  return buildNotFoundReply(
    '事故',
    resolution.query,
    '请提供肇事驾驶员姓名和事故发生日期。',
    'matched'
  );
}

export function buildDriverMissingInfoReply(): string {
  return buildTooShortReply(
    '驾驶员报告',
    ['驾驶员姓名：张三', '工号：203019'],
    '生成驾驶员报告，驾驶员：张三'
  );
}

export function buildVehicleMissingInfoReply(): string {
  return buildTooShortReply(
    '车辆报告',
    ['车牌号：沪A12345', '车牌号：粤A12345D'],
    '生成车辆报告，车辆：沪A12345'
  );
}

export function buildUnitMissingInfoReply(): string {
  return buildTooShortReply(
    '单位报告',
    ['单位名称：二巴公司', '单位名称：广州公交第一分公司'],
    '生成单位报告，单位：二巴公司'
  );
}

export function buildRouteMissingInfoReply(): string {
  return buildTooShortReply(
    '线路报告',
    ['线路名称：K1', '线路编号：route-001'],
    '生成线路报告，线路：K1'
  );
}

export function buildStationMissingInfoReply(): string {
  return buildTooShortReply(
    '站场报告',
    ['站场名称：体育中心站场', '站场名称：大学城南站场'],
    '生成站场报告，站场：体育中心站场'
  );
}

export function buildAccidentMissingInfoReply(): string {
  return buildTooShortReply(
    '事故调查报告',
    [
      '驾驶员姓名：张三，事故日期：20260310',
      '驾驶员：张三，日期：2026-03-10',
      '事故日期：2026-03-10',
    ],
    '生成事故调查报告，驾驶员：张三，日期：20260310'
  );
}

function getDriverLookupKey(resolution: DriverLookupResolution & { kind: 'resolved' }): string {
  return (
    resolution.candidate.identifier?.trim() || resolution.candidate.id || resolution.candidate.name
  );
}

function getVehicleLookupKey(resolution: VehicleLookupResolution & { kind: 'resolved' }): string {
  return (
    readFirstStringAtPaths(resolution.data, ['basic.vehicle_id']) ??
    resolution.candidate.vehicle_id?.trim() ??
    resolution.candidate.identifier?.trim() ??
    resolution.candidate.id ??
    resolution.candidate.name
  );
}

function getUnitLookupKey(resolution: UnitLookupResolution & { kind: 'resolved' }): string {
  return (
    readFirstStringAtPaths(resolution.data, ['basic.organ_id', 'identifier', 'id']) ??
    resolution.candidate.organ_id?.trim() ??
    resolution.candidate.identifier?.trim() ??
    resolution.candidate.id ??
    resolution.candidate.name
  );
}

function getRouteLookupKey(resolution: RouteLookupResolution & { kind: 'resolved' }): string {
  return (
    resolution.candidate.identifier?.trim() ||
    resolution.candidate.id ||
    resolution.candidate.route_id?.trim() ||
    resolution.candidate.route_name?.trim() ||
    resolution.candidate.name
  );
}

function getStationLookupKey(resolution: StationLookupResolution & { kind: 'resolved' }): string {
  return (
    resolution.candidate.identifier?.trim() ||
    resolution.candidate.id ||
    resolution.candidate.station_id?.trim() ||
    resolution.candidate.station_name?.trim() ||
    resolution.candidate.name
  );
}

function getIncidentLookupKey(resolution: IncidentLookupResolution & { kind: 'resolved' }): string {
  return (
    resolution.candidate.identifier?.trim() ||
    resolution.candidate.id ||
    resolution.candidate.driver_name?.trim() ||
    resolution.candidate.name
  );
}

export function buildDriverLookupWorkerPrompt(
  resolution: DriverLookupResolution & { kind: 'resolved' },
  partition?: string | null
): string {
  const driverName = resolution.candidate.name;
  const lookupKey = getDriverLookupKey(resolution);
  const dataSourceConfig = getStructuredReportDataSourceConfig('generate_driver_report');
  if (dataSourceConfig?.buildResolvedPrompt) {
    return dataSourceConfig.buildResolvedPrompt({
      displayName: driverName,
      entityId: lookupKey,
      partition,
    });
  }
  return [
    `请生成驾驶员「${driverName}」的安全报告。`,
    `已确认目标驾驶员：姓名「${driverName}」，工号「${lookupKey}」${partition ? `，报告日期为「${partition}」` : ''}。`,
    '请使用当前轮允许的驾驶员画像数据工具获取真实数据。',
    `请优先按工号“${lookupKey}”读取驾驶员画像，未命中时再按姓名“${driverName}”重试。`,
    '严格按技能模板输出 JSON，对齐管理人员版“综合风险 + 四个一级指标”的固定五行看板结构。',
    '核心风险研判写成单段总结；行为分析默认只展开四个一级指标，不重复分析综合风险。',
    '行为分析按基础指标风险分展示；如果缺少基础指标风险分，也要明确说明当前缺少风险分，不要省略也不要伪造。',
  ].join('\n');
}

export function buildVehicleLookupWorkerPrompt(
  resolution: VehicleLookupResolution & { kind: 'resolved' },
  partition?: string | null
): string {
  const plateNumber =
    String(
      readFirstStringAtPaths(resolution.data, ['basic.plate_number']) ??
        resolution.candidate.identifier ??
        resolution.candidate.name
    ).trim() || resolution.candidate.name;
  const vehicleId = getVehicleLookupKey(resolution);
  const dataSourceConfig = getStructuredReportDataSourceConfig('generate_vehicle_report');
  if (dataSourceConfig?.buildResolvedPrompt) {
    return dataSourceConfig.buildResolvedPrompt({
      displayName: plateNumber,
      entityId: vehicleId,
      partition,
    });
  }
  return [plateNumber, vehicleId].filter(Boolean).join(' ');
}

export function buildUnitLookupWorkerPrompt(
  resolution: UnitLookupResolution & { kind: 'resolved' },
  partition?: string | null
): string {
  const organName =
    String(
      readFirstStringAtPaths(resolution.data, ['basic.organ_name', 'name']) ??
        resolution.candidate.name
    ).trim() || resolution.candidate.name;
  const organId = getUnitLookupKey(resolution);
  const dataSourceConfig = getStructuredReportDataSourceConfig('generate_unit_report');
  if (dataSourceConfig?.buildResolvedPrompt) {
    return dataSourceConfig.buildResolvedPrompt({
      displayName: organName,
      entityId: organId,
      partition,
    });
  }
  return `请生成单位「${organName}」的安全风险分析总结报告（管理人员版）。`;
}

export function buildRouteLookupWorkerPrompt(
  resolution: RouteLookupResolution & { kind: 'resolved' },
  partition?: string | null
): string {
  const routeName =
    String(
      readFirstStringAtPaths(resolution.data, ['basic.route_name', 'route_name']) ??
        resolution.candidate.route_name ??
        resolution.candidate.name
    ).trim() || resolution.candidate.name;
  const routeId =
    String(
      readFirstStringAtPaths(resolution.data, ['basic.route_id', 'route_id']) ??
        resolution.candidate.route_id ??
        resolution.candidate.identifier ??
        resolution.candidate.id
    ).trim() || resolution.candidate.id;
  const lookupKey = getRouteLookupKey(resolution);
  const dataSourceConfig = getStructuredReportDataSourceConfig('generate_route_report');
  if (dataSourceConfig?.buildResolvedPrompt) {
    return dataSourceConfig.buildResolvedPrompt({
      displayName: routeName,
      entityId: lookupKey,
      partition,
    });
  }

  return [
    `请生成线路「${routeName}」的安全风险分析总结报告（管理人员版）。`,
    `已确认目标线路：线路名称「${routeName}」，线路ID「${routeId}」，查询标识「${lookupKey}」${partition ? `，报告日期为「${partition}」` : ''}。`,
    '请使用当前轮允许的线路画像数据工具获取真实数据。',
    `请优先按查询标识“${lookupKey}”读取线路画像，未命中时再按线路名称“${routeName}”重试。`,
    '仅输出管理版 JSON，必须包含 layout、management_summary、dashboard_rows、core_risk_assessment、behavior_data_analysis、interventions、appendix。',
    '“二、核心风险研判”需要逐条写明排序与关键指标，不要把其他线路的数据混入结果。',
  ].join('\n');
}

export function buildStationLookupWorkerPrompt(
  resolution: StationLookupResolution & { kind: 'resolved' },
  partition?: string | null
): string {
  const stationName =
    String(
      readFirstStringAtPaths(resolution.data, ['basic.station_name', 'station_name']) ??
        resolution.candidate.station_name ??
        resolution.candidate.name
    ).trim() || resolution.candidate.name;
  const lookupKey = getStationLookupKey(resolution);
  const dataSourceConfig = getStructuredReportDataSourceConfig('generate_station_report');
  if (dataSourceConfig?.buildResolvedPrompt) {
    return dataSourceConfig.buildResolvedPrompt({
      displayName: stationName,
      entityId: lookupKey,
      partition,
    });
  }
  return `请生成站场“${stationName}”的安全风险分析总结报告（管理人员版）。`;
}

export function buildIncidentLookupWorkerPrompt(
  resolution: IncidentLookupResolution & { kind: 'resolved' }
): string {
  const incidentTitle =
    String(
      readFirstStringAtPaths(resolution.data, ['basic.report_title']) ?? resolution.candidate.name
    ).trim() || resolution.candidate.name;
  const accidentDate = String(
    readFirstStringAtPaths(resolution.data, ['basic.accident_date']) ??
      resolution.candidate.accident_date ??
      ''
  ).trim();
  const routeName = String(
    readFirstStringAtPaths(resolution.data, ['basic.route_name']) ?? ''
  ).trim();
  const lookupKey = getIncidentLookupKey(resolution);
  const dataSourceConfig = getStructuredReportDataSourceConfig(
    'generate_accident_investigation_report'
  );

  if (dataSourceConfig?.buildResolvedPrompt) {
    return dataSourceConfig.buildResolvedPrompt({
      displayName: incidentTitle,
      entityId: lookupKey,
      partition: resolution.candidate.ppartition ?? accidentDate ?? null,
    });
  }
  return [
    '请生成事故调查情况和整改措施报告。',
    `已确认目标事故：驾驶员「${lookupKey}」${accidentDate ? `，事故日期「${accidentDate}」` : ''}${routeName ? `，事发线路「${routeName}」` : ''}。`,
    '请使用当前轮允许的事故调查数据工具获取真实数据。',
    `请优先按驾驶员姓名+事故日期"${lookupKey}${accidentDate ? `/${accidentDate}` : ''}"读取完整事故原始数据，再按"四大章节"输出结构化结果，并确保每条结论都有证据支撑。`,
  ].join('\n');
}

function parseDriverCandidates(value: unknown): DriverLookupCandidate[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      id: String(item.id ?? '').trim(),
      name: String(item.name ?? '').trim(),
      identifier: item.identifier == null ? null : String(item.identifier).trim(),
    }))
    .filter((item) => item.id && item.name);
}

function parseVehicleCandidates(value: unknown): VehicleLookupCandidate[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      id: String(item.id ?? '').trim(),
      name: String(item.name ?? '').trim(),
      identifier: item.identifier == null ? null : String(item.identifier).trim(),
      vehicle_id: item.vehicle_id == null ? null : String(item.vehicle_id).trim(),
    }))
    .filter((item) => item.id && item.name);
}

function parseUnitCandidates(value: unknown): UnitLookupCandidate[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      id: String(item.id ?? '').trim(),
      name: String(item.name ?? '').trim(),
      identifier: item.identifier == null ? null : String(item.identifier).trim(),
      organ_id: item.organ_id == null ? null : String(item.organ_id).trim(),
    }))
    .filter((item) => item.id && item.name);
}

function parseRouteCandidates(value: unknown): RouteLookupCandidate[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      id: String(item.id ?? '').trim(),
      name: String(item.name ?? '').trim(),
      identifier: item.identifier == null ? null : String(item.identifier).trim(),
      route_id: item.route_id == null ? null : String(item.route_id).trim(),
      route_name: item.route_name == null ? null : String(item.route_name).trim(),
    }))
    .filter((item) => item.id && item.name);
}

function parseIncidentCandidates(value: unknown): IncidentLookupCandidate[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      id: String(item.id ?? '').trim(),
      name: String(item.name ?? '').trim(),
      identifier: item.identifier == null ? null : String(item.identifier).trim(),
      driver_name: item.driver_name == null ? null : String(item.driver_name).trim(),
      ppartition: item.ppartition == null ? null : String(item.ppartition).trim(),
      accident_date: item.accident_date == null ? null : String(item.accident_date).trim(),
    }))
    .filter((item) => item.id && item.name);
}

function parseStationCandidates(value: unknown): StationLookupCandidate[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      id: String(item.id ?? '').trim(),
      name: String(item.name ?? '').trim(),
      identifier: item.identifier == null ? null : String(item.identifier).trim(),
      station_id: item.station_id == null ? null : String(item.station_id).trim(),
      station_name: item.station_name == null ? null : String(item.station_name).trim(),
    }))
    .filter((item) => item.id && item.name);
}

function parsePendingStructuredLookupState(value: unknown): PendingStructuredLookupState | null {
  if (!isRecord(value)) return null;
  const kind = value.kind;
  const query = typeof value.query === 'string' ? value.query.trim() : '';

  if (kind === 'driver_report_lookup') {
    const reason = typeof value.reason === 'string' ? value.reason.trim() : '';
    if (
      reason !== 'missing_name' &&
      reason !== 'too_short' &&
      reason !== 'ambiguous' &&
      reason !== 'same_name' &&
      reason !== 'single_candidate' &&
      reason !== 'not_found' &&
      reason !== 'invalid_query' &&
      reason !== 'permission_denied' &&
      reason !== 'upstream_error'
    ) {
      return null;
    }
    return { kind, reason, query, candidates: parseDriverCandidates(value.candidates) };
  }

  if (kind === 'vehicle_report_lookup') {
    const reason = typeof value.reason === 'string' ? value.reason.trim() : '';
    if (
      reason !== 'missing_vehicle' &&
      reason !== 'too_short' &&
      reason !== 'ambiguous' &&
      reason !== 'single_candidate' &&
      reason !== 'not_found' &&
      reason !== 'invalid_query' &&
      reason !== 'permission_denied' &&
      reason !== 'upstream_error'
    ) {
      return null;
    }
    return { kind, reason, query, candidates: parseVehicleCandidates(value.candidates) };
  }

  if (kind === 'unit_report_lookup') {
    const reason = typeof value.reason === 'string' ? value.reason.trim() : '';
    if (
      reason !== 'missing_unit' &&
      reason !== 'too_short' &&
      reason !== 'ambiguous' &&
      reason !== 'single_candidate' &&
      reason !== 'not_found' &&
      reason !== 'invalid_query' &&
      reason !== 'permission_denied' &&
      reason !== 'upstream_error'
    ) {
      return null;
    }
    return { kind, reason, query, candidates: parseUnitCandidates(value.candidates) };
  }

  if (kind === 'route_report_lookup') {
    const reason = typeof value.reason === 'string' ? value.reason.trim() : '';
    if (
      reason !== 'missing_route' &&
      reason !== 'too_short' &&
      reason !== 'ambiguous' &&
      reason !== 'single_candidate' &&
      reason !== 'not_found' &&
      reason !== 'invalid_query' &&
      reason !== 'permission_denied' &&
      reason !== 'upstream_error'
    ) {
      return null;
    }
    return { kind, reason, query, candidates: parseRouteCandidates(value.candidates) };
  }

  if (kind === 'station_report_lookup') {
    const reason = typeof value.reason === 'string' ? value.reason.trim() : '';
    if (
      reason !== 'missing_station' &&
      reason !== 'too_short' &&
      reason !== 'ambiguous' &&
      reason !== 'single_candidate' &&
      reason !== 'not_found' &&
      reason !== 'invalid_query' &&
      reason !== 'permission_denied' &&
      reason !== 'upstream_error'
    ) {
      return null;
    }
    return { kind, reason, query, candidates: parseStationCandidates(value.candidates) };
  }

  if (kind === 'incident_report_lookup') {
    const reason = typeof value.reason === 'string' ? value.reason.trim() : '';
    if (
      reason !== 'missing_driver_name' &&
      reason !== 'too_short' &&
      reason !== 'ambiguous' &&
      reason !== 'single_candidate' &&
      reason !== 'not_found' &&
      reason !== 'invalid_query' &&
      reason !== 'permission_denied' &&
      reason !== 'upstream_error'
    ) {
      return null;
    }
    return { kind, reason, query, candidates: parseIncidentCandidates(value.candidates) };
  }

  return null;
}

async function getPendingStructuredLookupState(
  db: any,
  sessionId: string
): Promise<PendingStructuredLookupState | null> {
  const row: { metadata: string | null } | null = await db
    .prepare(
      'SELECT metadata FROM agent_messages WHERE session_id = ? AND role = ? ORDER BY created_at DESC LIMIT 1'
    )
    .bind(sessionId, 'assistant')
    .first();
  if (!row?.metadata) return null;
  const parsed = safeJsonParse(row.metadata);
  if (!isRecord(parsed)) return null;
  return parsePendingStructuredLookupState(parsed.legacy_psl_state);
}

function getCandidateLookupTokens(
  candidate: PendingStructuredLookupState['candidates'][number]
): string[] {
  const common = [
    String(candidate.id ?? ''),
    String(candidate.name ?? ''),
    String((candidate as { identifier?: string | null }).identifier ?? ''),
  ];

  if ('vehicle_id' in candidate) {
    const vehicleCandidate = candidate as VehicleLookupCandidate;
    common.push(String(vehicleCandidate.vehicle_id ?? ''));
  }
  if ('organ_id' in candidate) {
    const unitCandidate = candidate as UnitLookupCandidate;
    common.push(String(unitCandidate.organ_id ?? ''));
  }
  if ('route_id' in candidate) {
    const routeCandidate = candidate as RouteLookupCandidate;
    common.push(String(routeCandidate.route_id ?? ''), String(routeCandidate.route_name ?? ''));
  }
  if ('station_id' in candidate) {
    const stationCandidate = candidate as StationLookupCandidate;
    common.push(
      String(stationCandidate.station_id ?? ''),
      String(stationCandidate.station_name ?? '')
    );
  }
  if ('driver_name' in candidate) {
    const incidentCandidate = candidate as IncidentLookupCandidate;
    common.push(
      String(incidentCandidate.driver_name ?? ''),
      String(incidentCandidate.ppartition ?? ''),
      String(incidentCandidate.accident_date ?? '')
    );
  }
  return common.filter((item) => item.trim().length > 0);
}

function findCandidateByReply(
  state: PendingStructuredLookupState,
  userContent: string
): PendingStructuredLookupState['candidates'][number] | null {
  const trimmed = userContent.trim();
  const normalized = normalizeArgToken(trimmed);
  if (!normalized) return null;

  const indexMatch = normalized.match(/^(?:第)?([1234一二三四])(?:个|條|条|位|辆|台|线路|起|项)?$/);
  if (indexMatch) {
    const indexMap: Record<string, number> = {
      '1': 0,
      '2': 1,
      '3': 2,
      '4': 3,
      一: 0,
      二: 1,
      三: 2,
      四: 3,
    };
    const index = indexMap[indexMatch[1]];
    if (index != null) {
      return state.candidates[index] ?? null;
    }
  }

  const direct = state.candidates.find((candidate) =>
    getCandidateLookupTokens(candidate).some((token) => normalizeArgToken(token) === normalized)
  );
  if (direct) return direct;

  const embedded = state.candidates.find((candidate) =>
    getCandidateLookupTokens(candidate).some((token) => {
      const normalizedToken = normalizeArgToken(token);
      return normalized.includes(normalizedToken) || normalizedToken.includes(normalized);
    })
  );
  if (embedded) return embedded;

  if (state.candidates.length === 1 && AFFIRMATIVE_TOKENS.has(normalized)) {
    return state.candidates[0];
  }

  return null;
}

function resolvePendingToolCallFromState(
  state: PendingStructuredLookupState,
  candidateOrRawValue: string
): WorkerToolCall {
  if (state.kind === 'driver_report_lookup') {
    return {
      tool: 'generate_driver_report',
      args: { driver_name: candidateOrRawValue },
    };
  }
  if (state.kind === 'vehicle_report_lookup') {
    return {
      tool: 'generate_vehicle_report',
      args: { numberPlate: candidateOrRawValue },
    };
  }
  if (state.kind === 'unit_report_lookup') {
    return {
      tool: 'generate_unit_report',
      args: { organ_name: candidateOrRawValue },
    };
  }
  if (state.kind === 'route_report_lookup') {
    return {
      tool: 'generate_route_report',
      args: { route_name: candidateOrRawValue },
    };
  }
  if (state.kind === 'station_report_lookup') {
    return {
      tool: 'generate_station_report',
      args: { station_name: candidateOrRawValue },
    };
  }
  return {
    tool: 'generate_accident_investigation_report',
    args: { driver_name: candidateOrRawValue, accident_date: candidateOrRawValue },
  };
}

function getPendingRawValueFromCandidate(
  state: PendingStructuredLookupState,
  candidate: PendingStructuredLookupState['candidates'][number]
): string {
  if (state.kind === 'driver_report_lookup') {
    return String((candidate as DriverLookupCandidate).identifier ?? candidate.name);
  }
  if (state.kind === 'vehicle_report_lookup') {
    const vehicle = candidate as VehicleLookupCandidate;
    return String(vehicle.identifier ?? vehicle.name ?? vehicle.vehicle_id);
  }
  if (state.kind === 'unit_report_lookup') {
    const unit = candidate as UnitLookupCandidate;
    return String(unit.organ_id ?? unit.identifier ?? unit.name);
  }
  if (state.kind === 'route_report_lookup') {
    const route = candidate as RouteLookupCandidate;
    return String(route.route_id ?? route.identifier ?? route.route_name ?? route.name);
  }
  if (state.kind === 'station_report_lookup') {
    const station = candidate as StationLookupCandidate;
    return String(station.station_id ?? station.identifier ?? station.station_name ?? station.name);
  }
  const incident = candidate as IncidentLookupCandidate;
  return String(incident.driver_name ?? incident.identifier ?? incident.id);
}

function isFreshStructuredLookupRequest(content: string): boolean {
  return (
    content.startsWith(INTERNAL_WORKER_TOOL_PREFIX) ||
    content.startsWith(LEGACY_INTERNAL_STRUCTURED_TOOL_PREFIX) ||
    parseStructuredToolCallRecord(safeJsonParse(content)) !== null
  );
}

export async function rewritePendingStructuredLookupFollowUp(
  db: any,
  sessionId: string,
  userContent: string
): Promise<string | null> {
  const state = await getPendingStructuredLookupState(db, sessionId);
  if (!state) return null;

  const trimmed = userContent.trim();
  if (!trimmed) return null;
  if (isFreshStructuredLookupRequest(trimmed)) return null;

  const matchedCandidate = findCandidateByReply(state, trimmed);
  if (matchedCandidate) {
    return encodeInternalWorkerToolCall(
      resolvePendingToolCallFromState(
        state,
        getPendingRawValueFromCandidate(state, matchedCandidate)
      )
    );
  }

  const cleaned = cleanExtractedEntityToken(
    trimmed.replace(/^(就是|确认|确认是|我选|选择|选|用|看)\s*/u, '')
  );

  if (state.kind === 'driver_report_lookup') {
    if (
      cleaned &&
      !isInvalidDriverNameArg(cleaned) &&
      (state.reason === 'missing_name' || state.reason === 'too_short')
    ) {
      return encodeInternalWorkerToolCall(resolvePendingToolCallFromState(state, cleaned));
    }
    return null;
  }

  if (state.kind === 'vehicle_report_lookup') {
    if (
      cleaned &&
      !isInvalidVehicleIdArg(cleaned) &&
      (state.reason === 'missing_vehicle' || state.reason === 'too_short')
    ) {
      return encodeInternalWorkerToolCall(resolvePendingToolCallFromState(state, cleaned));
    }
    return null;
  }

  if (state.kind === 'unit_report_lookup') {
    if (
      cleaned &&
      !isInvalidUnitNameArg(cleaned) &&
      (state.reason === 'missing_unit' || state.reason === 'too_short')
    ) {
      return encodeInternalWorkerToolCall(resolvePendingToolCallFromState(state, cleaned));
    }
    return null;
  }

  if (state.kind === 'route_report_lookup') {
    if (
      cleaned &&
      !isInvalidRouteNameArg(cleaned) &&
      (state.reason === 'missing_route' || state.reason === 'too_short')
    ) {
      return encodeInternalWorkerToolCall(resolvePendingToolCallFromState(state, cleaned));
    }
    return null;
  }

  if (state.kind === 'station_report_lookup') {
    if (
      cleaned &&
      !isInvalidStationNameArg(cleaned) &&
      (state.reason === 'missing_station' || state.reason === 'too_short')
    ) {
      return encodeInternalWorkerToolCall(resolvePendingToolCallFromState(state, cleaned));
    }
    return null;
  }

  if (
    cleaned &&
    !isInvalidIncidentArg(cleaned) &&
    (state.reason === 'missing_driver_name' || state.reason === 'too_short')
  ) {
    return encodeInternalWorkerToolCall(resolvePendingToolCallFromState(state, cleaned));
  }

  return null;
}

export function buildPendingStructuredLookupState(
  tool: StructuredLookupToolName,
  resolution:
    | DriverLookupResolution
    | VehicleLookupResolution
    | UnitLookupResolution
    | RouteLookupResolution
    | StationLookupResolution
    | IncidentLookupResolution
): PendingStructuredLookupState | null {
  if (resolution.kind === 'resolved') return null;
  if (tool === 'generate_driver_report') {
    return {
      kind: 'driver_report_lookup',
      reason: resolution.reason,
      query: resolution.query,
      candidates: resolution.candidates as DriverLookupCandidate[],
    };
  }
  if (tool === 'generate_vehicle_report') {
    return {
      kind: 'vehicle_report_lookup',
      reason: resolution.reason as PendingVehicleLookupState['reason'],
      query: resolution.query,
      candidates: resolution.candidates as VehicleLookupCandidate[],
    };
  }
  if (tool === 'generate_unit_report') {
    return {
      kind: 'unit_report_lookup',
      reason: resolution.reason as PendingUnitLookupState['reason'],
      query: resolution.query,
      candidates: resolution.candidates as UnitLookupCandidate[],
    };
  }
  if (tool === 'generate_route_report') {
    return {
      kind: 'route_report_lookup',
      reason: resolution.reason as PendingRouteLookupState['reason'],
      query: resolution.query,
      candidates: resolution.candidates as RouteLookupCandidate[],
    };
  }
  if (tool === 'generate_station_report') {
    return {
      kind: 'station_report_lookup',
      reason: resolution.reason as PendingStationLookupState['reason'],
      query: resolution.query,
      candidates: resolution.candidates as StationLookupCandidate[],
    };
  }
  return {
    kind: 'incident_report_lookup',
    reason: resolution.reason as PendingIncidentLookupState['reason'],
    query: resolution.query,
    candidates: resolution.candidates as IncidentLookupCandidate[],
  };
}

export function buildMissingStructuredLookupState(
  tool: StructuredLookupToolName
): PendingStructuredLookupState {
  if (tool === 'generate_driver_report') {
    return { kind: 'driver_report_lookup', reason: 'missing_name', query: '', candidates: [] };
  }
  if (tool === 'generate_vehicle_report') {
    return { kind: 'vehicle_report_lookup', reason: 'missing_vehicle', query: '', candidates: [] };
  }
  if (tool === 'generate_unit_report') {
    return { kind: 'unit_report_lookup', reason: 'missing_unit', query: '', candidates: [] };
  }
  if (tool === 'generate_route_report') {
    return { kind: 'route_report_lookup', reason: 'missing_route', query: '', candidates: [] };
  }
  if (tool === 'generate_station_report') {
    return { kind: 'station_report_lookup', reason: 'missing_station', query: '', candidates: [] };
  }
  return {
    kind: 'incident_report_lookup',
    reason: 'missing_driver_name',
    query: '',
    candidates: [],
  };
}

export function extractStructuredLookupDisplayName(
  tool: StructuredLookupToolName,
  resolution:
    | DriverLookupResolution
    | VehicleLookupResolution
    | UnitLookupResolution
    | RouteLookupResolution
    | StationLookupResolution
    | IncidentLookupResolution
): string {
  if (resolution.kind !== 'resolved') {
    return '';
  }

  if (tool === 'generate_driver_report') {
    return resolution.candidate.name;
  }
  if (tool === 'generate_vehicle_report') {
    return (
      readFirstStringAtPaths(resolution.data, ['basic.plate_number']) ??
      resolution.candidate.identifier ??
      resolution.candidate.name
    );
  }
  if (tool === 'generate_unit_report') {
    return (
      readFirstStringAtPaths(resolution.data, ['basic.organ_name', 'name']) ??
      (resolution.candidate as UnitLookupCandidate).name
    );
  }
  if (tool === 'generate_route_report') {
    const routeCandidate = resolution.candidate as RouteLookupCandidate;
    return (
      readFirstStringAtPaths(resolution.data, ['basic.route_name', 'route_name']) ??
      routeCandidate.route_name ??
      routeCandidate.name
    );
  }
  if (tool === 'generate_station_report') {
    const stationCandidate = resolution.candidate as StationLookupCandidate;
    return (
      readFirstStringAtPaths(resolution.data, ['basic.station_name', 'station_name']) ??
      stationCandidate.station_name ??
      stationCandidate.name
    );
  }
  return (
    readFirstStringAtPaths(resolution.data, ['basic.report_title']) ?? resolution.candidate.name
  );
}

export function getStructuredLookupSummary(
  tool: StructuredLookupToolName,
  resolution:
    | DriverLookupResolution
    | VehicleLookupResolution
    | UnitLookupResolution
    | RouteLookupResolution
    | StationLookupResolution
    | IncidentLookupResolution
): Record<string, unknown> {
  if (resolution.kind === 'resolved') {
    return {
      kind: resolution.kind,
      query: resolution.query,
      match_type: resolution.matchType,
      candidate: resolution.candidate,
      label: extractStructuredLookupDisplayName(tool, resolution),
    };
  }

  return {
    kind: resolution.kind,
    query: resolution.query,
    reason: resolution.reason,
    candidates: resolution.candidates,
  };
}

export function readStringValueAtPaths(
  source: Record<string, unknown>,
  paths: string[]
): string | null {
  for (const path of paths) {
    const value = getNestedValue(source, path);
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}
