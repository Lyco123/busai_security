import { isRecord } from './guards';
import { callMcpToolDebug, callMcpToolForAgent } from './mcp';
import { extractMessageSources, withMessageSources } from './message-sources';
import {
  buildQuotaItemIndex,
  normalizeQuotaTreeCount,
  pickTopLeafQuotaItemsByRoot,
  PROFILE_COUNT_SEMANTICS,
  PROFILE_RISK_SCORE_SEMANTICS,
  PROFILE_SOURCE_SCORE_SEMANTICS,
  PROFILE_SUGGESTION_SCORE_SEMANTICS,
  PROFILE_WEIGHTED_VALUE_SEMANTICS,
  resolveProfileFinalRiskScore,
  resolveQuotaDimensionByRoots,
} from './profile-quota-tree';
import { normalizeGuangdongVehiclePlate } from './vehicle-plate-normalizer';

const VEHICLE_PROFILE_TOOL_NAME = 'get_mcp_base_absBusProfileMain_queryByNumberplate';
const VEHICLE_RISK_SCORE_TOOL_NAME = 'get_mcp_base_absBusProfileMain_busRiskScore';
const VEHICLE_SUGGESTION_TOOL_NAME = 'get_mcp_suggest_absBusSuggestedSub_queryByBusNameAndDate';
const SHANGHAI_TIME_ZONE = 'Asia/Shanghai';
const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';
const FAULT_ROOT_ID = '车辆画像-故障风险';
const ENERGY_ROOT_ID = '车辆画像-能耗风险';
const OVERALL_DIMENSION = '综合风险';
const FAULT_DIMENSION = '故障风险';
const ENERGY_DIMENSION = '能耗风险';

type EnvLike = {
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
};

export type VehicleProfileLookupTrace = {
  tool_name: string;
  request: {
    numberplate: string;
    ppartition?: string;
  };
  configured: boolean;
  ok: boolean;
  error?: string;
  target_url: string | null;
  protocol_version: string;
  total_duration_ms: number;
  timestamp: string;
  stages: Array<{
    stage: string;
    ok: boolean;
    duration_ms: number;
    http_status: number | null;
    error?: string;
  }>;
  result_summary?: {
    kind: 'empty' | 'invalid_payload' | 'business_data';
    has_result: boolean;
    has_main: boolean;
    main_partition?: string;
    main_numberplate?: string;
  };
};

export type VehicleProfileFetchResult = {
  data: Record<string, unknown> | null;
  trace: VehicleProfileLookupTrace;
};

type VehicleProfileQuotaItem = {
  quotaName: string;
  score: number | null;
  quotaLevel: string | null;
  parentId: string | null;
  quotaId: string | null;
  weightRate: number | null;
  originalValue: number | null;
  ranking: number | null;
};

type VehicleSuggestionItem = {
  quotaName: string;
  suggestedContent: string;
  score: number | null;
  firstQuotaName: string | null;
  suggestedDate: string | null;
  acceptStatus: string | null;
  disposeStatus: string | null;
};

type VehicleRiskScoreItem = {
  quotaId: string | null;
  quotaName: string;
  currentRiskValue: number | null;
  previousPeriodRiskValue: number | null;
  lastYearSameDateRiskValue: number | null;
  organAvgRiskValue: number | null;
  routeAvgRiskValue: number | null;
  convertedScore: number | null;
  previousPeriodScore: number | null;
  lastYearSameDateScore: number | null;
  organAvgScore: number | null;
  routeAvgScore: number | null;
};

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function toStringValue(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function deriveRiskLevel(score: number | null): string | null {
  if (score == null) return null;
  if (score >= 80) return '高风险';
  if (score >= 60) return '中风险';
  if (score >= 40) return '关注';
  return '低风险';
}

function buildPartition(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: SHANGHAI_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const year = parts.find((item) => item.type === 'year')?.value ?? '';
  const month = parts.find((item) => item.type === 'month')?.value ?? '';
  const day = parts.find((item) => item.type === 'day')?.value ?? '';
  return `${year}${month}${day}`;
}

function normalizeNumberplate(value: string): string {
  return normalizeGuangdongVehiclePlate(value);
}

export function extractVehicleProfilePartitionFromText(
  value: string | null | undefined,
  fallback = buildPartition()
): string {
  const text = String(value ?? '').trim();
  if (!text) return fallback;

  const compact = text.match(/\b(20\d{2})(\d{2})(\d{2})\b/);
  if (compact) {
    return `${compact[1]}${compact[2]}${compact[3]}`;
  }

  const dashed = text.match(/\b(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})(?:日|号)?\b/);
  if (dashed) {
    const [, year, month, day] = dashed;
    return `${year}${month.padStart(2, '0')}${day.padStart(2, '0')}`;
  }

  return fallback;
}

function normalizeQuotaItems(value: unknown): VehicleProfileQuotaItem[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      quotaName: toStringValue(item.quotaName) ?? '',
      score: toNumber(item.score),
      quotaLevel: toStringValue(item.quotaLevel),
      parentId: toStringValue(item.parentId),
      quotaId: toStringValue(item.quotaId),
      weightRate: toNumber(item.weightRate),
      originalValue: toNumber(item.originalValue),
      ranking: toNumber(item.ranking),
    }))
    .filter((item) => item.quotaName && item.quotaId);
}

function pickTopIndicators(items: VehicleProfileQuotaItem[], rootId: string, limit: number): VehicleProfileQuotaItem[] {
  return pickTopLeafQuotaItemsByRoot(items, rootId, limit);
}

function buildDimensionRecord(
  score: number | null,
  indicators: VehicleProfileQuotaItem[],
  ranking: number | null
): Record<string, unknown> {
  const indicatorNames = indicators.map((item) => item.quotaName);
  return {
    ...(score != null ? { score } : {}),
    ...(ranking != null ? { rank_position: ranking } : {}),
    trend_text: '—',
    core_risk_indicators: indicatorNames,
    ...(indicatorNames[0] ? { top_indicator: indicatorNames[0] } : {}),
    ...(score != null ? { alert_count: Math.max(1, Math.round(score / 20)) } : {}),
  };
}

function computeOverallScore(mainScore: number | null): number | null {
  return mainScore != null ? Number(mainScore.toFixed(2)) : null;
}

function buildFallbackRecommendations(
  indicators: VehicleProfileQuotaItem[],
  suggestionItems: VehicleSuggestionItem[] = []
): Array<Record<string, unknown>> {
  if (suggestionItems.length > 0) {
    return suggestionItems.slice(0, 4).map((item, index) => ({
      priority: index + 1,
      indicator: item.quotaName,
      action: item.suggestedContent,
      expected_effect: '',
      source: 'mcp_suggested_sub',
      ...(item.score != null ? { score: item.score } : {}),
      ...(item.firstQuotaName ? { dimension: item.firstQuotaName } : {}),
      ...(item.suggestedDate ? { suggested_date: item.suggestedDate } : {}),
    }));
  }

  return indicators.slice(0, 4).map((item, index) => ({
    priority: index + 1,
    indicator: item.quotaName,
    action: NO_MANAGEMENT_SUGGESTION_TEXT,
    expected_effect: '',
    source: 'no_management_suggestion',
  }));
}

function normalizeVehicleSuggestionItems(value: unknown): VehicleSuggestionItem[] {
  const rawItems = isRecord(value) && Array.isArray(value.result) ? value.result : Array.isArray(value) ? value : [];
  return rawItems
    .filter(isRecord)
    .map((item) => ({
      quotaName: toStringValue(item.quotaName) ?? '',
      suggestedContent: toStringValue(item.suggestedContent) ?? '',
      score: toNumber(item.score),
      firstQuotaName: toStringValue(item.firstQuotaName),
      suggestedDate: toStringValue(item.suggestedDate),
      acceptStatus: toStringValue(item.acceptStatu_dictText) ?? toStringValue(item.acceptStatu),
      disposeStatus: toStringValue(item.disposeStatu_dictText) ?? toStringValue(item.disposeStatu),
    }))
    .filter((item) => item.quotaName && item.suggestedContent)
    .sort((left, right) => (right.score ?? -Infinity) - (left.score ?? -Infinity))
    .filter(
      (item, index, array) =>
        array.findIndex((candidate) => candidate.quotaName === item.quotaName) === index
    );
}

function normalizeVehicleRiskScoreItems(value: unknown): VehicleRiskScoreItem[] {
  const rawItems =
    isRecord(value) && Array.isArray(value.result) ? value.result : Array.isArray(value) ? value : [];
  return rawItems
    .filter(isRecord)
    .map((item) => ({
      quotaId: toStringValue(item.quotaId),
      quotaName: toStringValue(item.quotaName) ?? '',
      currentRiskValue: toNumber(item.currentRiskValue),
      previousPeriodRiskValue: toNumber(item.previousPeriodRiskValue),
      lastYearSameDateRiskValue: toNumber(item.lastYearSameDateRiskValue),
      organAvgRiskValue: toNumber(item.organAvgRiskValue),
      routeAvgRiskValue: toNumber(item.routeAvgRiskValue),
      convertedScore: toNumber(item.convertedScore),
      previousPeriodScore: toNumber(item.previousPeriodScore),
      lastYearSameDateScore: toNumber(item.lastYearSameDateScore),
      organAvgScore: toNumber(item.organAvgScore),
      routeAvgScore: toNumber(item.routeAvgScore),
    }))
    .filter((item) => item.quotaId || item.quotaName);
}

function formatTrendMetric(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const normalized = Number(value.toFixed(2));
  return `${normalized > 0 ? '+' : ''}${String(normalized).replace(/\.00$/, '')}%`;
}

function buildRiskScoreTrendText(item: VehicleRiskScoreItem | null): string {
  if (!item) return '—';
  return `同比${formatTrendMetric(item.lastYearSameDateRiskValue)}，环比${formatTrendMetric(
    item.previousPeriodRiskValue
  )}，同单位比${formatTrendMetric(item.organAvgRiskValue)}，同线路比${formatTrendMetric(
    item.routeAvgRiskValue
  )}`;
}

function buildRiskScoreMap(items: VehicleRiskScoreItem[]): Map<string, VehicleRiskScoreItem> {
  const trendMap = new Map<string, VehicleRiskScoreItem>();
  for (const item of items) {
    if (item.quotaId) trendMap.set(item.quotaId, item);
    if (item.quotaName) trendMap.set(item.quotaName, item);
  }
  return trendMap;
}

function buildCompactQuotaSummary(
  label: string,
  root: VehicleProfileQuotaItem | null,
  indicators: VehicleProfileQuotaItem[]
): Record<string, unknown> {
  return {
    dimension: label,
    ...(root ? { score: resolveProfileFinalRiskScore(root) } : {}),
    ...(root?.score != null ? { source_score: root.score } : {}),
    ...(root?.originalValue != null ? { original_value: root.originalValue } : {}),
    ...(root?.ranking != null ? { ranking: root.ranking } : {}),
    indicators: indicators.map((item) => ({
      name: item.quotaName,
      ...(item.originalValue != null || item.score != null
        ? { score: resolveProfileFinalRiskScore(item) }
        : {}),
      ...(item.score != null ? { source_score: item.score } : {}),
      ...(item.originalValue != null ? { original_value: item.originalValue } : {}),
      ...(item.weightRate != null ? { weight: item.weightRate } : {}),
    })),
  };
}

function buildLookupTrace(input: {
  debugResult: Awaited<ReturnType<typeof callMcpToolDebug>>;
  request: {
    numberplate: string;
    ppartition?: string;
  };
  rawResult: unknown;
}): VehicleProfileLookupTrace {
  const rawRecord =
    input.rawResult && typeof input.rawResult === 'object' && !Array.isArray(input.rawResult)
      ? (input.rawResult as Record<string, unknown>)
      : null;
  const rawPayload =
    rawRecord?.result && typeof rawRecord.result === 'object' && !Array.isArray(rawRecord.result)
      ? (rawRecord.result as Record<string, unknown>)
      : rawRecord;
  const rawMain =
    rawPayload?.main && typeof rawPayload.main === 'object' && !Array.isArray(rawPayload.main)
      ? (rawPayload.main as Record<string, unknown>)
      : null;

  return {
    tool_name: VEHICLE_PROFILE_TOOL_NAME,
    request: input.request,
    configured: input.debugResult.configured,
    ok: input.debugResult.ok,
    ...(input.debugResult.error ? { error: input.debugResult.error } : {}),
    target_url: input.debugResult.target_url,
    protocol_version: input.debugResult.protocol_version,
    total_duration_ms: input.debugResult.total_duration_ms,
    timestamp: input.debugResult.timestamp,
    stages: input.debugResult.stages.map((stage) => ({
      stage: stage.stage,
      ok: stage.ok,
      duration_ms: stage.duration_ms,
      http_status: stage.http_status,
      ...(stage.error ? { error: stage.error } : {}),
    })),
    result_summary: {
      kind: !rawRecord ? 'empty' : rawMain ? 'business_data' : 'invalid_payload',
      has_result: Boolean(rawRecord?.result),
      has_main: Boolean(rawMain),
      ...(toStringValue(rawMain?.ppartition) ? { main_partition: toStringValue(rawMain?.ppartition)! } : {}),
      ...(toStringValue(rawMain?.numberPlate) ? { main_numberplate: toStringValue(rawMain?.numberPlate)! } : {}),
    },
  };
}

function buildVehicleProfilePayload(
  rawResult: Record<string, unknown>,
  trimmedPlate: string,
  resolvedPartition: string | null,
  suggestionResult?: unknown,
  riskScoreResult?: unknown
): Record<string, unknown> | null {
  if (!isRecord(rawResult.main)) {
    return null;
  }

  const main = rawResult.main;
  const quotaItems = normalizeQuotaItems(rawResult.quotaScoreSubList);
  const rootConfigs = [
    { dimension: FAULT_DIMENSION, rootId: FAULT_ROOT_ID },
    { dimension: ENERGY_DIMENSION, rootId: ENERGY_ROOT_ID },
  ] as const;
  const itemById = buildQuotaItemIndex(quotaItems);
  const faultRoot = quotaItems.find((item) => item.quotaLevel === '1' && item.quotaId === FAULT_ROOT_ID) ?? null;
  const energyRoot = quotaItems.find((item) => item.quotaLevel === '1' && item.quotaId === ENERGY_ROOT_ID) ?? null;
  const faultIndicators = pickTopIndicators(quotaItems, FAULT_ROOT_ID, 3);
  const energyIndicators = pickTopIndicators(quotaItems, ENERGY_ROOT_ID, 3);
  const overallIndicators = [...faultIndicators, ...energyIndicators]
    .filter(
      (item, index, array) =>
        array.findIndex((candidate) => candidate.quotaName === item.quotaName) === index
    )
    .sort((left, right) => {
      const scoreDelta =
        (resolveProfileFinalRiskScore(right) ?? Number.NEGATIVE_INFINITY) -
        (resolveProfileFinalRiskScore(left) ?? Number.NEGATIVE_INFINITY);
      if (scoreDelta !== 0) return scoreDelta;
      return (right.score ?? Number.NEGATIVE_INFINITY) - (left.score ?? Number.NEGATIVE_INFINITY);
    })
    .slice(0, 4);
  const mainEvaluationType = toStringValue(main.evalutaionType);
  const overallScore = computeOverallScore(toNumber(main.score));
  const overallLevel = mainEvaluationType ?? deriveRiskLevel(overallScore);
  const reportDate = toStringValue(main.ppartition) ?? resolvedPartition ?? 'latest';
  const plateNumber = toStringValue(main.numberPlate) ?? toStringValue(main.busName) ?? trimmedPlate;
  const vehicleId = toStringValue(main.busId) ?? plateNumber;
  const suggestionItems = normalizeVehicleSuggestionItems(suggestionResult);
  const riskScoreItems = normalizeVehicleRiskScoreItems(riskScoreResult);
  const riskScoreMap = buildRiskScoreMap(riskScoreItems);
  const faultTrend = riskScoreMap.get(FAULT_ROOT_ID) ?? riskScoreMap.get(FAULT_DIMENSION) ?? null;
  const energyTrend = riskScoreMap.get(ENERGY_ROOT_ID) ?? riskScoreMap.get(ENERGY_DIMENSION) ?? null;
  const overallTrend = riskScoreItems[0] ?? null;
  const rankPosition = toNumber(main.ranking);
  const rankTotal = toNumber(main.evalutaionTypeCount);
  const rankPercent = toNumber(main.evalutaionTypePercent);

  return {
    id: plateNumber,
    name: plateNumber,
    identifier: plateNumber,
    basic: {
      plate_number: plateNumber,
      vehicle_id: vehicleId,
      display_name: toStringValue(main.busName) ?? plateNumber,
      fleet_name: toStringValue(main.organName),
      route_name: toStringValue(main.routeName),
    },
    performance_dashboard: {
      summary: {
        overall_score: overallScore,
        overall_level: overallLevel,
        level_source: mainEvaluationType ? 'main.evalutaionType' : 'derived_from_main.score',
        score_source: 'main.score',
      },
      dimensions: {
        [OVERALL_DIMENSION]: {
          ...buildDimensionRecord(overallScore, overallIndicators, rankPosition),
          trend_text: buildRiskScoreTrendText(overallTrend),
          ...(rankTotal != null ? { rank_total: rankTotal } : {}),
          ...(rankPercent != null ? { percentile: rankPercent } : {}),
          ...(rankPosition != null && rankTotal != null
            ? { display: `排名 ${rankPosition}/${rankTotal}` }
            : {}),
        },
        [FAULT_DIMENSION]: {
          ...buildDimensionRecord(
            faultRoot ? resolveProfileFinalRiskScore(faultRoot) : null,
            faultIndicators,
            faultRoot?.ranking ?? null
          ),
          trend_text: buildRiskScoreTrendText(faultTrend),
        },
        [ENERGY_DIMENSION]: {
          ...buildDimensionRecord(
            energyRoot ? resolveProfileFinalRiskScore(energyRoot) : null,
            energyIndicators,
            energyRoot?.ranking ?? null
          ),
          trend_text: buildRiskScoreTrendText(energyTrend),
        },
      },
      system_risk: {
        level: overallLevel,
        tags: overallIndicators.map((item) => item.quotaName),
      },
    },
    interventions: {
      recommendations: buildFallbackRecommendations(overallIndicators, suggestionItems),
    },
    appendix: {
      raw_data: {
        source: `mcp:${VEHICLE_PROFILE_TOOL_NAME}`,
        partition: reportDate,
        source_window: {
          as_of: reportDate,
          window_days: 7,
        },
        main: {
          ppartition: reportDate,
          bus_name: toStringValue(main.busName),
          number_plate: toStringValue(main.numberPlate),
          route_name: toStringValue(main.routeName),
          organ_name: toStringValue(main.organName),
          score: toNumber(main.score),
          evalutaion_type: mainEvaluationType,
          ranking: rankPosition,
          ranking_total: rankTotal,
          ranking_percentile: rankPercent,
        },
        ranking_snapshot: {
          ...(rankPosition != null ? { rank_position: rankPosition } : {}),
          ...(rankTotal != null ? { rank_total: rankTotal } : {}),
          ...(rankPercent != null ? { percentile: rankPercent } : {}),
          ...(rankPosition != null && rankTotal != null
            ? { display: `排名 ${rankPosition}/${rankTotal}` }
            : {}),
        },
        suggestion_counts: {
          pending_receive_count: toNumber(main.pendingReceiveCount),
          pending_confirm_count: toNumber(main.pendingConfirmCount),
          pending_optimize_count: toNumber(main.pendingOptimizeCount),
        },
        quota_summary: [
          {
            ...buildCompactQuotaSummary(FAULT_DIMENSION, faultRoot, faultIndicators),
            trend_text: buildRiskScoreTrendText(faultTrend),
          },
          {
            ...buildCompactQuotaSummary(ENERGY_DIMENSION, energyRoot, energyIndicators),
            trend_text: buildRiskScoreTrendText(energyTrend),
          },
        ],
        ...(riskScoreItems.length > 0
          ? {
              trend_summary: riskScoreItems.map((item) => ({
                quota_id: item.quotaId,
                quota_name: item.quotaName,
                current_risk_value: item.currentRiskValue,
                converted_score: item.convertedScore,
                previous_period_risk_value: item.previousPeriodRiskValue,
                last_year_same_date_risk_value: item.lastYearSameDateRiskValue,
                organ_avg_risk_value: item.organAvgRiskValue,
                route_avg_risk_value: item.routeAvgRiskValue,
                previous_period_score: item.previousPeriodScore,
                last_year_same_date_score: item.lastYearSameDateScore,
                organ_avg_score: item.organAvgScore,
                route_avg_score: item.routeAvgScore,
                trend_text: buildRiskScoreTrendText(item),
              })),
            }
          : {}),
        score_semantics: PROFILE_SOURCE_SCORE_SEMANTICS,
        final_score_semantics: PROFILE_RISK_SCORE_SEMANTICS,
        quota_value_notes: {
          score: PROFILE_SOURCE_SCORE_SEMANTICS,
          source_score: PROFILE_SOURCE_SCORE_SEMANTICS,
          risk_score: PROFILE_RISK_SCORE_SEMANTICS,
          final_risk_score: PROFILE_RISK_SCORE_SEMANTICS,
          original_value: PROFILE_WEIGHTED_VALUE_SEMANTICS,
          count: PROFILE_COUNT_SEMANTICS,
        },
        quota_items: quotaItems.map((item) => ({
          quota_id: item.quotaId,
          quota_name: item.quotaName,
          quota_level: item.quotaLevel,
          parent_id: item.parentId,
          dimension: resolveQuotaDimensionByRoots(item, itemById, rootConfigs),
          score: item.score,
          source_score: item.score,
          score_semantics: PROFILE_SOURCE_SCORE_SEMANTICS,
          count: normalizeQuotaTreeCount(item.originalValue),
          original_value: item.originalValue,
          final_risk_score: resolveProfileFinalRiskScore(item),
          risk_score: resolveProfileFinalRiskScore(item),
          final_score_semantics: PROFILE_RISK_SCORE_SEMANTICS,
          ranking: item.ranking,
          weight: item.weightRate,
        })),
        ...(suggestionItems.length > 0
          ? {
              suggestions: suggestionItems.map((item) => ({
                quota_name: item.quotaName,
                suggested_content: item.suggestedContent,
                score: item.score,
                risk_score: item.score,
                score_semantics: PROFILE_SUGGESTION_SCORE_SEMANTICS,
                first_quota_name: item.firstQuotaName,
                suggested_date: item.suggestedDate,
                accept_status: item.acceptStatus,
                dispose_status: item.disposeStatus,
              })),
            }
          : {}),
      },
    },
  };
}

function extractVehicleProfileToolPayload(value: unknown): Record<string, unknown> | null {
  if (!isRecord(value)) return null;
  if (isRecord(value.result)) return value.result as Record<string, unknown>;
  return value;
}

export function adaptVehicleProfileToolResult(
  rawResult: unknown,
  numberplate: string,
  partition?: string | null,
  suggestionResult?: unknown,
  riskScoreResult?: unknown
): Record<string, unknown> | null {
  const normalizedPayload = extractVehicleProfileToolPayload(rawResult);
  if (!normalizedPayload) {
    return null;
  }

  const vehicleProfilePayload = buildVehicleProfilePayload(
    normalizedPayload,
    normalizeNumberplate(numberplate),
    toStringValue(partition),
    suggestionResult,
    riskScoreResult
  );
  if (!vehicleProfilePayload) {
    return null;
  }

  return withMessageSources(vehicleProfilePayload, extractMessageSources(rawResult, 'mcp'));
}

export async function fetchVehicleProfileByNumberplateWithTrace(
  env: EnvLike,
  numberplate: string,
  partition?: string | null
): Promise<VehicleProfileFetchResult> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  const trimmedPlate = normalizeNumberplate(numberplate);
  const resolvedPartition = toStringValue(partition);
  if (!serverUrl || !trimmedPlate) {
    return {
      data: null,
      trace: {
        tool_name: VEHICLE_PROFILE_TOOL_NAME,
        request: {
          numberplate: trimmedPlate,
          ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
        },
        configured: false,
        ok: false,
        error: 'MCP_SERVER_URL is not configured',
        target_url: serverUrl || null,
        protocol_version: '2025-03-26',
        total_duration_ms: 0,
        timestamp: new Date().toISOString(),
        stages: [],
        result_summary: {
          kind: 'empty',
          has_result: false,
          has_main: false,
        },
      },
    };
  }

  const debugResult = await callMcpToolDebug(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    VEHICLE_PROFILE_TOOL_NAME,
    {
      numberPlate: trimmedPlate,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  const normalizedResult =
    debugResult.ok && isRecord(debugResult.result) ? debugResult.result : null;

  const normalizedPayload =
    debugResult.ok && isRecord(debugResult.result)
      ? (isRecord(debugResult.result.result) ? (debugResult.result.result as Record<string, unknown>) : debugResult.result)
      : null;

  const suggestionDebugResult =
    debugResult.ok && normalizedPayload
      ? await callMcpToolDebug(
          {
            serverUrl,
            clientId: env.CF_ACCESS_CLIENT_ID,
            clientSecret: env.CF_ACCESS_CLIENT_SECRET,
            accessToken: env.MCP_ACCESS_TOKEN,
          },
          VEHICLE_SUGGESTION_TOOL_NAME,
          {
            numberPlate: trimmedPlate,
            ...(resolvedPartition ? { partition: resolvedPartition } : {}),
          }
        )
      : null;

  const riskScoreDebugResult =
    debugResult.ok && normalizedPayload
      ? await callMcpToolDebug(
          {
            serverUrl,
            clientId: env.CF_ACCESS_CLIENT_ID,
            clientSecret: env.CF_ACCESS_CLIENT_SECRET,
            accessToken: env.MCP_ACCESS_TOKEN,
          },
          VEHICLE_RISK_SCORE_TOOL_NAME,
          {
            numberplate: trimmedPlate,
            ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
          }
        )
      : null;

  const vehicleProfilePayload =
    normalizedPayload != null
      ? buildVehicleProfilePayload(
          normalizedPayload,
          trimmedPlate,
          resolvedPartition,
          suggestionDebugResult?.ok ? suggestionDebugResult.result : null,
          riskScoreDebugResult?.ok ? riskScoreDebugResult.result : null
        )
      : null;

  return {
    data:
      vehicleProfilePayload && normalizedResult
        ? withMessageSources(vehicleProfilePayload, extractMessageSources(normalizedResult, 'mcp'))
        : vehicleProfilePayload,
    trace: buildLookupTrace({
      debugResult,
      request: {
        numberplate: trimmedPlate,
        ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
      },
      rawResult: debugResult.raw_result,
    }),
  };
}

export async function fetchVehicleProfileByNumberplate(
  env: EnvLike,
  numberplate: string,
  partition?: string | null
): Promise<Record<string, unknown> | null> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  const trimmedPlate = normalizeNumberplate(numberplate);
  const resolvedPartition = toStringValue(partition);
  if (!serverUrl || !trimmedPlate) {
    return null;
  }

  const result = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    VEHICLE_PROFILE_TOOL_NAME,
    {
      numberPlate: trimmedPlate,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  if (!result.success) {
    return null;
  }

  const suggestionResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    VEHICLE_SUGGESTION_TOOL_NAME,
    {
      numberPlate: trimmedPlate,
      ...(resolvedPartition ? { partition: resolvedPartition } : {}),
    }
  );

  const riskScoreResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    VEHICLE_RISK_SCORE_TOOL_NAME,
    {
      numberplate: trimmedPlate,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  return adaptVehicleProfileToolResult(
    result.data,
    trimmedPlate,
    resolvedPartition,
    suggestionResult.success ? suggestionResult.data : null,
    riskScoreResult.success ? riskScoreResult.data : null
  );
}

export function getDefaultVehicleProfilePartition(): string {
  return buildPartition();
}
