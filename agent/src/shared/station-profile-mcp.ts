import { isRecord } from './guards';
import { callMcpToolForAgent } from './mcp';
import { extractMessageSources, withMessageSources } from './message-sources';
import {
  buildQuotaItemIndex,
  buildQuotaChildrenIndex,
  isLeafQuotaTreeItem,
  normalizeQuotaTreeCount,
  PROFILE_COUNT_SEMANTICS,
  PROFILE_RISK_SCORE_SEMANTICS,
  PROFILE_SOURCE_SCORE_SEMANTICS,
  PROFILE_SUGGESTION_SCORE_SEMANTICS,
  PROFILE_WEIGHTED_VALUE_SEMANTICS,
  resolveProfileFinalRiskScore,
  resolveQuotaDimensionByRoots,
} from './profile-quota-tree';

export const STATION_PROFILE_TOOL_NAME =
  'get_mcp_base_absBusStationProfileMain_queryBusStationProfile';

const STATION_RISK_SCORE_TOOL_NAME = 'get_mcp_base_absBusStationProfileMain_stationRiskScore';
const STATION_SUGGESTION_TOOL_NAME =
  'get_mcp_suggest_absBusStationSuggestedSub_queryByBusStationNameAndDate';
const SHANGHAI_TIME_ZONE = 'Asia/Shanghai';
const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';
const OVERALL_DIMENSION = '综合风险';

type EnvLike = {
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
};

type StationProfileQuotaItem = {
  quotaName: string;
  score: number | null;
  quotaLevel: string | null;
  parentId: string | null;
  quotaId: string | null;
  weightRate: number | null;
  originalValue: number | null;
  ranking: number | null;
  firstQuotaName: string | null;
  riskData: string | null;
};

type StationIndicatorSummary = {
  name: string;
  score: number | null;
  count: number | null;
  quotaLevel: string | null;
  quotaId: string | null;
  parentId: string | null;
  riskData: string | null;
};

type StationSuggestionItem = {
  quotaName: string;
  suggestedContent: string;
  score: number | null;
  firstQuotaName: string | null;
  quotaLevel: string | null;
  suggestedDate: string | null;
  acceptStatus: string | null;
  disposeStatus: string | null;
};

type StationRiskScoreItem = {
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

const STATION_ROOTS = [
  { dimension: '交通安全', rootId: '交通安全' },
  { dimension: '三防安全', rootId: '三防安全' },
  { dimension: '消防安全', rootId: '消防安全' },
] as const;

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

function normalizeDimensionToken(value: string | null): string | null {
  if (!value) return null;
  const compact = value.replace(/\s+/g, '');
  if (compact.includes('交通安全')) return '交通安全';
  if (compact.includes('三防安全')) return '三防安全';
  if (compact.includes('消防安全')) return '消防安全';
  return value;
}

function hasStationProfileMainPayload(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const result = isRecord(value.result) ? value.result : value;
  return isRecord(result.main);
}

function normalizeQuotaItems(value: unknown): StationProfileQuotaItem[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((item) => ({
    quotaName: toStringValue(item.quotaName) ?? '',
    score: toNumber(item.score),
    quotaLevel: toStringValue(item.quotaLevel),
    parentId: toStringValue(item.parentId),
    quotaId: toStringValue(item.quotaId),
    weightRate: toNumber(item.weightRate),
    originalValue: toNumber(item.originalValue),
    ranking: toNumber(item.ranking),
    firstQuotaName: toStringValue(item.firstQuotaName),
    riskData: toStringValue(item.riskData),
  }));
}

function normalizeSuggestionItems(value: unknown): StationSuggestionItem[] {
  const rawItems =
    isRecord(value) && Array.isArray(value.result)
      ? value.result
      : Array.isArray(value)
        ? value
        : [];
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

function pickTopIndicators(
  quotaItems: StationProfileQuotaItem[],
  dimension: string,
  limit = 3
): StationIndicatorSummary[] {
  const itemById = buildQuotaItemIndex(quotaItems);
  const childrenByParent = buildQuotaChildrenIndex(quotaItems);
  return quotaItems
    .filter((item) => resolveProfileFinalRiskScore(item) != null)
    .filter((item) => item.quotaLevel !== '1')
    .filter((item) => resolveDimensionForQuota(item, itemById) === dimension)
    .filter((item) => isLeafQuotaTreeItem(item, childrenByParent))
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
    count: normalizeQuotaTreeCount(item.originalValue),
    quotaLevel: item.quotaLevel,
    quotaId: item.quotaId,
    parentId: item.parentId,
    riskData: item.riskData,
  }));
}

function resolveDimensionForQuota(
  item: StationProfileQuotaItem,
  itemById: Map<string, StationProfileQuotaItem>
): string | null {
  return normalizeDimensionToken(
    resolveQuotaDimensionByRoots(item, itemById, STATION_ROOTS) ??
      item.firstQuotaName ??
      item.quotaName
  );
}

function deriveRiskLevel(score: number | null): string | null {
  if (score == null) return null;
  if (score >= 65) return '危险';
  if (score >= 55) return '关注';
  if (score >= 45) return '观察';
  return '安全';
}

function normalizeEvaluationType(value: unknown): string | null {
  const text = toStringValue(value);
  if (!text) return null;
  if (text.includes('危险')) return '危险';
  if (text.includes('关注')) return '关注';
  if (text.includes('观察')) return '观察';
  if (text.includes('安全')) return '安全';
  return text;
}

function normalizeStationRiskScoreItems(value: unknown): StationRiskScoreItem[] {
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

function buildRiskScoreTrendText(item: StationRiskScoreItem | null): string {
  if (!item) return '同比—，环比—，同单位比—';
  return `同比${formatTrendMetric(item.lastYearSameDateRiskValue)}，环比${formatTrendMetric(
    item.previousPeriodRiskValue
  )}，同单位比${formatTrendMetric(item.organAvgRiskValue)}`;
}

function buildRiskScoreMap(items: StationRiskScoreItem[]): Map<string, StationRiskScoreItem> {
  const trendMap = new Map<string, StationRiskScoreItem>();
  for (const item of items) {
    if (item.quotaId) trendMap.set(item.quotaId, item);
    if (item.quotaName) trendMap.set(item.quotaName, item);
  }
  return trendMap;
}

function buildDimensionRecord(input: {
  score: number | null;
  indicators: StationIndicatorSummary[];
  ranking: number | null;
}): Record<string, unknown> {
  const topIndicator = input.indicators[0] ?? null;
  return {
    ...(input.score != null ? { score: Number(input.score.toFixed(2)) } : {}),
    ...(input.ranking != null ? { rank_position: input.ranking } : {}),
    trend_text: '同比—，环比—，同单位比—',
    core_risk_indicators: input.indicators.map((item) => item.name),
    ...(topIndicator?.name ? { top_indicator: topIndicator.name } : {}),
    ...(topIndicator?.count != null ? { alert_count: topIndicator.count } : {}),
    ...(topIndicator?.riskData ? { risk_data: topIndicator.riskData } : {}),
  };
}

function buildRecommendations(
  indicators: Array<{ name: string; dimension: string | null }>,
  suggestions: StationSuggestionItem[]
): Array<Record<string, unknown>> {
  const suggestionByQuota = new Map(suggestions.map((item) => [item.quotaName, item]));
  const rows = indicators.slice(0, 4).map((item, index) => {
    const suggestion = suggestionByQuota.get(item.name);
    return {
      priority: index + 1,
      indicator: item.name,
      dimension: item.dimension ?? '综合风险',
      action: suggestion?.suggestedContent ?? NO_MANAGEMENT_SUGGESTION_TEXT,
      source: suggestion ? 'mcp_suggested_sub' : 'no_management_suggestion',
    };
  });
  if (rows.length > 0) return rows;
  return [
    {
      priority: 1,
      indicator: '综合风险',
      dimension: '综合风险',
      action: NO_MANAGEMENT_SUGGESTION_TEXT,
      source: 'no_management_suggestion',
    },
  ];
}

function buildStationProfilePayload(
  rawPayload: Record<string, unknown>,
  stationName: string,
  partition?: string | null,
  suggestionResult?: unknown,
  riskScoreResult?: unknown
): Record<string, unknown> | null {
  const payload = isRecord(rawPayload.result) ? rawPayload.result : rawPayload;
  if (!isRecord(payload.main)) return null;

  const main = payload.main as Record<string, unknown>;
  const stationDisplayName = toStringValue(main.busStationName) ?? stationName.trim();
  const stationId = toStringValue(main.busStationId) ?? stationDisplayName;
  const resolvedPartition = toStringValue(main.ppartition) ?? toStringValue(partition);
  const quotaItems = normalizeQuotaItems(payload.quotaScoreSubList);
  const itemById = buildQuotaItemIndex(quotaItems);
  const rootItems = STATION_ROOTS.map((root) => ({
    ...root,
    root:
      quotaItems.find(
        (item) =>
          item.quotaLevel === '1' &&
          (item.quotaId?.includes(root.dimension) || item.quotaName === root.dimension)
      ) ??
      quotaItems.find(
        (item) => item.quotaLevel === '2' && normalizeDimensionToken(item.quotaName) === root.dimension
      ) ??
      null,
    indicators: pickTopIndicators(quotaItems, root.dimension, 3),
  }));
  const overallIndicators = rootItems
    .flatMap((item) =>
      item.indicators.map((indicator) => ({ ...indicator, dimension: item.dimension }))
    )
    .filter(
      (item, index, array) =>
        array.findIndex((candidate) => candidate.name === item.name) === index
    )
    .sort((left, right) => {
      const scoreDelta = (right.score ?? -Infinity) - (left.score ?? -Infinity);
      if (scoreDelta !== 0) return scoreDelta;
      return (right.count ?? -Infinity) - (left.count ?? -Infinity);
    })
    .slice(0, 5);
  const score = toNumber(main.score);
  const mainEvaluationType = normalizeEvaluationType(main.evalutaionType);
  const riskLevel = mainEvaluationType ?? deriveRiskLevel(score);
  const rankPosition = toNumber(main.ranking);
  const rankTotal = toNumber(main.evalutaionTypeCount);
  const rankPercent = toNumber(main.evalutaionTypePercent);
  const suggestions = normalizeSuggestionItems(suggestionResult);
  const riskScoreItems = normalizeStationRiskScoreItems(riskScoreResult);
  const riskScoreMap = buildRiskScoreMap(riskScoreItems);
  const overallTrend = riskScoreItems[0] ?? null;
  const reportDate =
    normalizeDateForReport(resolvedPartition) ??
    normalizeDateForReport(toStringValue(main.calculateDate)) ??
    'latest';

  return withMessageSources(
    {
      id: stationId,
      name: stationDisplayName,
      identifier: stationId,
      station_id: stationId,
      station_name: stationDisplayName,
      basic: {
        station_id: stationId,
        station_name: stationDisplayName,
        organ_id: toStringValue(main.organId),
        organ_name: toStringValue(main.organName),
        manager: toStringValue(main.manager),
        land_ownership: toStringValue(main.landOwnership),
        manage_org_name: toStringValue(main.manageOrgName),
        station_type: toStringValue(main.stationType),
        station_properties: toStringValue(main.stationProperties),
      },
      performance_dashboard: {
        summary: {
          overall_score: score,
          overall_level: riskLevel,
          level_source: mainEvaluationType ? 'main.evalutaionType' : 'derived_from_main.score',
          score_source: 'main.score',
        },
        dimensions: {
          [OVERALL_DIMENSION]: {
            ...buildDimensionRecord({
              score,
              indicators: overallIndicators,
              ranking: rankPosition,
            }),
            trend_text: buildRiskScoreTrendText(overallTrend),
            ...(rankTotal != null ? { rank_total: rankTotal } : {}),
            ...(rankPercent != null ? { percentile: rankPercent } : {}),
          },
          ...Object.fromEntries(
            rootItems.map((item) => [
              item.dimension,
              {
                ...buildDimensionRecord({
                  score: item.root ? resolveProfileFinalRiskScore(item.root) : null,
                  indicators: item.indicators,
                  ranking: item.root?.ranking ?? null,
                }),
                trend_text: buildRiskScoreTrendText(
                  riskScoreMap.get(item.root?.quotaId ?? '') ??
                    riskScoreMap.get(item.dimension) ??
                    (item.root?.quotaName ? riskScoreMap.get(item.root.quotaName) : null) ??
                    null
                ),
              },
            ])
          ),
        },
        system_risk: {
          level: riskLevel,
          tags: overallIndicators.map((item) =>
            item.riskData ? `${item.name}(${item.riskData})` : item.name
          ),
        },
      },
      interventions: {
        recommendations: buildRecommendations(
          overallIndicators.map((item) => ({ name: item.name, dimension: item.dimension })),
          suggestions
        ),
      },
      appendix: {
        raw_data: {
          source: `mcp:${STATION_PROFILE_TOOL_NAME}`,
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
          suggestion_counts: {
            pending_receive_count: toNumber(main.pendingReceiveCount),
            pending_confirm_count: toNumber(main.pendingConfirmCount),
            pending_optimize_count: toNumber(main.pendingOptimizeCount),
          },
          main: {
            ppartition: resolvedPartition,
            calculate_date: toStringValue(main.calculateDate),
            station_id: stationId,
            station_name: stationDisplayName,
            organ_id: toStringValue(main.organId),
            organ_name: toStringValue(main.organName),
            score,
            evalutaion_type: mainEvaluationType,
            ranking: rankPosition,
            pending_receive_count: toNumber(main.pendingReceiveCount),
            pending_confirm_count: toNumber(main.pendingConfirmCount),
            pending_optimize_count: toNumber(main.pendingOptimizeCount),
            station_type: toStringValue(main.stationType),
            station_properties: toStringValue(main.stationProperties),
            land_ownership: toStringValue(main.landOwnership),
            manage_org_name: toStringValue(main.manageOrgName),
          },
          quota_summary: rootItems.map((item) => ({
            dimension: item.dimension,
            quota_id: item.root?.quotaId ?? item.dimension,
            score: item.root ? resolveProfileFinalRiskScore(item.root) : null,
            source_score: item.root?.score ?? null,
            original_value: item.root?.originalValue ?? null,
            trend_text: buildRiskScoreTrendText(
              riskScoreMap.get(item.root?.quotaId ?? '') ??
                riskScoreMap.get(item.dimension) ??
                (item.root?.quotaName ? riskScoreMap.get(item.root.quotaName) : null) ??
                null
            ),
            indicators: item.indicators.map((indicator) => ({
              name: indicator.name,
              score: indicator.score,
              count: indicator.count,
              risk_data: indicator.riskData,
              quota_level: indicator.quotaLevel,
              quota_id: indicator.quotaId,
              parent_id: indicator.parentId,
            })),
          })),
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
            dimension: resolveDimensionForQuota(item, itemById),
            score: item.score,
            source_score: item.score,
            score_semantics: PROFILE_SOURCE_SCORE_SEMANTICS,
            count: normalizeQuotaTreeCount(item.originalValue),
            original_value: item.originalValue,
            final_risk_score: resolveProfileFinalRiskScore(item),
            risk_score: resolveProfileFinalRiskScore(item),
            final_score_semantics: PROFILE_RISK_SCORE_SEMANTICS,
            risk_data: item.riskData,
            ranking: item.ranking,
            weight: item.weightRate,
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
    },
    extractMessageSources(rawPayload, 'mcp')
  );
}

export function adaptStationProfileToolResult(
  rawResult: unknown,
  stationName: string,
  partition?: string | null,
  suggestionResult?: unknown,
  riskScoreResult?: unknown
): Record<string, unknown> | null {
  if (!isRecord(rawResult)) return null;
  return buildStationProfilePayload(
    rawResult,
    stationName.trim(),
    partition,
    suggestionResult,
    riskScoreResult
  );
}

export function getDefaultStationProfilePartition(): string {
  return buildPartition();
}

export async function fetchStationProfileByName(
  env: EnvLike,
  stationName: string,
  partition?: string | null
): Promise<Record<string, unknown> | null> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  const trimmedName = toStringValue(stationName);
  const resolvedPartition = toStringValue(partition);
  if (!serverUrl || !trimmedName) {
    return null;
  }

  const result = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    STATION_PROFILE_TOOL_NAME,
    {
      busStationName: trimmedName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  if (!result.success || !hasStationProfileMainPayload(result.data)) {
    return null;
  }

  const suggestionResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    STATION_SUGGESTION_TOOL_NAME,
    {
      busStationName: trimmedName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  const riskScoreResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    STATION_RISK_SCORE_TOOL_NAME,
    {
      busStationName: trimmedName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  return (
    adaptStationProfileToolResult(
      result.data,
      trimmedName,
      resolvedPartition,
      suggestionResult.success ? suggestionResult.data : undefined,
      riskScoreResult.success ? riskScoreResult.data : undefined
    ) ?? (result.data as Record<string, unknown>)
  );
}
