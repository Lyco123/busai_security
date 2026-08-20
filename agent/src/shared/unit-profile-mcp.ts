import { isRecord } from './guards';
import { callMcpToolForAgent } from './mcp';
import { extractMessageSources, withMessageSources } from './message-sources';
import { getStandardUnitName } from './entity-alias-resolver';
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

const UNIT_PROFILE_TOOL_NAME = 'get_mcp_base_absCompanyProfileMain_queryCompanyProfile';
const UNIT_PROFILE_TREND_TOOL_NAME = 'get_mcp_base_absCompanyProfileMain_quotaScoreTrend';
const UNIT_PROFILE_KEY_RISK_TOOL_NAME = 'get_mcp_base_absCompanyProfileMain_getKeyRisk';
const UNIT_SUGGESTION_TOOL_NAME = 'get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate';
const SHANGHAI_TIME_ZONE = 'Asia/Shanghai';
const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';
const OVERALL_DIMENSION = '综合风险';

type EnvLike = {
  DB?: any;
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
};

type UnitProfileQuotaItem = {
  quotaName: string;
  score: number | null;
  quotaLevel: string | null;
  parentId: string | null;
  quotaId: string | null;
  weightRate: number | null;
  originalValue: number | null;
  ranking: number | null;
  firstQuotaName: string | null;
};

type UnitProfileTrendItem = {
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

type UnitProfileScoreTrendPoint = {
  partition: string | null;
  score: number | null;
  originalValue: number | null;
};

type UnitProfileScoreTrendItem = {
  quotaId: string | null;
  quotaName: string;
  quotaScores: UnitProfileScoreTrendPoint[];
};

type UnitSuggestionItem = {
  quotaName: string;
  suggestedContent: string;
  score: number | null;
  firstQuotaName: string | null;
  suggestedDate: string | null;
  acceptStatus: string | null;
  disposeStatus: string | null;
};

const UNIT_ROOTS = [
  { dimension: '驾驶员风险', rootId: '单位画像-驾驶员风险' },
  { dimension: '车辆风险', rootId: '单位画像-车辆风险' },
  { dimension: '线路风险', rootId: '单位画像-线路风险' },
  { dimension: '站场风险', rootId: '单位画像-站场风险' },
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

function hasUnitProfileMainPayload(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const result = isRecord(value.result) ? value.result : value;
  return isRecord(result.main);
}

function normalizeQuotaItems(value: unknown): UnitProfileQuotaItem[] {
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
      firstQuotaName: toStringValue(item.firstQuotaName),
    }))
    .filter((item) => item.quotaName && item.quotaId);
}

function normalizeTrendItems(value: unknown): UnitProfileTrendItem[] {
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

function normalizeScoreTrendItems(value: unknown): UnitProfileScoreTrendItem[] {
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
  points: UnitProfileScoreTrendPoint[],
  resolvedPartition: string | null
): { current: UnitProfileScoreTrendPoint; previous: UnitProfileScoreTrendPoint | null } | null {
  if (points.length === 0) return null;
  const partitionToken = normalizePartitionToken(resolvedPartition);
  let index = points.length - 1;
  if (partitionToken) {
    const matchedIndex = points.findIndex(
      (item) => normalizePartitionToken(item.partition) === partitionToken
    );
    if (matchedIndex >= 0) {
      index = matchedIndex;
    }
  }
  return {
    current: points[index]!,
    previous: index > 0 ? points[index - 1]! : null,
  };
}

function adaptScoreTrendItems(
  value: unknown,
  resolvedPartition: string | null
): UnitProfileTrendItem[] {
  const adapted: UnitProfileTrendItem[] = [];
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

function normalizeUnitSuggestionItems(value: unknown): UnitSuggestionItem[] {
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

function normalizeIndicatorCount(value: number | null): number | null {
  if (value == null || !Number.isFinite(value) || value <= 0) return null;
  if (Math.abs(value - Math.round(value)) > 0.000001) return null;
  return Math.round(value);
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
  if (text.includes('危险') || text.includes('高风险') || text.includes('严重') || text.includes('重大')) {
    return '危险';
  }
  if (text.includes('关注') || text.includes('中风险')) {
    return '关注';
  }
  if (text.includes('观察') || text.includes('一般') || text.includes('低风险')) {
    return '观察';
  }
  if (text.includes('安全') || text.includes('正常')) {
    return '安全';
  }
  return null;
}

function pickTopIndicators(
  items: UnitProfileQuotaItem[],
  rootId: string,
  limit: number
): Array<{ name: string; score: number | null; count: number | null; value: number | null }> {
  return pickTopLeafQuotaItemsByRoot(items, rootId, limit).map((item) => ({
      name: item.quotaName,
      score: resolveProfileFinalRiskScore(item),
      count: normalizeIndicatorCount(item.originalValue),
      value: item.originalValue,
    }));
}

function computeOverallScore(mainScore: number | null): number | null {
  return mainScore != null ? Number(mainScore.toFixed(2)) : null;
}

function formatTrendMetric(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const normalized = Number(value.toFixed(2));
  const sign = normalized > 0 ? '+' : '';
  return `${sign}${normalized.toString().replace(/\.0+$/, '').replace(/(\.\d*[1-9])0+$/, '$1')}%`;
}

function buildTrendText(input?: {
  yoy?: number | null;
  mom?: number | null;
  unit?: number | null;
  route?: number | null;
}): string {
  const yoy = formatTrendMetric(input?.yoy ?? null);
  const mom = formatTrendMetric(input?.mom ?? null);
  const unit = formatTrendMetric(input?.unit ?? null);
  const route = formatTrendMetric(input?.route ?? null);
  return `同比${yoy}，环比${mom}，同单位比${unit}${route !== '—' ? `，同线路比${route}` : ''}`;
}

function buildTrendItemMap(items: UnitProfileTrendItem[]): Map<string, UnitProfileTrendItem> {
  const trendMap = new Map<string, UnitProfileTrendItem>();
  for (const item of items) {
    if (item.quotaId) {
      trendMap.set(item.quotaId, item);
    }
    if (item.quotaName) {
      trendMap.set(item.quotaName, item);
    }
  }
  return trendMap;
}

function pickRootTrend(
  rootId: string,
  rootName: string,
  trendMap: Map<string, UnitProfileTrendItem>
): UnitProfileTrendItem | null {
  return trendMap.get(rootId) ?? trendMap.get(rootName) ?? null;
}

function averageTrendMetric(
  items: UnitProfileTrendItem[],
  selector: (item: UnitProfileTrendItem) => number | null
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
  items: UnitProfileTrendItem[]
): UnitProfileTrendItem | null {
  if (items.length === 0) return null;
  return {
    quotaId,
    quotaName,
    currentRiskValue: averageTrendMetric(items, (item) => item.currentRiskValue),
    previousPeriodRiskValue: averageTrendMetric(
      items,
      (item) => item.previousPeriodRiskValue
    ),
    lastYearSameDateRiskValue: averageTrendMetric(
      items,
      (item) => item.lastYearSameDateRiskValue
    ),
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
  trendItems: UnitProfileTrendItem[],
  trendMap: Map<string, UnitProfileTrendItem>,
  quotaItems: UnitProfileQuotaItem[]
): UnitProfileTrendItem | null {
  const exact = pickRootTrend(rootId, rootName, trendMap);
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
    return quota?.quotaId === rootId || quota?.parentId === rootId || quota?.firstQuotaName === rootName;
  });

  return aggregateTrendItems(rootId, rootName, childItems);
}

function extractResultArray(value: unknown): unknown {
  return isRecord(value) && Array.isArray(value.result) ? value.result : value;
}

function mergeTrendItems(
  scoreTrendItems: UnitProfileTrendItem[],
  keyRiskItems: UnitProfileTrendItem[]
): UnitProfileTrendItem[] {
  const merged = new Map<string, UnitProfileTrendItem>();
  for (const item of scoreTrendItems) {
    const key = item.quotaId || item.quotaName;
    if (key) merged.set(key, item);
  }
  for (const item of keyRiskItems) {
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
}): Record<string, unknown> {
  const topIndicator = input.indicators[0] ?? null;
  return {
    ...(input.score != null ? { score: Number(input.score.toFixed(2)) } : {}),
    ...(input.ranking != null ? { rank_position: input.ranking } : {}),
    trend_text: input.trendText?.trim() || buildTrendText(),
    core_risk_indicators: input.indicators.map((item) => item.name),
    ...(topIndicator?.name ? { top_indicator: topIndicator.name } : {}),
    ...(topIndicator?.count != null ? { alert_count: topIndicator.count } : {}),
  };
}

function buildFallbackRecommendations(
  indicators: Array<{ name: string; dimension: string }>,
  suggestionItems: UnitSuggestionItem[] = []
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
  root: UnitProfileQuotaItem | null,
  indicators: Array<{ name: string; score: number | null; count: number | null; value: number | null }>
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
      ...(item.value != null ? { value: item.value } : {}),
    })),
  };
}

function extractUnitProfileToolPayload(value: unknown): Record<string, unknown> | null {
  if (!isRecord(value)) return null;
  if (isRecord(value.result)) return value.result as Record<string, unknown>;
  return value;
}

function buildUnitProfilePayload(
  rawResult: Record<string, unknown>,
  organName: string,
  resolvedPartition: string | null,
  rawTrendResult?: unknown,
  rawKeyRiskResult?: unknown,
  suggestionResult?: unknown
): Record<string, unknown> | null {
  if (!isRecord(rawResult.main)) {
    return null;
  }

  const main = rawResult.main;
  const quotaItems = normalizeQuotaItems(rawResult.quotaScoreSubList);
  const itemById = buildQuotaItemIndex(quotaItems);
  const scoreTrendItems = adaptScoreTrendItems(extractResultArray(rawTrendResult), resolvedPartition);
  const keyRiskItems = normalizeTrendItems(extractResultArray(rawKeyRiskResult));
  const trendItems = mergeTrendItems(scoreTrendItems, keyRiskItems);
  const trendMap = buildTrendItemMap(trendItems);
  const rootSummaries = UNIT_ROOTS.map((config) => {
    const root =
      quotaItems.find((item) => item.quotaLevel === '1' && item.quotaId === config.rootId) ?? null;
    const indicators = pickTopIndicators(quotaItems, config.rootId, 4);
    const trend = aggregateRootTrend(
      config.rootId,
      config.dimension,
      trendItems,
      trendMap,
      quotaItems
    );
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
      const scoreDelta = (right.score ?? -Infinity) - (left.score ?? -Infinity);
      if (scoreDelta !== 0) return scoreDelta;
      return (right.count ?? -Infinity) - (left.count ?? -Infinity);
    })
    .slice(0, 4);
  const mainEvaluationType = normalizeEvaluationType(main.evalutaionType);
  const overallScore = computeOverallScore(toNumber(main.score));
  const reportDate = toStringValue(main.calculateDate) ?? toStringValue(main.ppartition) ?? resolvedPartition ?? 'latest';
  const normalizedOrganName = toStringValue(main.organName) ?? organName;
  const organId = toStringValue(main.organId) ?? normalizedOrganName;
  const suggestionItems = normalizeUnitSuggestionItems(suggestionResult);
  const rankPosition = toNumber(main.ranking);
  const rankTotal = toNumber(main.evalutaionTypeCount);
  const rankPercent = toNumber(main.evalutaionTypePercent);
  const overallLevel = mainEvaluationType ?? deriveRiskLevel(overallScore);
  const alertCounts = Object.fromEntries(
    overallIndicators
      .filter((item) => item.count != null)
      .map((item) => [item.name, item.count as number])
  );
  const rootTrendItems = rootSummaries
    .map((item) => item.trend)
    .filter((item): item is UnitProfileTrendItem => item != null);
  const overallTrend = aggregateTrendItems(
    OVERALL_DIMENSION,
    OVERALL_DIMENSION,
    rootTrendItems.length > 0 ? rootTrendItems : trendItems
  );
  const overallTrendText =
    overallTrend
      ? buildTrendText({
          yoy: overallTrend.lastYearSameDateRiskValue,
          mom: overallTrend.previousPeriodRiskValue,
          unit: overallTrend.organAvgRiskValue,
          route: overallTrend.routeAvgRiskValue,
        })
      : buildTrendText();

  return {
    id: organId,
    name: normalizedOrganName,
    identifier: organId,
    basic: {
      organ_name: normalizedOrganName,
      organ_id: organId,
      manager: toStringValue(main.manager),
    },
    performance_dashboard: {
      summary: {
        overall_score: overallScore,
        overall_level: overallLevel,
        level_source: mainEvaluationType ? 'main.evalutaionType' : 'derived_from_main.score',
        score_source: 'main.score',
      },
      dimensions: {
        [OVERALL_DIMENSION]: buildDimensionRecord({
          score: overallScore,
          indicators: overallIndicators,
          ranking: rankPosition,
          trendText: overallTrendText,
        }),
        综合排行: {
          ...(rankPosition != null ? { rank_position: rankPosition } : {}),
          ...(rankTotal != null ? { rank_total: rankTotal } : {}),
          ...(rankPercent != null ? { percentile: rankPercent } : {}),
          ...(rankPosition != null && rankTotal != null
            ? { display: `排名 ${rankPosition}/${rankTotal}` }
            : {}),
        },
        ...Object.fromEntries(
          rootSummaries.map((item) => [
            item.dimension,
            buildDimensionRecord({
              score: item.root ? resolveProfileFinalRiskScore(item.root) : null,
              indicators: item.indicators,
              ranking: item.root?.ranking ?? null,
              trendText: buildTrendText({
                yoy: item.trend?.lastYearSameDateRiskValue,
                mom: item.trend?.previousPeriodRiskValue,
                unit: item.trend?.organAvgRiskValue,
                route: item.trend?.routeAvgRiskValue,
              }),
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
        overallIndicators.map((item) => ({ name: item.name, dimension: item.dimension })),
        suggestionItems
      ),
    },
    appendix: {
      raw_data: {
        source: `mcp:${UNIT_PROFILE_TOOL_NAME}`,
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
        suggestion_counts: {
          pending_receive_count: toNumber(main.pendingReceiveCount),
          pending_confirm_count: toNumber(main.pendingConfirmCount),
          pending_optimize_count: toNumber(main.pendingOptimizeCount),
        },
        main: {
          ppartition: toStringValue(main.ppartition) ?? resolvedPartition,
          calculate_date: toStringValue(main.calculateDate),
          organ_id: organId,
          organ_name: normalizedOrganName,
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
          first_quota_name: item.firstQuotaName,
          dimension: resolveQuotaDimensionByRoots(item, itemById, UNIT_ROOTS),
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
            trend_text: buildTrendText({
              yoy: item.trend?.lastYearSameDateRiskValue,
              mom: item.trend?.previousPeriodRiskValue,
              unit: item.trend?.organAvgRiskValue,
              route: item.trend?.routeAvgRiskValue,
            }),
          }));
          if (dimensionTrends.length > 0) {
            return dimensionTrends;
          }
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
            trend_text: buildTrendText({
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

export function adaptUnitProfileToolResult(
  rawResult: unknown,
  organName: string,
  partition?: string | null,
  rawTrendResult?: unknown,
  rawKeyRiskResult?: unknown,
  suggestionResult?: unknown
): Record<string, unknown> | null {
  const normalizedPayload = extractUnitProfileToolPayload(rawResult);
  if (!normalizedPayload) {
    return null;
  }

  const unitProfilePayload = buildUnitProfilePayload(
    normalizedPayload,
    organName.trim(),
    toStringValue(partition),
    rawTrendResult,
    rawKeyRiskResult,
    suggestionResult
  );
  if (!unitProfilePayload) {
    return null;
  }

  return withMessageSources(unitProfilePayload, extractMessageSources(rawResult, 'mcp'));
}

export function getDefaultUnitProfilePartition(): string {
  return buildPartition();
}

export async function fetchUnitProfileByName(
  env: EnvLike,
  organName: string,
  partition?: string | null
): Promise<Record<string, unknown> | null> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  const trimmedName = toStringValue(organName);
  const standardName = trimmedName ? await getStandardUnitName(env.DB, trimmedName) : null;
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
    UNIT_PROFILE_TOOL_NAME,
    {
      organName: standardName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  if (!result.success || !hasUnitProfileMainPayload(result.data)) {
    return null;
  }

  const trendResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    UNIT_PROFILE_TREND_TOOL_NAME,
    {
      organName: standardName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  const keyRiskResult = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    UNIT_PROFILE_KEY_RISK_TOOL_NAME,
    {
      organName: standardName,
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
    UNIT_SUGGESTION_TOOL_NAME,
    {
      organName: standardName,
      ...(resolvedPartition ? { ppartition: resolvedPartition } : {}),
    }
  );

  return adaptUnitProfileToolResult(
    result.data,
    standardName,
    resolvedPartition,
    trendResult.success ? trendResult.data : undefined,
    keyRiskResult.success ? keyRiskResult.data : undefined,
    suggestionResult.success ? suggestionResult.data : undefined
  );
}
