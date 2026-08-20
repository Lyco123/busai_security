import { isRecord } from './guards';
import { getStandardRouteName } from './entity-alias-resolver';
import { callMcpToolForAgent } from './mcp';
import {
  buildQuotaChildrenIndex,
  buildQuotaItemIndex,
  isLeafQuotaTreeItem,
  normalizeQuotaTreeCount,
  PROFILE_COUNT_SEMANTICS,
  PROFILE_RISK_SCORE_SEMANTICS,
  PROFILE_SOURCE_SCORE_SEMANTICS,
  PROFILE_SUGGESTION_SCORE_SEMANTICS,
  PROFILE_WEIGHTED_VALUE_SEMANTICS,
  resolveProfileFinalRiskScore,
} from './profile-quota-tree';

const ROUTE_PROFILE_TOOL_NAME = 'get_mcp_base_absRouteProfileMain_queryRouteProfile';
const ROUTE_RISK_SCORE_TOOL_NAME = 'get_mcp_base_absRouteProfileMain_routeRiskScore';
const ROUTE_SUGGESTION_TOOL_NAME = 'get_mcp_suggest_absRouteSuggestedSub_queryByRouteNameAndDate';
const SHANGHAI_TIME_ZONE = 'Asia/Shanghai';
const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';
const OVERALL_DIMENSION = '综合风险';
const STATIC_DIMENSION = '静态风险';
const DYNAMIC_DIMENSION = '动态风险';

type EnvLike = {
  DB?: any;
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
};

type RouteProfileQuotaItem = {
  quotaName: string;
  score: number | null;
  quotaLevel: string | null;
  parentId: string | null;
  quotaId: string | null;
  originalValue: number | null;
  ranking: number | null;
  firstQuotaName: string | null;
};

type RouteIndicatorSummary = {
  name: string;
  score: number | null;
  count: number | null;
  quotaLevel: string | null;
  quotaId: string | null;
  parentId: string | null;
};

type RouteSuggestionItem = {
  quotaName: string;
  suggestedContent: string;
  score: number | null;
  firstQuotaName: string | null;
  quotaLevel: string | null;
  suggestedDate: string | null;
  acceptStatus: string | null;
  disposeStatus: string | null;
};

type RouteRiskScoreItem = {
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

function normalizeDateForReport(value: string | null): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;
  const partitionMatch = trimmed.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (partitionMatch) return `${partitionMatch[1]}-${partitionMatch[2]}-${partitionMatch[3]}`;
  return trimmed;
}

function toStringValue(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function simplifyText(value: string | null): string {
  return String(value ?? '')
    .replace(/\s+/g, '')
    .trim();
}

function normalizeIndicatorCount(value: number | null): number | null {
  return normalizeQuotaTreeCount(value);
}

function deriveRouteRiskLevel(score: number | null): string | null {
  if (score == null) return null;
  if (score >= 65) return '危险';
  if (score >= 55) return '关注';
  if (score >= 45) return '观察';
  return '安全';
}

function buildTrendText(): string {
  return '同比—，环比—，同单位比—';
}

function normalizeRouteRiskScoreItems(value: unknown): RouteRiskScoreItem[] {
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

function buildRiskScoreTrendText(item: RouteRiskScoreItem | null): string {
  if (!item) return buildTrendText();
  return `同比${formatTrendMetric(item.lastYearSameDateRiskValue)}，环比${formatTrendMetric(
    item.previousPeriodRiskValue
  )}，同单位比${formatTrendMetric(item.organAvgRiskValue)}`;
}

function buildRiskScoreMap(items: RouteRiskScoreItem[]): Map<string, RouteRiskScoreItem> {
  const trendMap = new Map<string, RouteRiskScoreItem>();
  for (const item of items) {
    if (item.quotaId) trendMap.set(item.quotaId, item);
    if (item.quotaName) trendMap.set(item.quotaName, item);
  }
  return trendMap;
}

function buildDimensionRecord(input: {
  score: number | null;
  indicators: RouteIndicatorSummary[];
  ranking: number | null;
}): Record<string, unknown> {
  const topIndicator = input.indicators[0] ?? null;
  return {
    ...(input.score != null ? { score: Number(input.score.toFixed(2)) } : {}),
    ...(input.ranking != null ? { rank_position: input.ranking } : {}),
    trend_text: buildTrendText(),
    core_risk_indicators: input.indicators.map((item) => item.name),
    ...(topIndicator?.name ? { top_indicator: topIndicator.name } : {}),
    ...(topIndicator?.count != null ? { alert_count: topIndicator.count } : {}),
  };
}

function computeOverallScore(mainScore: number | null): number | null {
  return mainScore != null ? Number(mainScore.toFixed(2)) : null;
}

function normalizeEvaluationType(value: unknown): string | null {
  const text = toStringValue(value);
  if (!text) return null;
  const normalized = simplifyText(text);
  if (!normalized) return null;
  if (normalized.includes('危险') || normalized.includes('高风险')) return '危险';
  if (normalized.includes('关注') || normalized.includes('中风险')) return '关注';
  if (normalized.includes('观察') || normalized.includes('低风险')) return '观察';
  if (normalized.includes('安全') || normalized.includes('正常')) return '安全';
  return text;
}

function hasRouteProfileMainPayload(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const result = isRecord(value.result) ? value.result : value;
  return isRecord(result.main);
}

function normalizeQuotaItems(value: unknown): RouteProfileQuotaItem[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      quotaName: toStringValue(item.quotaName) ?? '',
      score: toNumber(item.score),
      quotaLevel: toStringValue(item.quotaLevel),
      parentId: toStringValue(item.parentId),
      quotaId: toStringValue(item.quotaId),
      originalValue: toNumber(item.originalValue),
      ranking: toNumber(item.ranking),
      firstQuotaName: toStringValue(item.firstQuotaName),
    }))
    .filter((item) => item.quotaName && item.quotaId);
}

function normalizeRouteSuggestionItems(value: unknown): RouteSuggestionItem[] {
  const rawItems =
    isRecord(value) && Array.isArray(value.result) ? value.result : Array.isArray(value) ? value : [];
  return rawItems
    .filter(isRecord)
    .map((item) => ({
      quotaName: toStringValue(item.quotaName) ?? '',
      suggestedContent: toStringValue(item.suggestedContent) ?? '',
      score: toNumber(item.score),
      firstQuotaName: toStringValue(item.firstQuotaName),
      quotaLevel: toStringValue(item.quotaLevel),
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

function resolveRouteDimensionByName(value: string | null): string | null {
  const normalized = simplifyText(value);
  if (!normalized) return null;
  if (normalized.includes('静态')) return STATIC_DIMENSION;
  if (normalized.includes('动态')) return DYNAMIC_DIMENSION;
  return null;
}

function resolveRouteDimensionForQuota(
  item: RouteProfileQuotaItem,
  itemById: Map<string, RouteProfileQuotaItem>
): string | null {
  const direct = resolveRouteDimensionByName(item.firstQuotaName);
  if (direct) return direct;

  let current: RouteProfileQuotaItem | null = item;
  const visited = new Set<string>();
  while (current) {
    const currentDimension = resolveRouteDimensionByName(current.quotaName);
    if (current.quotaLevel === '1' && currentDimension) {
      return currentDimension;
    }
    const parentId: string | null = current.parentId;
    if (!parentId || visited.has(parentId)) break;
    visited.add(parentId);
    current = itemById.get(parentId) ?? null;
  }

  return resolveRouteDimensionByName(item.quotaName);
}

function isLeafRouteQuota(
  item: RouteProfileQuotaItem,
  childrenByParent: Map<string, RouteProfileQuotaItem[]>
): boolean {
  return isLeafQuotaTreeItem(item, childrenByParent);
}

function pickTopRouteIndicators(
  items: RouteProfileQuotaItem[],
  dimension: string,
  limit: number
): RouteIndicatorSummary[] {
  const itemById = buildQuotaItemIndex(items);
  const childrenByParent = buildQuotaChildrenIndex(items);
  return items
    .filter((item) => resolveProfileFinalRiskScore(item) != null)
    .filter((item) => resolveRouteDimensionForQuota(item, itemById) === dimension)
    .filter((item) => item.quotaLevel !== '1')
    .filter((item) => isLeafRouteQuota(item, childrenByParent))
    .sort((left, right) => {
      const scoreDelta =
        (resolveProfileFinalRiskScore(right) ?? Number.NEGATIVE_INFINITY) -
        (resolveProfileFinalRiskScore(left) ?? Number.NEGATIVE_INFINITY);
      if (scoreDelta !== 0) return scoreDelta;
      return (right.score ?? Number.NEGATIVE_INFINITY) - (left.score ?? Number.NEGATIVE_INFINITY);
    })
    .filter(
      (item, index, array) =>
        array.findIndex((candidate) => candidate.quotaName === item.quotaName) === index
    )
    .slice(0, limit)
    .map((item) => ({
      name: item.quotaName,
      score: resolveProfileFinalRiskScore(item),
      count: normalizeIndicatorCount(item.originalValue),
      quotaLevel: item.quotaLevel,
      quotaId: item.quotaId,
      parentId: item.parentId,
    }));
}

function buildFallbackRecommendations(
  indicators: Array<{ name: string; dimension: string }>,
  suggestionItems: RouteSuggestionItem[] = []
): Array<Record<string, unknown>> {
  if (suggestionItems.length > 0) {
    return suggestionItems.slice(0, 5).map((item, index) => ({
      priority: index + 1,
      indicator: item.quotaName,
      action: item.suggestedContent,
      expected_effect: '',
      source: 'mcp_suggested_sub',
      ...(item.score != null ? { score: item.score } : {}),
      ...(item.firstQuotaName ? { dimension: item.firstQuotaName } : {}),
      ...(item.suggestedDate ? { suggested_date: item.suggestedDate } : {}),
      ...(item.acceptStatus ? { accept_status: item.acceptStatus } : {}),
      ...(item.disposeStatus ? { dispose_status: item.disposeStatus } : {}),
    }));
  }

  return indicators.slice(0, 5).map((item, index) => ({
    priority: index + 1,
    indicator: item.name,
    action: NO_MANAGEMENT_SUGGESTION_TEXT,
    expected_effect: '',
    source: 'no_management_suggestion',
    dimension: item.dimension,
  }));
}

function buildCompactQuotaSummary(
  label: string,
  root: RouteProfileQuotaItem | null,
  indicators: RouteIndicatorSummary[]
): Record<string, unknown> {
  return {
    dimension: label,
    ...(root ? { score: resolveProfileFinalRiskScore(root) } : {}),
    ...(root?.score != null ? { source_score: root.score } : {}),
    ...(root?.originalValue != null ? { original_value: root.originalValue } : {}),
    ...(root?.ranking != null ? { ranking: root.ranking } : {}),
    indicators: indicators.map((item) => ({
      name: item.name,
      ...(item.score != null ? { score: item.score } : {}),
      ...(item.count != null ? { count: item.count } : {}),
      ...(item.quotaLevel ? { quota_level: item.quotaLevel } : {}),
      ...(item.quotaId ? { quota_id: item.quotaId } : {}),
      ...(item.parentId ? { parent_id: item.parentId } : {}),
    })),
  };
}

export function adaptRouteProfileToolResult(
  rawResult: unknown,
  routeName: string,
  partition?: string | null,
  suggestionResult?: unknown,
  riskScoreResult?: unknown
): Record<string, unknown> | null {
  if (!isRecord(rawResult)) return null;
  const payload = isRecord(rawResult.result) ? (rawResult.result as Record<string, unknown>) : rawResult;
  if (!isRecord(payload.main)) return null;

  const main = payload.main as Record<string, unknown>;
  const resolvedRouteName = toStringValue(main.routeName) ?? routeName.trim();
  const resolvedRouteId =
    toStringValue(main.routeId) ??
    toStringValue(main.route_id) ??
    toStringValue(main.id) ??
    toStringValue(main.identifier) ??
    resolvedRouteName;
  const resolvedPartition = toStringValue(main.ppartition) ?? toStringValue(partition);
  const quotaItems = normalizeQuotaItems(payload.quotaScoreSubList);
  const itemById = buildQuotaItemIndex(quotaItems);
  const staticRoot =
    quotaItems.find(
      (item) => item.quotaLevel === '1' && resolveRouteDimensionByName(item.quotaName) === STATIC_DIMENSION
    ) ?? null;
  const dynamicRoot =
    quotaItems.find(
      (item) => item.quotaLevel === '1' && resolveRouteDimensionByName(item.quotaName) === DYNAMIC_DIMENSION
    ) ?? null;
  const staticIndicators = pickTopRouteIndicators(quotaItems, STATIC_DIMENSION, 3);
  const dynamicIndicators = pickTopRouteIndicators(quotaItems, DYNAMIC_DIMENSION, 3);
  const overallIndicators = [...staticIndicators, ...dynamicIndicators]
    .filter(
      (item, index, array) =>
        array.findIndex((candidate) => candidate.name === item.name) === index
    )
    .sort((left, right) => {
      const scoreDelta = (right.score ?? Number.NEGATIVE_INFINITY) - (left.score ?? Number.NEGATIVE_INFINITY);
      if (scoreDelta !== 0) return scoreDelta;
      return (right.count ?? Number.NEGATIVE_INFINITY) - (left.count ?? Number.NEGATIVE_INFINITY);
    })
    .slice(0, 5);
  const mainEvaluationType = normalizeEvaluationType(main.evalutaionType);
  const overallScore = computeOverallScore(toNumber(main.score));
  const riskLevel = mainEvaluationType ?? deriveRouteRiskLevel(overallScore);
  const rankPosition = toNumber(main.ranking);
  const rankTotal = toNumber(main.evalutaionTypeCount);
  const rankPercent = toNumber(main.evalutaionTypePercent);
  const suggestions = normalizeRouteSuggestionItems(suggestionResult);
  const riskScoreItems = normalizeRouteRiskScoreItems(riskScoreResult);
  const riskScoreMap = buildRiskScoreMap(riskScoreItems);
  const staticTrend =
    riskScoreMap.get(staticRoot?.quotaId ?? '') ??
    riskScoreMap.get(STATIC_DIMENSION) ??
    (staticRoot?.quotaName ? riskScoreMap.get(staticRoot.quotaName) : null) ??
    null;
  const dynamicTrend =
    riskScoreMap.get(dynamicRoot?.quotaId ?? '') ??
    riskScoreMap.get(DYNAMIC_DIMENSION) ??
    (dynamicRoot?.quotaName ? riskScoreMap.get(dynamicRoot.quotaName) : null) ??
    null;
  const overallTrend = riskScoreItems[0] ?? null;
  const recommendations = buildFallbackRecommendations(
    overallIndicators.map((item) => ({
      name: item.name,
      dimension:
        staticIndicators.some((candidate) => candidate.name === item.name)
          ? STATIC_DIMENSION
          : DYNAMIC_DIMENSION,
    })),
    suggestions
  );
  const alertCounts = Object.fromEntries(
    [...staticIndicators, ...dynamicIndicators]
      .filter((item) => item.count != null)
      .map((item) => [item.name, item.count as number])
  );
  const overallDimension = {
    ...buildDimensionRecord({
      score: overallScore,
      indicators: overallIndicators,
      ranking: rankPosition,
    }),
    trend_text: buildRiskScoreTrendText(overallTrend),
    ...(rankTotal != null ? { rank_total: rankTotal } : {}),
    ...(rankPercent != null ? { percentile: rankPercent } : {}),
    ...(rankPosition != null && rankTotal != null
      ? { display: `排名 ${rankPosition}/${rankTotal}` }
      : {}),
  };
  const reportDate =
    normalizeDateForReport(resolvedPartition) ??
    normalizeDateForReport(toStringValue(main.calculateDate)) ??
    'latest';

  return {
    id: resolvedRouteId,
    name: resolvedRouteName,
    identifier: resolvedRouteId,
    route_id: resolvedRouteId,
    route_name: resolvedRouteName,
    basic: {
      route_id: resolvedRouteId,
      route_name: resolvedRouteName,
      fleet_name: toStringValue(main.organName),
    },
    performance_dashboard: {
      summary: {
        overall_score: overallScore,
        overall_level: riskLevel,
        level_source: mainEvaluationType ? 'main.evalutaionType' : 'derived_from_main.score',
        score_source: 'main.score',
      },
      dimensions: {
        [OVERALL_DIMENSION]: overallDimension,
        [STATIC_DIMENSION]: {
          ...buildDimensionRecord({
            score: staticRoot ? resolveProfileFinalRiskScore(staticRoot) : null,
            indicators: staticIndicators,
            ranking: staticRoot?.ranking ?? null,
          }),
          trend_text: buildRiskScoreTrendText(staticTrend),
        },
        [DYNAMIC_DIMENSION]: {
          ...buildDimensionRecord({
            score: dynamicRoot ? resolveProfileFinalRiskScore(dynamicRoot) : null,
            indicators: dynamicIndicators,
            ranking: dynamicRoot?.ranking ?? null,
          }),
          trend_text: buildRiskScoreTrendText(dynamicTrend),
        },
      },
      system_risk: {
        level: riskLevel,
        tags: overallIndicators.map((item) =>
          item.count != null ? `${item.name}(${item.count}次)` : item.name
        ),
      },
    },
    interventions: {
      recommendations,
    },
    appendix: {
      raw_data: {
        source: `mcp:${ROUTE_PROFILE_TOOL_NAME}`,
        partition: resolvedPartition ?? 'latest',
        source_window: {
          as_of: reportDate,
          window_days: 7,
        },
        ranking_snapshot: {
          ...(rankPosition != null ? { rank_position: rankPosition } : {}),
          ...(rankTotal != null ? { rank_total: rankTotal } : {}),
          ...(rankPercent != null ? { percentile: rankPercent } : {}),
          ...(rankPosition != null && rankTotal != null
            ? { display: `排名 ${rankPosition}/${rankTotal}` }
            : {}),
        },
        alerts_counts: alertCounts,
        suggestion_counts: {
          pending_receive_count: toNumber(main.pendingReceiveCount),
          pending_confirm_count: toNumber(main.pendingConfirmCount),
          pending_optimize_count: toNumber(main.pendingOptimizeCount),
        },
        main: {
          ppartition: resolvedPartition,
          calculate_date: toStringValue(main.calculateDate),
          route_id: resolvedRouteId,
          route_name: resolvedRouteName,
          organ_name: toStringValue(main.organName),
          score: toNumber(main.score),
          evalutaion_type: mainEvaluationType,
          ranking: rankPosition,
          ranking_total: rankTotal,
          ranking_percentile: rankPercent,
          pending_receive_count: toNumber(main.pendingReceiveCount),
          pending_confirm_count: toNumber(main.pendingConfirmCount),
          pending_optimize_count: toNumber(main.pendingOptimizeCount),
        },
        quota_summary: [
          {
            ...buildCompactQuotaSummary(STATIC_DIMENSION, staticRoot, staticIndicators),
            trend_text: buildRiskScoreTrendText(staticTrend),
          },
          {
            ...buildCompactQuotaSummary(DYNAMIC_DIMENSION, dynamicRoot, dynamicIndicators),
            trend_text: buildRiskScoreTrendText(dynamicTrend),
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
          first_quota_name: item.firstQuotaName,
          dimension: resolveRouteDimensionForQuota(item, itemById),
          score: item.score,
          source_score: item.score,
          score_semantics: PROFILE_SOURCE_SCORE_SEMANTICS,
          count: normalizeIndicatorCount(item.originalValue),
          original_value: item.originalValue,
          final_risk_score: resolveProfileFinalRiskScore(item),
          risk_score: resolveProfileFinalRiskScore(item),
          final_score_semantics: PROFILE_RISK_SCORE_SEMANTICS,
          ranking: item.ranking,
        })),
        ...(suggestions.length > 0
          ? {
              suggestions: suggestions.map((item) => ({
                quota_name: item.quotaName,
                suggested_content: item.suggestedContent,
                score: item.score,
                risk_score: item.score,
                score_semantics: PROFILE_SUGGESTION_SCORE_SEMANTICS,
                first_quota_name: item.firstQuotaName,
                quota_level: item.quotaLevel,
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

export function getDefaultRouteProfilePartition(): string {
  return buildPartition();
}

export async function fetchRouteProfileByName(
  env: EnvLike,
  routeName: string,
  partition?: string | null
): Promise<Record<string, unknown> | null> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  const trimmedName = toStringValue(routeName);
  const standardName = trimmedName ? await getStandardRouteName(env.DB, trimmedName) : null;
  const resolvedPartition = toStringValue(partition);
  if (!serverUrl || !standardName) {
    return null;
  }

  const result = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    ROUTE_PROFILE_TOOL_NAME,
    {
      routeName: standardName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  if (!result.success || !hasRouteProfileMainPayload(result.data)) {
    return null;
  }

  const suggestionResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    ROUTE_SUGGESTION_TOOL_NAME,
    {
      routeName: standardName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  const payload = isRecord(result.data) && isRecord(result.data.result)
    ? (result.data.result as Record<string, unknown>)
    : isRecord(result.data)
      ? result.data
      : null;
  const routeId =
    payload && isRecord(payload.main)
      ? toStringValue(payload.main.routeId) ??
        toStringValue(payload.main.route_id) ??
        toStringValue(payload.main.id) ??
        toStringValue(payload.main.identifier)
      : null;
  const riskScoreResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    ROUTE_RISK_SCORE_TOOL_NAME,
    {
      ...(routeId ? { routeId } : { routeName: standardName }),
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  return (
    adaptRouteProfileToolResult(
      result.data,
      standardName,
      resolvedPartition,
      suggestionResult.success ? suggestionResult.data : undefined,
      riskScoreResult.success ? riskScoreResult.data : undefined
    ) ??
    (result.data as Record<string, unknown>)
  );
}
