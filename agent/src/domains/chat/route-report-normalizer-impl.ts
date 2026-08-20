import { isRecord } from '../../shared/guards';
import { getNestedValue } from '../../shared/object-path';
import {
  buildManagementComparisonText,
  buildManagementRankInfo,
  buildManagementReportDate,
  deriveRiskLevelLabel,
  findMappedAnalysisItem,
  findMappedDashboardRow,
  getStringArray,
  hasStructuredReportTemplateMarkerNotation,
  parseAlertCount,
  readArrayAtPath,
  readFirstNumberAtPaths,
  readFirstRecordAtPaths,
  readFirstStringAtPaths,
  readRecordAtPath,
  resolveDashboardTrendText,
  readStringAtPath,
  trimNumberString,
} from './structured-report-normalizers';

const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';
const ROUTE_REPORT_TARGET_DIMENSIONS = ['综合风险', '静态风险', '动态风险'] as const;

type RouteReportTargetDimension = (typeof ROUTE_REPORT_TARGET_DIMENSIONS)[number];

interface RouteIndicatorCandidate {
  indicator: string;
  dimension: RouteReportTargetDimension;
  score: number | null;
  riskScore: number | null;
  count: number | null;
}

const ROUTE_REPORT_DIMENSION_CONFIGS: Array<{
  target: RouteReportTargetDimension;
  aliases: string[];
  sourceDimensionPaths: string[];
  sourceScorePaths: string[];
}> = [
  {
    target: '综合风险',
    aliases: ['综合风险', '整体风险', '线路综合风险'],
    sourceDimensionPaths: [
      'performance_dashboard.dimensions.综合风险',
      'performance_dashboard.summary',
      'risk_profile',
      'safety_rating',
    ],
    sourceScorePaths: [
      'performance_dashboard.dimensions.综合风险.score',
      'performance_dashboard.summary.overall_score',
      'risk_profile.overall',
      'safety_rating.overall',
    ],
  },
  {
    target: '静态风险',
    aliases: ['静态风险', '静态环境风险', '线形路况风险', '人口密集区域风险', '行为黑点风险'],
    sourceDimensionPaths: [
      'performance_dashboard.dimensions.静态风险',
      'static_risk',
      'risk_profile',
    ],
    sourceScorePaths: [
      'performance_dashboard.dimensions.静态风险.score',
      'risk_profile.static',
      'static_risk.score',
      'risk_profile.infrastructure',
    ],
  },
  {
    target: '动态风险',
    aliases: ['动态风险', '动态运行风险', '运行风险', '行为风险'],
    sourceDimensionPaths: [
      'performance_dashboard.dimensions.动态风险',
      'dynamic_risk',
      'risk_profile',
    ],
    sourceScorePaths: [
      'performance_dashboard.dimensions.动态风险.score',
      'risk_profile.dynamic',
      'dynamic_risk.score',
      'risk_profile.traffic',
    ],
  },
];

const ROUTE_REPORT_SUGGESTION_PREFIXES = [
  '风险最高的基础指标是',
  '其次是',
  '再次是',
  '同时有',
  '最后是',
];
const ROUTE_REPORT_ANALYSIS_PREFIXES = ['风险最高的一级指标是', '其次是'];

function buildRouteRecommendationText(
  prefix: string,
  indicator: string,
  actionText: string,
  expectedText: string
): string {
  if (actionText.trim() === NO_MANAGEMENT_SUGGESTION_TEXT) {
    return `${prefix}{${indicator}}，${NO_MANAGEMENT_SUGGESTION_TEXT}。`;
  }
  return expectedText
    ? `${prefix}{${indicator}}，建议开展{${actionText}}，【${expectedText}】。`
    : `${prefix}{${indicator}}，建议开展{${actionText}}。`;
}
const ROUTE_DYNAMIC_INDICATOR_PATTERN =
  /(急加速|急减速|急刹车|不规范进站|进站|空挡|滑行|超速|闯灯|故障|工单|电池|ABS|电机|轮胎|报警|运行|行为|动态|交通|traffic)/i;
const ROUTE_STATIC_INDICATOR_PATTERN =
  /(急转弯|左转弯|右转弯|斑马线|上坡|下坡|限速|临水临崖|学校|商场|体育馆|医院|老人刷卡|黑点|路况|人口|静态|设施|基础设施|站点|站台|路段|路口|infrastructure)/i;

function simplifyRouteIndicatorLabel(value: unknown): string {
  if (typeof value !== 'string') return '';
  return value
    .replace(/[（(][^）)]*[）)]/g, '')
    .replace(/\s+/g, '')
    .trim();
}

function getRouteDimensionConfigByTarget(
  target: string
): (typeof ROUTE_REPORT_DIMENSION_CONFIGS)[number] | null {
  return ROUTE_REPORT_DIMENSION_CONFIGS.find((item) => item.target === target) ?? null;
}

function normalizeRouteDimensionName(value: unknown): RouteReportTargetDimension | null {
  if (typeof value !== 'string') return null;
  const simplified = simplifyRouteIndicatorLabel(value);
  if (!simplified) return null;
  for (const config of ROUTE_REPORT_DIMENSION_CONFIGS) {
    if (
      config.aliases.some((alias) => {
        const normalizedAlias = simplifyRouteIndicatorLabel(alias);
        return simplified === normalizedAlias || simplified.includes(normalizedAlias);
      })
    ) {
      return config.target;
    }
  }
  return null;
}

function looksLikeRouteDimensionText(value: string): boolean {
  return normalizeRouteDimensionName(value) != null;
}

function inferRouteDimensionFromIndicator(indicator: string): RouteReportTargetDimension {
  if (ROUTE_DYNAMIC_INDICATOR_PATTERN.test(indicator)) {
    return '动态风险';
  }
  if (ROUTE_STATIC_INDICATOR_PATTERN.test(indicator)) {
    return '静态风险';
  }
  return '综合风险';
}

function inferRouteDimensionFromCategory(category: unknown): RouteReportTargetDimension {
  if (typeof category !== 'string') return '综合风险';
  const normalized = simplifyRouteIndicatorLabel(category);
  if (!normalized) return '综合风险';
  if (/(静态|路况|人口|黑点|设施|基础设施|infrastructure)/.test(normalized)) return '静态风险';
  if (/(动态|故障|行为|运行|交通|traffic)/.test(normalized)) return '动态风险';
  return inferRouteDimensionFromIndicator(normalized);
}

function dedupeRouteIndicatorTexts(values: string[]): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    const normalized = simplifyRouteIndicatorLabel(trimmed);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    next.push(trimmed);
  }
  return next;
}

function collectRouteIndicatorCandidates(
  sourceData: Record<string, unknown> | null
): RouteIndicatorCandidate[] {
  if (!sourceData) return [];
  const candidates: RouteIndicatorCandidate[] = [];

  const pushCandidate = (rawIndicator: unknown, partial: Partial<RouteIndicatorCandidate> = {}) => {
    const indicator = simplifyRouteIndicatorLabel(rawIndicator);
    if (!indicator || looksLikeRouteDimensionText(indicator)) return;
    candidates.push({
      indicator,
      dimension: partial.dimension ?? inferRouteDimensionFromIndicator(indicator),
      score: partial.score ?? null,
      riskScore: partial.riskScore ?? partial.score ?? null,
      count: partial.count ?? null,
    });
  };

  const quotaSummaries = readArrayAtPath(sourceData, 'appendix.raw_data.quota_summary') ?? [];
  for (const summary of quotaSummaries) {
    if (!isRecord(summary)) continue;
    const summaryDimension = normalizeRouteDimensionName(summary.dimension);
    if (!summaryDimension) continue;
    const indicators = Array.isArray(summary.indicators) ? summary.indicators : [];
    for (const indicator of indicators) {
      if (!isRecord(indicator)) continue;
      pushCandidate(indicator.name ?? indicator.indicator ?? indicator.quota_name, {
        dimension: summaryDimension,
        score: parseAlertCount(indicator.score),
        riskScore: parseAlertCount(
          indicator.final_risk_score ??
            indicator.risk_score ??
            indicator.original_value ??
            indicator.score
        ),
        count: parseAlertCount(indicator.count ?? indicator.alert_count),
      });
    }
  }

  const quotaItems = readArrayAtPath(sourceData, 'appendix.raw_data.quota_items') ?? [];
  for (const item of quotaItems) {
    if (!isRecord(item)) continue;
    const dimension =
      normalizeRouteDimensionName(item.dimension) ??
      normalizeRouteDimensionName(item.first_quota_name) ??
      inferRouteDimensionFromCategory(item.first_quota_name ?? item.parent_name);
    pushCandidate(item.quota_name ?? item.name ?? item.indicator, {
      dimension,
      score: parseAlertCount(item.score),
      riskScore: parseAlertCount(item.final_risk_score ?? item.risk_score ?? item.original_value),
      count: parseAlertCount(item.count ?? item.alert_count),
    });
  }

  const dashboardDimensions: Array<{ path: string; dimension: RouteReportTargetDimension }> = [
    { path: 'performance_dashboard.dimensions.静态风险', dimension: '静态风险' },
    { path: 'performance_dashboard.dimensions.动态风险', dimension: '动态风险' },
  ];
  for (const item of dashboardDimensions) {
    const record = readRecordAtPath(sourceData, item.path);
    if (!record) continue;
    const indicators = getStringArray(record.core_risk_indicators);
    for (const indicator of indicators) {
      pushCandidate(indicator, {
        dimension: item.dimension,
        score: parseAlertCount(record.score),
      });
    }
    pushCandidate(record.top_indicator, {
      dimension: item.dimension,
      score: parseAlertCount(record.score),
      count: parseAlertCount(record.alert_count),
    });
  }

  const highRiskIndicators = getNestedValue(sourceData, 'high_risk_indicators.indicators');
  if (Array.isArray(highRiskIndicators)) {
    for (const item of highRiskIndicators) {
      if (isRecord(item)) {
        pushCandidate(item.indicator ?? item.name ?? item.title ?? item.type, {
          dimension:
            normalizeRouteDimensionName(item.dimension) ??
            inferRouteDimensionFromCategory(item.category),
          score: parseAlertCount(item.score),
          count: parseAlertCount(item.alert_count ?? item.count ?? item.times ?? item.occurrences),
        });
      } else {
        pushCandidate(item);
      }
    }
  }

  const systemTags = readArrayAtPath(sourceData, 'performance_dashboard.system_risk.tags') ?? [];
  for (const tag of systemTags) {
    pushCandidate(tag, {
      count: parseAlertCount(tag),
    });
  }

  const highRiskSegments = readArrayAtPath(sourceData, 'high_risk_segments') ?? [];
  for (const item of highRiskSegments) {
    if (!isRecord(item)) continue;
    const segmentText = simplifyRouteIndicatorLabel(item.segment ?? item.location);
    pushCandidate(item.issue ?? item.indicator ?? item.name, {
      dimension:
        normalizeRouteDimensionName(item.dimension) ??
        inferRouteDimensionFromCategory(item.category ?? item.issue),
      score: parseAlertCount(item.score ?? item.risk_score),
      count: parseAlertCount(item.alert_count ?? item.count ?? item.times ?? item.occurrences),
    });
    if (segmentText) {
      pushCandidate(`高风险路段${segmentText}`, {
        dimension: '静态风险',
        score: parseAlertCount(item.score ?? item.risk_score),
        count: parseAlertCount(item.alert_count ?? item.count ?? item.times ?? item.occurrences),
      });
    }
  }

  const indicatorSections: Array<{ path: string; dimension: RouteReportTargetDimension }> = [
    { path: 'indicators.static_risk_road', dimension: '静态风险' },
    { path: 'indicators.static_risk_population', dimension: '静态风险' },
    { path: 'indicators.static_risk_blackspot', dimension: '静态风险' },
    { path: 'indicators.dynamic_risk_faults', dimension: '动态风险' },
  ];
  for (const section of indicatorSections) {
    const values = readRecordAtPath(sourceData, section.path);
    if (!values) continue;
    for (const [key, value] of Object.entries(values)) {
      pushCandidate(key, {
        dimension: section.dimension,
        score: typeof value === 'number' ? value : parseAlertCount(value),
      });
    }
  }

  const risks = readArrayAtPath(sourceData, 'risk_segments') ?? [];
  for (const item of risks) {
    if (!isRecord(item)) continue;
    const factors = Array.isArray(item.risk_factors) ? item.risk_factors : [];
    for (const factor of factors) {
      pushCandidate(factor, {
        dimension: '静态风险',
        score: parseAlertCount(item.risk_score),
        count: parseAlertCount(item.accident_count),
      });
    }
  }

  const deduped = new Map<string, RouteIndicatorCandidate>();
  for (const candidate of candidates) {
    const key = `${candidate.dimension}:${candidate.indicator}`;
    const existing = deduped.get(key);
    if (!existing) {
      deduped.set(key, candidate);
      continue;
    }
    const existingScore = existing.score ?? Number.NEGATIVE_INFINITY;
    const candidateScore = candidate.score ?? Number.NEGATIVE_INFINITY;
    const existingRiskScore = existing.riskScore ?? Number.NEGATIVE_INFINITY;
    const candidateRiskScore = candidate.riskScore ?? Number.NEGATIVE_INFINITY;
    const existingCount = existing.count ?? Number.NEGATIVE_INFINITY;
    const candidateCount = candidate.count ?? Number.NEGATIVE_INFINITY;
    if (
      candidateScore > existingScore ||
      (candidateScore === existingScore && candidateRiskScore > existingRiskScore) ||
      (candidateScore === existingScore &&
        candidateRiskScore === existingRiskScore &&
        candidateCount > existingCount)
    ) {
      deduped.set(key, candidate);
    }
  }

  return Array.from(deduped.values()).sort((left, right) => {
    const scoreDelta =
      (right.score ?? Number.NEGATIVE_INFINITY) - (left.score ?? Number.NEGATIVE_INFINITY);
    if (scoreDelta !== 0) return scoreDelta;
    return (right.count ?? Number.NEGATIVE_INFINITY) - (left.count ?? Number.NEGATIVE_INFINITY);
  });
}

function findRouteIndicatorCandidate(
  sourceData: Record<string, unknown> | null,
  indicator: unknown,
  targetDimension?: RouteReportTargetDimension
): RouteIndicatorCandidate | null {
  const normalized = simplifyRouteIndicatorLabel(indicator);
  if (!normalized) return null;
  const matches = collectRouteIndicatorCandidates(sourceData).filter((item) => {
    const candidate = simplifyRouteIndicatorLabel(item.indicator);
    return (
      candidate === normalized || candidate.includes(normalized) || normalized.includes(candidate)
    );
  });
  if (targetDimension) {
    return matches.find((item) => item.dimension === targetDimension) ?? null;
  }
  return matches[0] ?? null;
}

function buildRouteDimensionAggregateScore(
  target: RouteReportTargetDimension,
  sourceData: Record<string, unknown> | null
): number | null {
  if (!sourceData) return null;
  const config = getRouteDimensionConfigByTarget(target);
  const direct = config ? readFirstNumberAtPaths(sourceData, config.sourceScorePaths) : null;
  if (direct != null) return direct;
  if (target === '综合风险') {
    const score = readFirstNumberAtPaths(sourceData, ['appendix.raw_data.main.score']);
    if (score != null) return score;
  }
  const quotaSummaries = readArrayAtPath(sourceData, 'appendix.raw_data.quota_summary') ?? [];
  for (const summary of quotaSummaries) {
    if (!isRecord(summary)) continue;
    if (normalizeRouteDimensionName(summary.dimension) !== target) continue;
    const score = parseAlertCount(summary.score);
    if (score != null) return score;
  }
  return null;
}

function isRouteIndicatorCompatibleWithTarget(
  indicator: string,
  target: RouteReportTargetDimension,
  sourceData: Record<string, unknown> | null
): boolean {
  if (target === '综合风险') return true;
  const matched = findRouteIndicatorCandidate(sourceData, indicator, target);
  if (matched) {
    return matched.dimension === target;
  }
  return inferRouteDimensionFromIndicator(indicator) === target;
}

function getRouteIndicatorFallback(
  target: RouteReportTargetDimension,
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string {
  const reportFactors = getStringArray(
    getNestedValue(report, 'management_summary.major_risk_factors')
  );
  const sourceCandidates = collectRouteIndicatorCandidates(sourceData).filter(
    (item) => target === '综合风险' || item.dimension === target
  );
  const compatibleReportFactors = reportFactors.filter((item) =>
    isRouteIndicatorCompatibleWithTarget(item, target, sourceData)
  );
  const merged = dedupeRouteIndicatorTexts([
    ...sourceCandidates.map((item) => item.indicator),
    ...compatibleReportFactors,
  ]);
  if (merged.length) return merged[0];
  return '';
}

function normalizeRouteIndicatorText(
  rawIndicator: unknown,
  target: RouteReportTargetDimension,
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string {
  const simplified = simplifyRouteIndicatorLabel(rawIndicator);
  if (simplified && !looksLikeRouteDimensionText(simplified)) {
    const matched = findRouteIndicatorCandidate(
      sourceData,
      simplified,
      target === '综合风险' ? undefined : target
    );
    if (matched) {
      if (target === '综合风险' || matched.dimension === target) {
        return matched.indicator;
      }
      return getRouteIndicatorFallback(target, sourceData, report);
    }
    const inferred = inferRouteDimensionFromIndicator(simplified);
    if (target === '综合风险' || inferred === target) {
      return simplified;
    }
  }
  return getRouteIndicatorFallback(target, sourceData, report);
}

function collectRouteIndicatorsForTarget(
  target: RouteReportTargetDimension,
  reportRow: Record<string, unknown> | null,
  sourceDimension: Record<string, unknown> | null,
  analysisItem: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string[] {
  const candidateIndicators = collectRouteIndicatorCandidates(sourceData)
    .filter((item) => target === '综合风险' || item.dimension === target)
    .map((item) => item.indicator);
  const rawIndicators = [
    ...candidateIndicators,
    ...getStringArray(sourceDimension?.core_risk_indicators),
    simplifyRouteIndicatorLabel(sourceDimension?.top_indicator),
    simplifyRouteIndicatorLabel(analysisItem?.top_indicator),
    ...getStringArray(reportRow?.core_risk_indicators),
  ];
  const normalized = rawIndicators
    .map((item) => normalizeRouteIndicatorText(item, target, sourceData, report))
    .filter(
      (item): item is string =>
        item.length > 0 && item !== '—' && !looksLikeRouteDimensionText(item)
    )
    .filter((item) => isRouteIndicatorCompatibleWithTarget(item, target, sourceData));
  const deduped = dedupeRouteIndicatorTexts(normalized);
  if (deduped.length) {
    return deduped.slice(0, target === '综合风险' ? 5 : 3);
  }
  const fallback = getRouteIndicatorFallback(target, sourceData, report);
  return fallback ? [fallback] : [];
}

function buildRouteTrendText(
  target: RouteReportTargetDimension,
  aliases: string[],
  reportRow: Record<string, unknown> | null,
  sourceDimension: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null
): string {
  return resolveDashboardTrendText({
    reportRow,
    sourceDimension,
    sourceData,
    keys: [target, ...aliases],
    includeRouteComparison: false,
    allowOverallFallback: target === ROUTE_REPORT_TARGET_DIMENSIONS[0],
    defaultText: '同比—，环比—，同单位比—',
  });
}

function buildRouteDashboardRows(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const rows = ROUTE_REPORT_DIMENSION_CONFIGS.map((config) => {
    const sourceDimension = readFirstRecordAtPaths(sourceData ?? {}, config.sourceDimensionPaths);
    const reportRow = findMappedDashboardRow(report, config.aliases);
    const analysisItem = findMappedAnalysisItem(report, config.aliases);
    const score =
      (reportRow ? parseAlertCount(reportRow.score) : null) ??
      buildRouteDimensionAggregateScore(config.target, sourceData);
    return {
      dimension: config.target,
      score,
      trend_text: buildRouteTrendText(
        config.target,
        config.aliases,
        reportRow,
        sourceDimension,
        sourceData
      ),
      core_risk_indicators: collectRouteIndicatorsForTarget(
        config.target,
        reportRow,
        sourceDimension,
        analysisItem,
        sourceData,
        report
      ),
    };
  });

  const overallRow = rows.find((row) => row.dimension === '综合风险');
  const detailRows = rows.filter((row) => row.dimension !== '综合风险');
  detailRows.sort((left, right) => {
    const leftScore = typeof left.score === 'number' ? left.score : Number.NEGATIVE_INFINITY;
    const rightScore = typeof right.score === 'number' ? right.score : Number.NEGATIVE_INFINITY;
    return rightScore - leftScore;
  });
  return overallRow ? [overallRow, ...detailRows] : detailRows;
}

function resolveRouteIndicatorAlertCount(
  indicator: string,
  analysisItem: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null,
  sourceDimension: Record<string, unknown> | null,
  targetDimension?: RouteReportTargetDimension
): number | null {
  const direct = parseAlertCount(analysisItem?.alert_count);
  if (direct != null && direct > 0) return direct;
  const dimensionCount = parseAlertCount(sourceDimension?.alert_count);
  if (dimensionCount != null && dimensionCount > 0) return dimensionCount;
  const candidate = findRouteIndicatorCandidate(sourceData, indicator, targetDimension);
  if (candidate?.count != null && candidate.count > 0) return candidate.count;
  return null;
}

function resolveRouteIndicatorRiskScore(
  indicator: string,
  sourceData: Record<string, unknown> | null,
  targetDimension?: RouteReportTargetDimension
): number | null {
  const candidate = findRouteIndicatorCandidate(sourceData, indicator, targetDimension);
  if (candidate?.riskScore != null && candidate.riskScore > 0) return candidate.riskScore;
  if (candidate?.score != null && candidate.score > 0) return candidate.score;
  return null;
}

function buildRouteAnalysisInsightText(
  prefix: string,
  dimension: string,
  score: string,
  indicators: string[],
  indicatorScores: Array<{ indicator: string; score: number | null }>
): string {
  const hasAnyScores = indicatorScores.some((item) => item.score != null);
  const indicatorDetails = indicators
    .map((ind) => {
      const entry = indicatorScores.find((item) => item.indicator === ind);
      if (entry?.score != null) {
        return `{${ind}}{${trimNumberString(entry.score)}}分`;
      }
      return `{${ind}}`;
    })
    .join('、');
  if (hasAnyScores) {
    return `${prefix}{${dimension}}(一级指标)，这是因为${indicatorDetails}风险贡献较高，【说明该维度风险相对突出，需持续跟踪并压降波动。】`;
  }
  return `${prefix}{${dimension}}(一级指标)，其中风险值最高的基础指标是${indicatorDetails}，当前缺少基础指标风险分，【建议结合近30天行为明细、线路黑点分布和干预执行记录进一步复核。】`;
}

function buildRouteAnalysisItems(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const nonOverallRows = rows.filter(
    (row) => typeof row.dimension === 'string' && row.dimension !== '综合风险'
  );
  return nonOverallRows.map((row, index) => {
    const dimension = typeof row.dimension === 'string' ? row.dimension : '—';
    const config = getRouteDimensionConfigByTarget(dimension);
    const analysisItem = config ? findMappedAnalysisItem(report, config.aliases) : null;
    const sourceDimension = config
      ? readFirstRecordAtPaths(sourceData ?? {}, config.sourceDimensionPaths)
      : null;
    const rawIndicatorCandidate =
      (analysisItem && analysisItem.top_indicator) ||
      sourceDimension?.top_indicator ||
      (Array.isArray(row.core_risk_indicators) ? row.core_risk_indicators[0] : null);
    const target = (normalizeRouteDimensionName(dimension) ??
      '综合风险') as RouteReportTargetDimension;
    const topIndicator = normalizeRouteIndicatorText(
      rawIndicatorCandidate,
      target,
      sourceData,
      report
    );
    const allIndicators = Array.isArray(row.core_risk_indicators)
      ? (row.core_risk_indicators as string[]).filter(
          (item) => typeof item === 'string' && item.trim().length > 0 && item !== '—'
        )
      : topIndicator
        ? [topIndicator]
        : [];
    const indicatorsToShow =
      allIndicators.length > 0 ? allIndicators : topIndicator ? [topIndicator] : [];
    const alertCounts = indicatorsToShow.map((ind) => ({
      indicator: ind,
      count: resolveRouteIndicatorAlertCount(ind, analysisItem, sourceData, sourceDimension, target),
    }));
    const indicatorScores = indicatorsToShow.map((ind) => ({
      indicator: ind,
      score: resolveRouteIndicatorRiskScore(ind, sourceData, target),
    }));
    const scoreText = typeof row.score === 'number' ? trimNumberString(row.score) : '—';
    const prefix = ROUTE_REPORT_ANALYSIS_PREFIXES[index] ?? `其次是`;
    return {
      rank_label: prefix,
      dimension,
      top_indicator: topIndicator ?? '',
      alert_count: alertCounts[0]?.count ?? '—',
      insight: buildRouteAnalysisInsightText(
        prefix,
        dimension,
        scoreText,
        indicatorsToShow,
        indicatorScores
      ),
    };
  });
}

function buildRouteAttentionNote(analysisItems: Array<Record<string, unknown>>): string {
  const missingCount = analysisItems.some((item) => {
    const count = item.alert_count;
    return count == null || count === '—';
  });
  if (missingCount) {
    return '【部分维度当前缺少基础指标风险分，建议结合近30天行为明细、线路黑点分布和干预执行记录进一步复核。】';
  }
  const focusIndicators = analysisItems
    .slice(0, 2)
    .map((item) => (typeof item.top_indicator === 'string' ? item.top_indicator : ''))
    .filter((item) => item.length > 0)
    .map((item) => `{${item}}`)
    .join('、');
  return focusIndicators
    ? `【建议优先围绕${focusIndicators}推进线路干预闭环，并持续观察综合风险分是否回落。】`
    : '【建议持续跟踪线路静态短板与动态行为风险的联动变化。】';
}

function buildRouteRecommendations(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const sourceRecommendations = getNestedValue(sourceData ?? {}, 'interventions.recommendations');
  if (Array.isArray(sourceRecommendations) && sourceRecommendations.length > 0) {
    return sourceRecommendations
      .filter((item): item is Record<string, unknown> => isRecord(item))
      .slice(0, 5)
      .map((candidate, index) => {
        const indicator =
          (typeof candidate.indicator === 'string' && candidate.indicator.trim()) ||
          (typeof candidate.title === 'string' && candidate.title.trim()) ||
          `risk_indicator_${index + 1}`;
        const actionText =
          (typeof candidate.action === 'string' && candidate.action.trim()) ||
          (typeof candidate.title === 'string' && candidate.title.trim()) ||
          '';
        const expectedText =
          (typeof candidate.expected_effect === 'string' && candidate.expected_effect.trim()) ||
          (typeof candidate.detail === 'string' && candidate.detail.trim()) ||
          (typeof candidate.rationale === 'string' && candidate.rationale.trim()) ||
          '';
        const policyReference =
          (typeof candidate.policy_reference === 'string' && candidate.policy_reference.trim()) ||
          '—';
        const prefix = ROUTE_REPORT_SUGGESTION_PREFIXES[index] ?? '建议重点关注';
        return {
          priority: index + 1,
          indicator,
          policy_reference: policyReference,
          suggestion: buildRouteRecommendationText(prefix, indicator, actionText, expectedText),
        };
      });
  }

  const globalIndicators = collectRouteIndicatorCandidates(sourceData);
  const seen = new Set<string>();
  const indicatorQueue: Array<{ indicator: string; dimension: RouteReportTargetDimension }> = [];

  for (const candidate of globalIndicators) {
    const key = simplifyRouteIndicatorLabel(candidate.indicator);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    indicatorQueue.push({ indicator: candidate.indicator, dimension: candidate.dimension });
  }

  for (const row of rows) {
    if (typeof row.dimension !== 'string' || row.dimension === '综合风险') continue;
    const indicators = Array.isArray(row.core_risk_indicators) ? row.core_risk_indicators : [];
    for (const ind of indicators) {
      if (typeof ind !== 'string') continue;
      const key = simplifyRouteIndicatorLabel(ind);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      const dim =
        normalizeRouteDimensionName(row.dimension) ?? inferRouteDimensionFromIndicator(ind);
      indicatorQueue.push({ indicator: ind, dimension: dim });
    }
  }

  const maxItems = Math.min(indicatorQueue.length, 5);
  const items = indicatorQueue.slice(0, Math.max(maxItems, 1));

  return items.map((entry, index) => {
    const actionText = NO_MANAGEMENT_SUGGESTION_TEXT;
    const expectedText = '';
    const policyReference = '—';
    const prefixIndex =
      items.length <= 1
        ? 0
        : index === items.length - 1
          ? ROUTE_REPORT_SUGGESTION_PREFIXES.length - 1
          : index;
    const prefix = ROUTE_REPORT_SUGGESTION_PREFIXES[prefixIndex] ?? '建议重点关注';
    return {
      priority: index + 1,
      indicator: entry.indicator,
      policy_reference: policyReference,
      suggestion: buildRouteRecommendationText(prefix, entry.indicator, actionText, expectedText),
    };
  });
}

function buildRouteMajorRiskFactors(
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string[] {
  const reportFactors = getStringArray(
    getNestedValue(report, 'management_summary.major_risk_factors')
  );
  const sourceFactors = collectRouteIndicatorCandidates(sourceData)
    .map((item) => item.indicator)
    .filter((item) => item.length > 0);
  return dedupeRouteIndicatorTexts([...sourceFactors, ...reportFactors]).slice(0, 5);
}

function buildRouteCoreRiskAssessment(
  rows: Array<Record<string, unknown>>,
  analysisItems: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const routeName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.route_name', 'route_name', 'name']) ??
    readFirstStringAtPaths(report, ['management_summary.route_name']) ??
    '—';
  const routeId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.route_id', 'route_id', 'id']) ??
    readFirstStringAtPaths(report, ['management_summary.route_id']) ??
    '—';
  const overallScore =
    readFirstNumberAtPaths(report, ['core_risk_assessment.overall_score']) ??
    buildRouteDimensionAggregateScore('综合风险', sourceData);
  const riskLevel = deriveRiskLevelLabel(
    readFirstStringAtPaths(report, [
      'core_risk_assessment.risk_level',
      'management_summary.risk_level',
    ]) ??
      readFirstStringAtPaths(sourceData ?? {}, [
        'performance_dashboard.summary.overall_level',
        'risk_profile.level',
        'safety_rating.level',
      ]),
    overallScore
  );
  const rankInfo = buildManagementRankInfo(report, sourceData);
  const comparison = buildManagementComparisonText(
    rankInfo.position,
    rankInfo.total,
    rankInfo.percentile,
    '线路'
  );
  const majorRiskFactors = buildRouteMajorRiskFactors(sourceData, report);
  const orderedDimensions = rows
    .map((row) => (typeof row.dimension === 'string' ? `{${row.dimension}}` : ''))
    .filter((item) => item.length > 0)
    .join('、');
  const factorText = majorRiskFactors.length
    ? majorRiskFactors.map((item) => `{${item}}`).join('、')
    : '当前缺少完整的高风险因子明细';
  const rankSentence =
    rankInfo.position != null && rankInfo.total != null && comparison.verb
      ? `综合表现位于所属单位第{${rankInfo.position}}名{(${rankInfo.position}/${rankInfo.total})}，显示其{${comparison.verb}}多数线路`
      : rankInfo.position != null
        ? `综合排名为第{${rankInfo.position}}名`
        : '当前缺少完整排名快照';
  const topIndicators = analysisItems
    .slice(0, 2)
    .map((item) => (typeof item.top_indicator === 'string' ? `{${item.top_indicator}}` : ''))
    .filter((item) => item.length > 0)
    .join('、');
  const summary = `综合近期运行数据判断，线路{${routeName}}(线路ID{${routeId}})综合风险值为{${
    overallScore != null ? trimNumberString(overallScore) : '—'
  }}分，当前处于{${riskLevel}}状态，三个一级指标由高到低依次为${orderedDimensions}，主要风险因素为${factorText}，${rankSentence}，【说明当前风险主要集中在${
    topIndicators || '多个维度'
  }，需同步推进静态环境治理与动态行为干预。】`;

  return {
    summary,
    overall_score: overallScore,
    risk_level: riskLevel,
    rank: {
      position: rankInfo.position,
      total: rankInfo.total,
      display: rankInfo.display,
    },
    comparison: comparison.label,
    attention_note: buildRouteAttentionNote(analysisItems),
    detail_lines: [],
  };
}

function buildRouteManagementSummary(
  rows: Array<Record<string, unknown>>,
  coreRiskAssessment: Record<string, unknown>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const routeName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.route_name', 'route_name', 'name']) ??
    readFirstStringAtPaths(report, ['management_summary.route_name']) ??
    '—';
  const routeId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.route_id', 'route_id', 'id']) ??
    readFirstStringAtPaths(report, ['management_summary.route_id']) ??
    '—';
  const fleetName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.fleet_name', 'fleet_name', 'branch_name']) ??
    readFirstStringAtPaths(report, ['management_summary.fleet_name']) ??
    '—';
  const overallScore = readFirstNumberAtPaths(coreRiskAssessment, ['overall_score']);
  const riskLevel =
    readFirstStringAtPaths(coreRiskAssessment, ['risk_level']) ||
    deriveRiskLevelLabel(
      readFirstStringAtPaths(sourceData ?? {}, [
        'performance_dashboard.summary.overall_level',
        'risk_profile.level',
        'safety_rating.level',
      ]),
      overallScore
    );
  const reportDate = buildManagementReportDate(report, sourceData);
  const majorRiskFactors = buildRouteMajorRiskFactors(sourceData, report);
  const rankPosition = readFirstNumberAtPaths(coreRiskAssessment, ['rank.position']);
  const rankTotal = readFirstNumberAtPaths(coreRiskAssessment, ['rank.total']);
  const comparison =
    readFirstStringAtPaths(coreRiskAssessment, ['comparison']) ?? '当前缺少完整排名快照';
  const orderedDimensions = rows
    .map((row) => (typeof row.dimension === 'string' ? `{${row.dimension}}` : ''))
    .filter((item) => item.length > 0)
    .join('、');
  const factorText = majorRiskFactors.length
    ? majorRiskFactors.map((item) => `{${item}}`).join('、')
    : '当前缺少完整的高风险因子明细';
  const rankText =
    rankPosition != null && rankTotal != null
      ? `综合表现位于所属单位第{${rankPosition}}名{(${rankPosition}/${rankTotal})}，${comparison}`
      : rankPosition != null
        ? `综合排名为第{${rankPosition}}名`
        : '当前缺少完整排名快照';
  const summaryText = `${
    reportDate !== '—' ? `{${reportDate}}` : ''
  }线路{${routeName}}被判定为{${riskLevel}}状态，综合风险值为{${
    overallScore != null ? trimNumberString(overallScore) : '—'
  }}分，三个一级指标由高到低依次为${orderedDimensions}，主要风险因素为${factorText}，${rankText}，【需优先关注静态环境短板与动态风险触发的叠加效应，并持续跟踪干预闭环。】`;

  return {
    report_date: reportDate,
    route_name: routeName,
    route_id: routeId,
    fleet_name: fleetName,
    risk_level: riskLevel,
    major_risk_factors: majorRiskFactors,
    summary_text: summaryText,
  };
}

function buildRouteLayout(summaryText: string): Record<string, unknown> {
  return {
    title: '线路安全风险分析总结报告',
    summary: summaryText,
    header: {
      items: [
        { label: '线路', value_path: 'management_summary.route_name' },
        { label: '所属单位', value_path: 'management_summary.fleet_name' },
        { label: '风险状态', value_path: 'management_summary.risk_level', highlight: true },
      ],
    },
    sections: [
      {
        title: '一、多维绩效看板',
        blocks: [
          {
            type: 'table',
            columns: [
              { title: '核心维度', key: 'dimension' },
              { title: '风险得分', key: 'score' },
              { title: '趋势表现', key: 'trend_text' },
              { title: '核心风险指标', key: 'core_risk_indicators' },
            ],
            rows_path: 'dashboard_rows',
          },
        ],
      },
      {
        title: '二、核心风险研判',
        blocks: [{ type: 'text', text_path: 'core_risk_assessment.summary' }],
      },
      {
        title: '三、行为与数据关联分析',
        blocks: [
          {
            type: 'list',
            items_path: 'behavior_data_analysis.analysis_items',
            ordered: false,
          },
        ],
      },
      {
        title: '四、针对性干预建议',
        blocks: [{ type: 'list', items_path: 'interventions.recommendations', ordered: false }],
      },
      {
        title: '附录（原始数据）',
        collapsible: true,
        default_open: false,
        blocks: [{ type: 'json', title: '原始数据', data_path: 'appendix' }],
      },
    ],
  };
}

function buildRouteAppendix(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const rawData =
    readRecordAtPath(sourceData ?? {}, 'appendix.raw_data') ??
    sourceData ??
    readRecordAtPath(report, 'appendix.raw_data') ??
    {};
  return { raw_data: rawData };
}

export function normalizeRouteManagementReport(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  if (readStringAtPath(report, 'error')) {
    return report;
  }

  const rows = buildRouteDashboardRows(report, sourceData);
  const analysisItems = buildRouteAnalysisItems(rows, report, sourceData);
  const recommendations = buildRouteRecommendations(rows, report, sourceData);
  const coreRiskAssessment = buildRouteCoreRiskAssessment(rows, analysisItems, report, sourceData);
  const managementSummary = buildRouteManagementSummary(
    rows,
    coreRiskAssessment,
    report,
    sourceData
  );

  return {
    report_type: 'route_safety_summary_management',
    template_version: '20260305',
    report_role: 'management',
    layout: buildRouteLayout(
      typeof managementSummary.summary_text === 'string' ? managementSummary.summary_text : ''
    ),
    management_summary: managementSummary,
    dashboard_rows: rows,
    core_risk_assessment: coreRiskAssessment,
    behavior_data_analysis: { analysis_items: analysisItems },
    interventions: { recommendations },
    appendix: buildRouteAppendix(report, sourceData),
  };
}

export function hasRouteTemplateMarkerNotation(report: Record<string, unknown>): boolean {
  return hasStructuredReportTemplateMarkerNotation(report);
}

export function hasCompleteRouteManagementReport(report: Record<string, unknown>): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  if (readStringAtPath(report, 'report_type') !== 'route_safety_summary_management') {
    return false;
  }
  if (readStringAtPath(report, 'report_role') !== 'management') {
    return false;
  }

  const requiredRecords = [
    'layout',
    'management_summary',
    'core_risk_assessment',
    'behavior_data_analysis',
    'interventions',
    'appendix',
  ];
  if (requiredRecords.some((path) => !isRecord(getNestedValue(report, path)))) {
    return false;
  }

  const rows = getNestedValue(report, 'dashboard_rows');
  if (!Array.isArray(rows) || rows.length !== ROUTE_REPORT_TARGET_DIMENSIONS.length) {
    return false;
  }
  const dimensions = rows
    .map((row) => (isRecord(row) && typeof row.dimension === 'string' ? row.dimension.trim() : ''))
    .filter((item) => item.length > 0);
  if (
    dimensions[0] !== '综合风险' ||
    !ROUTE_REPORT_TARGET_DIMENSIONS.every((dim) => dimensions.includes(dim))
  ) {
    return false;
  }

  const summaryText = readStringAtPath(report, 'management_summary.summary_text') ?? '';
  const coreSummary = readStringAtPath(report, 'core_risk_assessment.summary') ?? '';
  if (!summaryText || !coreSummary) {
    return false;
  }

  const analysisItems = getNestedValue(report, 'behavior_data_analysis.analysis_items');
  if (!Array.isArray(analysisItems)) {
    return false;
  }

  const recommendations = getNestedValue(report, 'interventions.recommendations');
  if (
    !Array.isArray(recommendations) ||
    recommendations.length === 0 ||
    recommendations.length > 5
  ) {
    return false;
  }

  return true;
}
