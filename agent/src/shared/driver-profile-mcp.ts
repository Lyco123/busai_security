import { isRecord } from './guards';
import { callMcpToolForAgent } from './mcp';
import { extractMessageSources, withMessageSources } from './message-sources';
import {
  buildQuotaItemIndex,
  pickTopLeafQuotaItemsByRoot,
  PROFILE_COUNT_SEMANTICS,
  PROFILE_RISK_SCORE_SEMANTICS,
  PROFILE_SOURCE_SCORE_SEMANTICS,
  PROFILE_SUGGESTION_SCORE_SEMANTICS,
  PROFILE_WEIGHTED_VALUE_SEMANTICS,
  resolveProfileFinalRiskScore,
  resolveQuotaDimensionByRoots,
} from './profile-quota-tree';

const DRIVER_PROFILE_TOOL_NAME = 'get_mcp_base_absDriverProfileMain_queryDriverProfile';
const DRIVER_PROFILE_TREND_TOOL_NAME = 'get_mcp_base_absDriverProfileMain_quotaScoreTrend';
const DRIVER_PROFILE_RISK_SCORE_TOOL_NAME = 'get_mcp_base_absDriverProfileMain_driverRiskScore';
const DRIVER_SUGGESTION_TOOL_NAME = 'get_mcp_suggest_absDriverSuggestedSub_queryByDriverNameAndDate';
const SHANGHAI_TIME_ZONE = 'Asia/Shanghai';
const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';
const OVERALL_DIMENSION = '综合风险';
const ACCIDENT_ROOT_ID = '驾驶员画像-事故风险';
const ENERGY_ROOT_ID = '驾驶员画像-能耗风险';
const SERVICE_ROOT_ID = '驾驶员画像-服务态度';
const SAFETY_ROOT_ID = '驾驶员画像-安全评价';

type EnvLike = {
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
};

type DriverProfileQuotaItem = {
  quotaName: string;
  score: number | null;
  quotaLevel: string | null;
  parentId: string | null;
  quotaId: string | null;
  originalValue: number | null;
  riskData: string | null;
  ranking: number | null;
};

type DriverSuggestionItem = {
  quotaName: string;
  suggestedContent: string;
  score: number | null;
  firstQuotaName: string | null;
  suggestedDate: string | null;
  acceptStatus: string | null;
  disposeStatus: string | null;
};

type DriverProfileTrendItem = {
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

type DriverProfileScoreTrendPoint = {
  partition: string | null;
  score: number | null;
  originalValue: number | null;
};

type DriverProfileScoreTrendItem = {
  quotaId: string | null;
  quotaName: string;
  quotaScores: DriverProfileScoreTrendPoint[];
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

function hasDriverProfileMainPayload(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const result = isRecord(value.result) ? value.result : value;
  return isRecord(result.main);
}

function normalizeQuotaItems(value: unknown): DriverProfileQuotaItem[] {
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
      riskData: toStringValue(item.riskData),
      ranking: toNumber(item.ranking),
    }))
    .filter((item) => item.quotaName && item.quotaId);
}

function normalizeDriverSuggestionItems(value: unknown): DriverSuggestionItem[] {
  const rawItems =
    isRecord(value) && Array.isArray(value.result) ? value.result : Array.isArray(value) ? value : [];
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

function normalizeTrendItems(value: unknown): DriverProfileTrendItem[] {
  if (!Array.isArray(value)) return [];
  return value
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

function normalizeScoreTrendItems(value: unknown): DriverProfileScoreTrendItem[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      quotaId: toStringValue(item.quotaId),
      quotaName: toStringValue(item.quotaName) ?? '',
      quotaScores: Array.isArray(item.quotaScores)
        ? item.quotaScores
            .filter(isRecord)
            .map((scoreItem) => ({
              partition: toStringValue(scoreItem.ppartition),
              score: toNumber(scoreItem.score),
              originalValue: toNumber(scoreItem.originalValue),
            }))
        : [],
    }))
    .filter((item) => (item.quotaId || item.quotaName) && item.quotaScores.length > 0);
}

function normalizePartitionToken(value: string | null): string | null {
  if (!value) return null;
  const digits = value.replace(/\D/g, '');
  if (digits.length >= 8) return digits.slice(-4);
  if (digits.length === 4) return digits;
  return digits || null;
}

function computeTrendDelta(current: number | null, previous: number | null): number | null {
  if (current == null || previous == null || !Number.isFinite(current) || !Number.isFinite(previous)) {
    return null;
  }
  if (Math.abs(previous) < 0.000001) return null;
  return ((current - previous) / Math.abs(previous)) * 100;
}

function pickCurrentScoreTrendPoint(
  points: DriverProfileScoreTrendPoint[],
  resolvedPartition: string | null
): { current: DriverProfileScoreTrendPoint; previous: DriverProfileScoreTrendPoint | null } | null {
  if (points.length === 0) return null;
  const partitionToken = normalizePartitionToken(resolvedPartition);
  let index = points.length - 1;
  if (partitionToken) {
    const matchedIndex = points.findIndex(
      (item) => normalizePartitionToken(item.partition) === partitionToken
    );
    if (matchedIndex >= 0) index = matchedIndex;
  }
  return {
    current: points[index]!,
    previous: index > 0 ? points[index - 1]! : null,
  };
}

function adaptScoreTrendItems(value: unknown, resolvedPartition: string | null): DriverProfileTrendItem[] {
  const adapted: DriverProfileTrendItem[] = [];
  for (const item of normalizeScoreTrendItems(value)) {
    const picked = pickCurrentScoreTrendPoint(item.quotaScores, resolvedPartition);
    if (!picked) continue;
    const currentScore = picked.current.score;
    const previousScore = picked.previous?.score ?? null;
    adapted.push({
      quotaId: item.quotaId,
      quotaName: item.quotaName,
      currentRiskValue: picked.current.originalValue,
      previousPeriodRiskValue: computeTrendDelta(currentScore, previousScore),
      lastYearSameDateRiskValue: null,
      organAvgRiskValue: null,
      routeAvgRiskValue: null,
      convertedScore: currentScore,
      previousPeriodScore: previousScore,
      lastYearSameDateScore: null,
      organAvgScore: null,
      routeAvgScore: null,
    });
  }
  return adapted;
}

function normalizeIndicatorCountFromRiskData(value: string | null): number | null {
  if (!value) return null;
  const match = value.match(/(\d+(?:\.\d+)?)\s*(?:次|条|起|个)/);
  if (!match) return null;
  const parsed = Number(match[1]);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;
  return parsed;
}

function pickTopIndicators(
  items: DriverProfileQuotaItem[],
  rootId: string,
  limit: number
): Array<{ name: string; score: number | null; count: number | null }> {
  return pickTopLeafQuotaItemsByRoot(items, rootId, limit).map((item) => ({
      name: item.quotaName,
      score: resolveProfileFinalRiskScore(item),
      count: normalizeIndicatorCountFromRiskData(item.riskData),
    }));
}

function deriveRiskLevel(score: number | null): string | null {
  if (score == null) return null;
  if (score >= 65) return '危险型';
  if (score >= 55) return '关注型';
  if (score >= 45) return '观察型';
  return '安全型';
}

function computeOverallScore(mainScore: number | null): number | null {
  return mainScore != null ? Number(mainScore.toFixed(2)) : null;
}

function buildTrendText(trendDelta: number | null): string {
  if (trendDelta == null) {
    return '同比—，环比—，同单位比—，同线路比—';
  }
  const delta = `${trendDelta > 0 ? '+' : ''}${trendDelta.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1')}%`;
  return `同比—，环比${delta}，同单位比—，同线路比—`;
}

function formatTrendMetric(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const normalized = Number(value.toFixed(2));
  const sign = normalized > 0 ? '+' : '';
  return `${sign}${normalized.toString().replace(/\.0+$/, '').replace(/(\.\d*[1-9])0+$/, '$1')}%`;
}

function buildTrendComparisonText(input?: {
  yoy?: number | null;
  mom?: number | null;
  unit?: number | null;
  route?: number | null;
}): string | null {
  const yoy = formatTrendMetric(input?.yoy ?? null);
  const mom = formatTrendMetric(input?.mom ?? null);
  const unit = formatTrendMetric(input?.unit ?? null);
  const route = formatTrendMetric(input?.route ?? null);
  if (yoy === '—' && mom === '—' && unit === '—' && route === '—') return null;
  return `同比${yoy}，环比${mom}，同单位比${unit}，同线路比${route}`;
}

function buildTrendItemMap(items: DriverProfileTrendItem[]): Map<string, DriverProfileTrendItem> {
  const trendMap = new Map<string, DriverProfileTrendItem>();
  for (const item of items) {
    if (item.quotaId) trendMap.set(item.quotaId, item);
    if (item.quotaName) trendMap.set(item.quotaName, item);
  }
  return trendMap;
}

function averageTrendMetric(
  items: DriverProfileTrendItem[],
  selector: (item: DriverProfileTrendItem) => number | null
): number | null {
  const values = items
    .map(selector)
    .filter((value): value is number => value != null && Number.isFinite(value));
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function aggregateTrendItems(
  quotaId: string,
  quotaName: string,
  items: DriverProfileTrendItem[]
): DriverProfileTrendItem | null {
  if (items.length === 0) return null;
  return {
    quotaId,
    quotaName,
    currentRiskValue: averageTrendMetric(items, (item) => item.currentRiskValue),
    previousPeriodRiskValue: averageTrendMetric(items, (item) => item.previousPeriodRiskValue),
    lastYearSameDateRiskValue: averageTrendMetric(items, (item) => item.lastYearSameDateRiskValue),
    organAvgRiskValue: averageTrendMetric(items, (item) => item.organAvgRiskValue),
    routeAvgRiskValue: averageTrendMetric(items, (item) => item.routeAvgRiskValue),
    convertedScore: averageTrendMetric(items, (item) => item.convertedScore),
    previousPeriodScore: averageTrendMetric(items, (item) => item.previousPeriodScore),
    lastYearSameDateScore: averageTrendMetric(items, (item) => item.lastYearSameDateScore),
    organAvgScore: averageTrendMetric(items, (item) => item.organAvgScore),
    routeAvgScore: averageTrendMetric(items, (item) => item.routeAvgScore),
  };
}

function aggregateRootTrend(
  rootId: string,
  rootName: string,
  trendItems: DriverProfileTrendItem[],
  trendMap: Map<string, DriverProfileTrendItem>,
  quotaItems: DriverProfileQuotaItem[]
): DriverProfileTrendItem | null {
  const exact = trendMap.get(rootId) ?? trendMap.get(rootName);
  if (exact) return exact;

  const childPrefix = `${rootId}-`;
  const childItems = trendItems.filter((item) => {
    if (item.quotaId?.startsWith(childPrefix)) return true;
    const quota = quotaItems.find(
      (candidate) =>
        candidate.quotaId === item.quotaId ||
        candidate.quotaName === item.quotaName ||
        candidate.quotaName === item.quotaId
    );
    return quota?.quotaId === rootId || quota?.parentId === rootId;
  });

  return aggregateTrendItems(rootId, rootName, childItems);
}

function extractResultArray(value: unknown): unknown {
  return isRecord(value) && Array.isArray(value.result) ? value.result : value;
}

function mergeTrendItems(
  scoreTrendItems: DriverProfileTrendItem[],
  riskScoreItems: DriverProfileTrendItem[]
): DriverProfileTrendItem[] {
  const merged = new Map<string, DriverProfileTrendItem>();
  for (const item of scoreTrendItems) {
    const key = item.quotaId || item.quotaName;
    if (key) merged.set(key, item);
  }
  for (const item of riskScoreItems) {
    const key = item.quotaId || item.quotaName;
    if (!key) continue;
    const existing = merged.get(key);
    merged.set(key, existing ? { ...existing, ...item } : item);
  }
  return Array.from(merged.values());
}

function buildDimensionRecord(input: {
  score: number | null;
  indicators: Array<{ name: string; score: number | null; count: number | null }>;
  ranking: number | null;
  trendText?: string | null;
  trendDelta?: number | null;
  trend?: DriverProfileTrendItem | null;
}): Record<string, unknown> {
  const indicatorNames = input.indicators.map((item) => item.name);
  const topIndicator = input.indicators[0] ?? null;
  return {
    ...(input.score != null ? { score: Number(input.score.toFixed(2)) } : {}),
    ...(input.ranking != null ? { rank_position: input.ranking } : {}),
    trend_text:
      input.trendText?.trim() ||
      buildTrendComparisonText({
        yoy: input.trend?.lastYearSameDateRiskValue,
        mom: input.trend?.previousPeriodRiskValue,
        unit: input.trend?.organAvgRiskValue,
        route: input.trend?.routeAvgRiskValue,
      }) ||
      buildTrendText(input.trendDelta ?? null),
    core_risk_indicators: indicatorNames,
    ...(topIndicator?.name ? { top_indicator: topIndicator.name } : {}),
    ...(topIndicator?.count != null ? { alert_count: topIndicator.count } : {}),
  };
}

function buildFallbackRecommendations(
  indicators: Array<{ name: string; dimension: string }>,
  suggestionItems: DriverSuggestionItem[] = []
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
      ...(item.acceptStatus ? { accept_status: item.acceptStatus } : {}),
      ...(item.disposeStatus ? { dispose_status: item.disposeStatus } : {}),
    }));
  }

  return indicators.slice(0, 4).map((item, index) => ({
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
  root: DriverProfileQuotaItem | null,
  indicators: Array<{ name: string; score: number | null; count: number | null }>
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
    })),
  };
}

function extractDriverProfileToolPayload(value: unknown): Record<string, unknown> | null {
  if (!isRecord(value)) return null;
  if (isRecord(value.result)) return value.result as Record<string, unknown>;
  return value;
}

function buildDriverProfilePayload(
  rawResult: Record<string, unknown>,
  driverName: string,
  resolvedPartition: string | null,
  rawTrendResult?: unknown,
  rawRiskScoreResult?: unknown,
  suggestionResult?: unknown
): Record<string, unknown> | null {
  if (!isRecord(rawResult.main)) {
    return null;
  }

  const main = rawResult.main;
  const quotaItems = normalizeQuotaItems(rawResult.quotaScoreSubList);
  const rootConfigs = [
    { dimension: '事故风险', rootId: ACCIDENT_ROOT_ID },
    { dimension: '能耗风险', rootId: ENERGY_ROOT_ID },
    { dimension: '服务态度', rootId: SERVICE_ROOT_ID },
    { dimension: '安全评价', rootId: SAFETY_ROOT_ID },
  ] as const;
  const itemById = buildQuotaItemIndex(quotaItems);
  const scoreTrendItems = adaptScoreTrendItems(extractResultArray(rawTrendResult), resolvedPartition);
  const riskScoreItems = normalizeTrendItems(extractResultArray(rawRiskScoreResult));
  const trendItems = mergeTrendItems(scoreTrendItems, riskScoreItems);
  const trendMap = buildTrendItemMap(trendItems);
  const rootSummaries = rootConfigs.map((config) => {
    const root =
      quotaItems.find((item) => item.quotaLevel === '1' && item.quotaId === config.rootId) ?? null;
    const indicators = pickTopIndicators(quotaItems, config.rootId, 3);
    const trend = aggregateRootTrend(config.rootId, config.dimension, trendItems, trendMap, quotaItems);
    return { ...config, root, indicators, trend };
  });
  const overallIndicators = rootSummaries
    .flatMap((item) =>
      item.indicators.map((indicator) => ({
        ...indicator,
        dimension: item.dimension,
      }))
    )
    .filter(
      (item, index, array) =>
        array.findIndex((candidate) => candidate.name === item.name) === index
    )
    .sort((left, right) => {
      const leftScore = left.score ?? Number.NEGATIVE_INFINITY;
      const rightScore = right.score ?? Number.NEGATIVE_INFINITY;
      if (rightScore !== leftScore) return rightScore - leftScore;
      const leftCount = left.count ?? Number.NEGATIVE_INFINITY;
      const rightCount = right.count ?? Number.NEGATIVE_INFINITY;
      return rightCount - leftCount;
    })
    .slice(0, 4);
  const mainEvaluationType = toStringValue(main.evalutaionType);
  const overallScore = computeOverallScore(toNumber(main.score));
  const overallLevel = mainEvaluationType ?? deriveRiskLevel(overallScore);
  const reportDate = toStringValue(main.calculateDate) ?? resolvedPartition ?? 'latest';
  const normalizedDriverName = toStringValue(main.driverName) ?? driverName;
  const driverId = toStringValue(main.driverId) ?? normalizedDriverName;
  const suggestionItems = normalizeDriverSuggestionItems(suggestionResult);
  const rankPosition = toNumber(main.ranking);
  const rankTotal = toNumber(main.evalutaionTypeCount);
  const rankPercent = toNumber(main.evalutaionTypePercent);
  const rootTrendItems = rootSummaries
    .map((item) => item.trend)
    .filter((item): item is DriverProfileTrendItem => item != null);
  const overallTrend = aggregateTrendItems(
    OVERALL_DIMENSION,
    OVERALL_DIMENSION,
    rootTrendItems.length > 0 ? rootTrendItems : trendItems
  );

  const alertCounts = Object.fromEntries(
    overallIndicators
      .filter((item) => item.count != null)
      .map((item) => [item.name, item.count as number])
  );

  return {
    id: driverId,
    name: normalizedDriverName,
    identifier: driverId,
    basic: {
      driver_name: normalizedDriverName,
      driver_id: driverId,
      fleet_name: toStringValue(main.organName),
      route_name: toStringValue(main.routeName),
    },
    performance_dashboard: {
      summary: {
        overall_score: overallScore,
        overall_level: overallLevel,
        overall_trend_delta: null,
        level_source: mainEvaluationType ? 'main.evalutaionType' : 'derived_from_main.score',
        score_source: 'main.score',
      },
      dimensions: {
        [OVERALL_DIMENSION]: buildDimensionRecord({
          score: overallScore,
          indicators: overallIndicators,
          ranking: rankPosition,
          trend: overallTrend,
          trendDelta: null,
        }),
        综合排行: {
          ...(rankPosition != null ? { rank_position: rankPosition } : {}),
          ...(rankTotal != null ? { rank_total: rankTotal } : {}),
          ...(rankPercent != null ? { percentile: rankPercent } : {}),
          ...(rankPosition != null && rankTotal != null
            ? { display: `排名 ${rankPosition}/${rankTotal}` }
            : {}),
          biz_note: '绩效总览',
        },
        ...Object.fromEntries(
          rootSummaries.map((item) => [
            item.dimension,
            buildDimensionRecord({
              score: item.root ? resolveProfileFinalRiskScore(item.root) : null,
              indicators: item.indicators,
              ranking: item.root?.ranking ?? null,
              trend: item.trend,
              trendDelta: null,
            }),
          ])
        ),
      },
      system_risk: {
        level: overallLevel,
        tags: overallIndicators.map((item) =>
          item.count != null ? `${item.name}(${item.count}次)` : item.name
        ),
      },
    },
    interventions: {
      recommendations: buildFallbackRecommendations(
        overallIndicators.map((item) => ({
          name: item.name,
          dimension: item.dimension,
        })),
        suggestionItems
      ),
    },
    appendix: {
      raw_data: {
        source: `mcp:${DRIVER_PROFILE_TOOL_NAME}`,
        partition: toStringValue(main.ppartition) ?? resolvedPartition ?? 'latest',
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
        main: {
          ppartition: toStringValue(main.ppartition) ?? resolvedPartition,
          calculate_date: toStringValue(main.calculateDate),
          driver_id: driverId,
          driver_name: normalizedDriverName,
          organ_name: toStringValue(main.organName),
          route_name: toStringValue(main.routeName),
          score: toNumber(main.score),
          evalutaion_type: mainEvaluationType,
          ranking: rankPosition,
          pending_receive_count: toNumber(main.pendingReceiveCount),
          pending_confirm_count: toNumber(main.pendingConfirmCount),
          pending_optimize_count: toNumber(main.pendingOptimizeCount),
        },
        quota_summary: rootSummaries.map((item) =>
          buildCompactQuotaSummary(item.dimension, item.root, item.indicators)
        ),
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
          original_value: item.originalValue,
          final_risk_score: resolveProfileFinalRiskScore(item),
          risk_score: resolveProfileFinalRiskScore(item),
          final_score_semantics: PROFILE_RISK_SCORE_SEMANTICS,
          risk_data: item.riskData,
          ranking: item.ranking,
        })),
        trend_summary: (() => {
          const dimensionTrends = rootSummaries
            .filter((item) => item.trend)
            .map((item) => ({
              dimension: item.dimension,
              quota_id: item.rootId,
              quota_name: item.dimension,
              current_risk_value: item.trend?.currentRiskValue ?? null,
              converted_score: item.trend?.convertedScore ?? null,
              previous_period_risk_value: item.trend?.previousPeriodRiskValue ?? null,
              last_year_same_date_risk_value: item.trend?.lastYearSameDateRiskValue ?? null,
              organ_avg_risk_value: item.trend?.organAvgRiskValue ?? null,
              route_avg_risk_value: item.trend?.routeAvgRiskValue ?? null,
              previous_period_score: item.trend?.previousPeriodScore ?? null,
              last_year_same_date_score: item.trend?.lastYearSameDateScore ?? null,
              organ_avg_score: item.trend?.organAvgScore ?? null,
              route_avg_score: item.trend?.routeAvgScore ?? null,
              trend_text: buildTrendComparisonText({
                yoy: item.trend?.lastYearSameDateRiskValue,
                mom: item.trend?.previousPeriodRiskValue,
                unit: item.trend?.organAvgRiskValue,
                route: item.trend?.routeAvgRiskValue,
              }),
            }));
          if (dimensionTrends.length > 0) return dimensionTrends;
          return trendItems.map((item) => ({
            dimension: item.quotaName,
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
            trend_text: buildTrendComparisonText({
              yoy: item.lastYearSameDateRiskValue,
              mom: item.previousPeriodRiskValue,
              unit: item.organAvgRiskValue,
              route: item.routeAvgRiskValue,
            }),
          }));
        })(),
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

export function adaptDriverProfileToolResult(
  rawResult: unknown,
  driverName: string,
  partition?: string | null,
  rawTrendResult?: unknown,
  rawRiskScoreResult?: unknown,
  suggestionResult?: unknown
): Record<string, unknown> | null {
  const normalizedPayload = extractDriverProfileToolPayload(rawResult);
  if (!normalizedPayload) {
    return null;
  }

  const driverProfilePayload = buildDriverProfilePayload(
    normalizedPayload,
    driverName.trim(),
    toStringValue(partition),
    rawTrendResult,
    rawRiskScoreResult,
    suggestionResult
  );
  if (!driverProfilePayload) {
    return null;
  }

  return withMessageSources(driverProfilePayload, extractMessageSources(rawResult, 'mcp'));
}

export function getDefaultDriverProfilePartition(): string {
  return buildPartition();
}

export async function fetchDriverProfileByName(
  env: EnvLike,
  driverName: string,
  partition?: string | null
): Promise<Record<string, unknown> | null> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  const trimmedName = toStringValue(driverName);
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
    DRIVER_PROFILE_TOOL_NAME,
    {
      driverName: trimmedName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  if (!result.success || !hasDriverProfileMainPayload(result.data)) {
    return null;
  }

  const trendResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    DRIVER_PROFILE_TREND_TOOL_NAME,
    {
      driverName: trimmedName,
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
    DRIVER_PROFILE_RISK_SCORE_TOOL_NAME,
    {
      driverName: trimmedName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  const suggestionResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    DRIVER_SUGGESTION_TOOL_NAME,
    {
      driverName: trimmedName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  return adaptDriverProfileToolResult(
    result.data,
    trimmedName,
    resolvedPartition,
    trendResult.success ? trendResult.data : undefined,
    riskScoreResult.success ? riskScoreResult.data : undefined,
    suggestionResult.success ? suggestionResult.data : undefined
  );
}
