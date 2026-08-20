import { isRecord } from '../../shared/guards';
import { getNestedValue } from '../../shared/object-path';

const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';

function readStringAtPath(source: Record<string, unknown>, path: string): string | null {
  const value = getNestedValue(source, path);
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function hasStructuredReportTemplateMarkerNotation(report: Record<string, unknown>): boolean {
  const errorCode = readStringAtPath(report, 'error');
  if (errorCode) {
    return true;
  }

  const texts: string[] = [];
  const directPaths = [
    'layout.summary',
    'management_summary.summary_text',
    'core_risk_assessment.summary',
    'core_risk_assessment.attention_note',
  ];
  for (const path of directPaths) {
    const value = readStringAtPath(report, path);
    if (value) {
      texts.push(value);
    }
  }

  const analysisItems = getNestedValue(report, 'behavior_data_analysis.analysis_items');
  if (Array.isArray(analysisItems)) {
    for (const item of analysisItems) {
      if (!isRecord(item)) continue;
      const insight = typeof item.insight === 'string' ? item.insight.trim() : '';
      if (insight) {
        texts.push(insight);
      }
    }
  }

  const recommendations = getNestedValue(report, 'interventions.recommendations');
  if (Array.isArray(recommendations)) {
    for (const item of recommendations) {
      if (!isRecord(item)) continue;
      const suggestion = typeof item.suggestion === 'string' ? item.suggestion.trim() : '';
      if (suggestion) {
        texts.push(suggestion);
      }
    }
  }

  if (!texts.length) {
    return false;
  }

  const hasDataMarker = texts.some((text) => /\{[^{}\r\n]+\}/.test(text));
  const hasAiMarker = texts.some((text) => /【[^【】\r\n]+】/.test(text));
  return hasDataMarker && hasAiMarker;
}

function hasDriverTemplateMarkerNotation(report: Record<string, unknown>): boolean {
  return hasStructuredReportTemplateMarkerNotation(report);
}

const DRIVER_REPORT_TARGET_DIMENSIONS = ['事故风险', '能耗风险', '服务态度', '安全评价'] as const;
const DRIVER_REPORT_DASHBOARD_DIMENSIONS = [
  '综合风险',
  ...DRIVER_REPORT_TARGET_DIMENSIONS,
] as const;
type DriverReportTargetDimension = (typeof DRIVER_REPORT_TARGET_DIMENSIONS)[number];
type DriverDashboardDimension = (typeof DRIVER_REPORT_DASHBOARD_DIMENSIONS)[number];

const DRIVER_REPORT_ANALYSIS_PREFIXES = ['风险最高的一级指标是', '其次是', '再次是', '最后是'];

const DRIVER_REPORT_DIMENSION_ALIASES: Array<{
  target: DriverReportTargetDimension;
  aliases: string[];
}> = [
  { target: '事故风险', aliases: ['事故风险', '综合安全'] },
  { target: '能耗风险', aliases: ['能耗风险', '行车技能'] },
  { target: '服务态度', aliases: ['服务态度', '驾驶态度'] },
  { target: '安全评价', aliases: ['安全评价', '行为习惯'] },
];

const DRIVER_REPORT_SUGGESTION_PREFIXES = ['风险最高的基础指标是', '其次是', '再次是', '最后是'];

function readNumberAtPath(source: Record<string, unknown>, path: string): number | null {
  const value = getNestedValue(source, path);
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value.trim().replace(/%$/, ''));
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function orderDashboardRowsByOverallThenScore(
  rows: Array<Record<string, unknown>>,
  overallDimension: string
): Array<Record<string, unknown>> {
  const overallRow = rows.find((row) => row.dimension === overallDimension);
  const detailRows = rows
    .filter((row) => row.dimension !== overallDimension)
    .sort((left, right) => {
      const leftScore = typeof left.score === 'number' ? left.score : Number.NEGATIVE_INFINITY;
      const rightScore = typeof right.score === 'number' ? right.score : Number.NEGATIVE_INFINITY;
      return rightScore - leftScore;
    });
  return overallRow ? [overallRow, ...detailRows] : detailRows;
}

function readArrayAtPath(source: Record<string, unknown>, path: string): unknown[] | null {
  const value = getNestedValue(source, path);
  return Array.isArray(value) ? value : null;
}

function readRecordAtPath(
  source: Record<string, unknown>,
  path: string
): Record<string, unknown> | null {
  const value = getNestedValue(source, path);
  return isRecord(value) ? value : null;
}

function trimNumberString(value: number): string {
  return value
    .toFixed(2)
    .replace(/\.00$/, '')
    .replace(/(\.\d)0$/, '$1');
}

function formatPercentValue(value: unknown): string {
  if (typeof value === 'string' && value.trim()) {
    const trimmed = value.trim();
    if (trimmed === '—') return trimmed;
    return trimmed.includes('%') ? trimmed : `${trimmed}%`;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return `${trimNumberString(value)}%`;
  }
  return '—';
}

function toFiniteTrendNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function formatTrendMetricValue(value: unknown): string {
  const numberValue = toFiniteTrendNumber(value);
  if (numberValue == null) return '—';
  const normalized = Number(numberValue.toFixed(2));
  const text = String(normalized)
    .replace(/\.0+$/, '')
    .replace(/(\.\d*[1-9])0+$/, '$1');
  return `${normalized > 0 ? '+' : ''}${text}%`;
}

function hasConcreteTrendText(value: string | null | undefined): boolean {
  return typeof value === 'string' && /\d/.test(value);
}

function buildTrendTextFromSummaryRecord(
  row: Record<string, unknown> | null,
  includeRouteComparison = true
): string | null {
  if (!row) return null;
  const directText = typeof row.trend_text === 'string' ? row.trend_text.trim() : '';
  if (hasConcreteTrendText(directText)) return directText;

  const hasTrendValue = [
    'previous_period_risk_value',
    'last_year_same_date_risk_value',
    'organ_avg_risk_value',
    'route_avg_risk_value',
    'previousPeriodRiskValue',
    'lastYearSameDateRiskValue',
    'organAvgRiskValue',
    'routeAvgRiskValue',
    'mom',
    'yoy',
    'unit',
    'route',
  ].some((key) => toFiniteTrendNumber(row[key]) != null);
  if (!hasTrendValue) return null;

  const base = `同比${formatTrendMetricValue(
    row.last_year_same_date_risk_value ?? row.lastYearSameDateRiskValue ?? row.yoy
  )}，环比${formatTrendMetricValue(
    row.previous_period_risk_value ?? row.previousPeriodRiskValue ?? row.mom
  )}，同单位比${formatTrendMetricValue(
    row.organ_avg_risk_value ?? row.organAvgRiskValue ?? row.unit
  )}`;
  const routeValue = row.route_avg_risk_value ?? row.routeAvgRiskValue ?? row.route;
  return includeRouteComparison && toFiniteTrendNumber(routeValue) != null
    ? `${base}，同线路比${formatTrendMetricValue(routeValue)}`
    : base;
}

function normalizeTrendMatchKey(value: unknown): string {
  return simplifyIndicatorLabel(value);
}

function findTrendSummaryRecord(
  sourceData: Record<string, unknown> | null,
  keys: unknown[],
  allowOverallFallback = false
): Record<string, unknown> | null {
  const trends =
    readArrayAtPath(sourceData ?? {}, 'appendix.raw_data.trend_summary') ??
    readArrayAtPath(sourceData ?? {}, 'raw_data.trend_summary') ??
    readArrayAtPath(sourceData ?? {}, 'trend_summary') ??
    [];
  const records = trends.filter((item): item is Record<string, unknown> => isRecord(item));
  if (!records.length) return null;

  const normalizedKeys = keys.map((item) => normalizeTrendMatchKey(item)).filter(Boolean);
  for (const row of records) {
    const rowKeys = [row.dimension, row.quota_name, row.quotaName, row.quota_id, row.quotaId].map(
      (item) => normalizeTrendMatchKey(item)
    );
    if (
      rowKeys.some((rowKey) =>
        normalizedKeys.some((key) => rowKey === key || rowKey.includes(key) || key.includes(rowKey))
      )
    ) {
      return row;
    }
  }

  if (!allowOverallFallback) return null;
  return (
    records.slice().sort((left, right) => {
      const leftScore =
        toFiniteTrendNumber(left.converted_score ?? left.convertedScore) ??
        toFiniteTrendNumber(left.current_risk_value ?? left.currentRiskValue) ??
        Number.NEGATIVE_INFINITY;
      const rightScore =
        toFiniteTrendNumber(right.converted_score ?? right.convertedScore) ??
        toFiniteTrendNumber(right.current_risk_value ?? right.currentRiskValue) ??
        Number.NEGATIVE_INFINITY;
      return rightScore - leftScore;
    })[0] ?? null
  );
}

function resolveDashboardTrendText(input: {
  reportRow?: Record<string, unknown> | null;
  sourceDimension?: Record<string, unknown> | null;
  sourceData?: Record<string, unknown> | null;
  keys?: unknown[];
  includeRouteComparison?: boolean;
  allowOverallFallback?: boolean;
  defaultText: string;
}): string {
  const existing =
    typeof input.reportRow?.trend_text === 'string' ? input.reportRow.trend_text.trim() : '';
  if (hasConcreteTrendText(existing)) return existing;

  const sourceTrendText =
    typeof input.sourceDimension?.trend_text === 'string'
      ? input.sourceDimension.trend_text.trim()
      : '';
  if (hasConcreteTrendText(sourceTrendText)) return sourceTrendText;

  const keys = [
    ...(input.keys ?? []),
    input.sourceDimension?.dimension,
    input.sourceDimension?.quota_name,
    input.sourceDimension?.quotaName,
    input.sourceDimension?.quota_id,
    input.sourceDimension?.quotaId,
    input.reportRow?.dimension,
  ];
  const trendText = buildTrendTextFromSummaryRecord(
    findTrendSummaryRecord(input.sourceData ?? null, keys, input.allowOverallFallback ?? false),
    input.includeRouteComparison ?? true
  );
  if (trendText) return trendText;

  const trendDelta = input.sourceDimension?.trend_delta;
  return (
    existing ||
    sourceTrendText ||
    (trendDelta == null
      ? input.defaultText
      : input.defaultText.replace('环比—', `环比${formatPercentValue(trendDelta)}`))
  );
}

function formatDateToCn(value: string | null): string | null {
  if (!value) return null;
  const match = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const [, year, month, day] = match;
  return `${year}年${Number(month)}月${Number(day)}日`;
}

function normalizeRiskLevelLabel(value: string | null): string {
  const trimmed = value?.replace(/[{}【】]/g, '').trim() ?? '';
  if (!trimmed) return '—';
  const mapping: Record<string, string> = {
    安全型: '安全',
    观察型: '观察',
    关注型: '关注',
    危险型: '危险',
    观察风险: '观察',
    关注风险: '关注',
    中等风险: '关注',
    危险风险: '危险',
    正常: '安全',
    低风险: '观察',
    较低: '观察',
    一般: '关注',
    中等: '关注',
    中风险: '关注',
    较高: '危险',
    高风险: '危险',
    安全: '安全',
    观察: '观察',
    关注: '关注',
    危险: '危险',
  };
  return mapping[trimmed] || trimmed;
}

function hasMeaningfulRiskLevelLabel(value: string | null): boolean {
  const trimmed = value?.replace(/[{}【】]/g, '').trim() ?? '';
  if (!trimmed) return false;
  return !/^(?:—|-|未知|未评估|待评估|暂无|N\/A|n\/a|null|none|\?+|？+)$/i.test(trimmed);
}

function deriveRiskLevelLabel(value: string | null, score: number | null): string {
  if (hasMeaningfulRiskLevelLabel(value)) {
    return normalizeRiskLevelLabel(value);
  }
  if (score == null || !Number.isFinite(score)) {
    return '—';
  }
  if (score >= 65) return '危险';
  if (score >= 55) return '关注';
  if (score >= 45) return '观察';
  return '安全';
}

function simplifyIndicatorLabel(value: unknown): string {
  if (typeof value !== 'string') return '';
  return value
    .replace(/[（(][^）)]*[）)]/g, '')
    .replace(/\s+/g, '')
    .trim();
}

function getStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
}

function parseAlertCount(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const match = value.match(/(\d+(?:\.\d+)?)/);
    if (match) {
      const parsed = Number(match[1]);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return null;
}

function looksLikeLegacyDriverDimensionText(value: string): boolean {
  const simplified = simplifyIndicatorLabel(value);
  if (!simplified) return false;
  return DRIVER_REPORT_DIMENSION_ALIASES.some((config) =>
    config.aliases.some((alias) => simplified.includes(alias))
  );
}

function getDriverIndicatorFallback(
  targetDimension: string,
  sourceDimension: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null
): string {
  const candidates: string[] = [];
  const bizNote = simplifyIndicatorLabel(sourceDimension?.biz_note);
  if (bizNote && !/(核心考核指标|绩效总览)/.test(bizNote)) {
    candidates.push(bizNote);
  }
  if (targetDimension === '事故风险' && sourceData) {
    const systemTags = getStringArray(
      getNestedValue(sourceData, 'performance_dashboard.system_risk.tags')
    )
      .map((item) => simplifyIndicatorLabel(item))
      .filter((item) => item.length > 0 && !item.includes('评分下滑'));
    candidates.push(...systemTags);
  }
  return candidates.find((item, index) => item && candidates.indexOf(item) === index) || '';
}

function normalizeDriverIndicatorText(
  rawIndicator: unknown,
  targetDimension: string,
  sourceDimension: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null
): string {
  const simplified = simplifyIndicatorLabel(rawIndicator);
  if (simplified && !looksLikeLegacyDriverDimensionText(simplified)) {
    return simplified;
  }
  return getDriverIndicatorFallback(targetDimension, sourceDimension, sourceData);
}

function replaceLegacyDriverDimensionMentions(value: string): string {
  let next = value;
  for (const config of DRIVER_REPORT_DIMENSION_ALIASES) {
    for (const alias of config.aliases.slice(1)) {
      next = next.replace(new RegExp(alias, 'g'), config.target);
    }
  }
  return next;
}

function getDriverDimensionConfigByTarget(
  target: string
): { target: DriverReportTargetDimension; aliases: string[] } | null {
  return DRIVER_REPORT_DIMENSION_ALIASES.find((item) => item.target === target) ?? null;
}

function getDriverDimensionConfigByAlias(
  alias: string
): { target: DriverReportTargetDimension; aliases: string[] } | null {
  return DRIVER_REPORT_DIMENSION_ALIASES.find((item) => item.aliases.includes(alias)) ?? null;
}

function getDriverSourceDimension(
  sourceData: Record<string, unknown> | null,
  aliases: string[]
): Record<string, unknown> | null {
  if (!sourceData) return null;
  return (
    aliases
      .map((alias) => readRecordAtPath(sourceData, `performance_dashboard.dimensions.${alias}`))
      .find((item) => item != null) ?? null
  );
}

function findMappedDashboardRow(
  report: Record<string, unknown>,
  aliases: string[]
): Record<string, unknown> | null {
  const rows = getNestedValue(report, 'dashboard_rows');
  if (!Array.isArray(rows)) return null;
  for (const row of rows) {
    if (!isRecord(row)) continue;
    const dimension = typeof row.dimension === 'string' ? row.dimension.trim() : '';
    if (aliases.includes(dimension)) {
      return row;
    }
  }
  return null;
}

function findMappedAnalysisItem(
  report: Record<string, unknown>,
  aliases: string[]
): Record<string, unknown> | null {
  const items = getNestedValue(report, 'behavior_data_analysis.analysis_items');
  if (!Array.isArray(items)) return null;
  for (const item of items) {
    if (!isRecord(item)) continue;
    const dimension = typeof item.dimension === 'string' ? item.dimension.trim() : '';
    if (aliases.includes(dimension)) {
      return item;
    }
  }
  return null;
}

function listRecommendationCandidates(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const pools: Record<string, unknown>[] = [];
  const reportRecommendations = getNestedValue(report, 'interventions.recommendations');
  if (Array.isArray(reportRecommendations)) {
    for (const item of reportRecommendations) {
      if (isRecord(item)) pools.push(item);
    }
  }
  if (sourceData) {
    const sourceRecommendations = getNestedValue(sourceData, 'interventions.recommendations');
    if (Array.isArray(sourceRecommendations)) {
      for (const item of sourceRecommendations) {
        if (isRecord(item)) pools.push(item);
      }
    }
    pools.push(...listRawSuggestionRecommendations(sourceData));
  }
  return pools;
}

function getRecommendationCandidateIndicator(item: Record<string, unknown>): string {
  return simplifyIndicatorLabel(
    (typeof item.indicator === 'string' ? item.indicator : '') ||
      (typeof item.title === 'string' ? item.title : '')
  );
}

function hasStructuredRecommendationPayload(item: Record<string, unknown>): boolean {
  return Boolean(
    (typeof item.action === 'string' && item.action.trim()) ||
    (typeof item.title === 'string' && item.title.trim()) ||
    (typeof item.expected_effect === 'string' && item.expected_effect.trim()) ||
    (typeof item.detail === 'string' && item.detail.trim()) ||
    (typeof item.rationale === 'string' && item.rationale.trim())
  );
}

function listRawSuggestionRecommendations(
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  if (!sourceData) return [];

  const rawSuggestions = getNestedValue(sourceData, 'appendix.raw_data.suggestions');
  if (!Array.isArray(rawSuggestions)) return [];

  return rawSuggestions
    .filter((item): item is Record<string, unknown> => isRecord(item))
    .map((item) => ({
      indicator:
        (typeof item.quota_name === 'string' && item.quota_name.trim()) ||
        (typeof item.indicator === 'string' && item.indicator.trim()) ||
        '',
      action:
        (typeof item.suggested_content === 'string' && item.suggested_content.trim()) ||
        (typeof item.action === 'string' && item.action.trim()) ||
        '',
      expected_effect:
        (typeof item.expected_effect === 'string' && item.expected_effect.trim()) ||
        (typeof item.detail === 'string' && item.detail.trim()) ||
        '',
      policy_reference:
        (typeof item.dispose_status === 'string' && item.dispose_status.trim()) ||
        (typeof item.accept_status === 'string' && item.accept_status.trim()) ||
        '',
      ...(typeof item.first_quota_name === 'string' && item.first_quota_name.trim()
        ? { dimension: item.first_quota_name.trim() }
        : {}),
      ...(typeof item.score === 'number' && Number.isFinite(item.score)
        ? { score: item.score }
        : {}),
      source: 'mcp_suggested_sub',
    }))
    .filter((item) => typeof item.indicator === 'string' && item.indicator.trim());
}

function normalizeRecommendationActionText(value: string): string {
  return value.trim().replace(/[。．.!！；;，,]+$/u, '');
}

function isNoManagementSuggestionText(value: string): boolean {
  return normalizeRecommendationActionText(value) === NO_MANAGEMENT_SUGGESTION_TEXT;
}

function listSourceRecommendations(
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  if (!sourceData) return [];

  const structured = listRecommendationCandidates({}, sourceData).filter(
    hasStructuredRecommendationPayload
  );
  if (structured.length > 0) {
    return structured.slice(0, 4);
  }

  return listRawSuggestionRecommendations(sourceData).slice(0, 4);
}

function buildDriverRecommendationText(
  prefix: string,
  indicator: string,
  actionText: string,
  expectedText: string
): string {
  const normalizedActionText = normalizeRecommendationActionText(actionText);
  const normalizedExpectedText = expectedText.trim();
  if (isNoManagementSuggestionText(normalizedActionText)) {
    return `${prefix}{${indicator}}，${NO_MANAGEMENT_SUGGESTION_TEXT}。`;
  }
  if (!normalizedExpectedText) {
    return `${prefix}{${indicator}}，建议开展{${normalizedActionText}}。`;
  }
  return `${prefix}{${indicator}}，建议开展{${normalizedActionText}}，【${normalizedExpectedText}】。`;
}

function resolveIndicatorAlertCount(
  indicator: string,
  analysisItem: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null,
  sourceDimension: Record<string, unknown> | null
): number | null {
  const direct = parseAlertCount(analysisItem?.alert_count);
  if (direct != null && direct > 0) return direct;
  const dimensionCount = parseAlertCount(sourceDimension?.alert_count);
  if (dimensionCount != null && dimensionCount > 0) return dimensionCount;
  if (!sourceData) return null;

  const tags = readArrayAtPath(sourceData, 'performance_dashboard.system_risk.tags') ?? [];
  for (const tag of tags) {
    if (typeof tag !== 'string') continue;
    if (simplifyIndicatorLabel(tag).includes(indicator)) {
      const parsed = parseAlertCount(tag);
      if (parsed != null && parsed > 0) return parsed;
    }
  }

  const alertCounts = readRecordAtPath(sourceData, 'appendix.raw_data.alerts_counts');
  if (alertCounts) {
    for (const [key, value] of Object.entries(alertCounts)) {
      if (simplifyIndicatorLabel(key).includes(indicator)) {
        const parsed = parseAlertCount(value);
        if (parsed != null && parsed > 0) return parsed;
      }
    }
  }

  return null;
}

function buildNormalizedTrendText(
  reportRow: Record<string, unknown> | null,
  sourceDimension: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null = null,
  keys: unknown[] = []
): string {
  return resolveDashboardTrendText({
    reportRow,
    sourceDimension,
    sourceData,
    keys,
    includeRouteComparison: true,
    defaultText: '同比—，环比—，同单位比—，同线路比—',
  });
}

type DriverIndicatorCandidate = {
  indicator: string;
  dimension: DriverReportTargetDimension;
  score: number | null;
  riskScore: number | null;
  count: number | null;
};

function buildDriverOverallTrendText(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): string {
  const reportRow = findMappedDashboardRow(report, ['综合风险', '综合安全']);
  const sourceDimension =
    readFirstRecordAtPaths(sourceData ?? {}, [
      'performance_dashboard.dimensions.综合风险',
      'performance_dashboard.summary',
    ]) ?? null;
  return resolveDashboardTrendText({
    reportRow,
    sourceDimension,
    sourceData,
    keys: ['综合风险', '综合安全'],
    includeRouteComparison: true,
    allowOverallFallback: true,
    defaultText: '同比—，环比—，同单位比—，同线路比—',
  });
}

function normalizeDriverAnalysisIndicatorText(
  rawIndicator: unknown,
  targetDimension: DriverReportTargetDimension,
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string {
  const sourceDimension = getDriverSourceDimension(
    sourceData,
    getDriverDimensionConfigByTarget(targetDimension)?.aliases ?? [targetDimension]
  );
  return normalizeDriverIndicatorText(
    rawIndicator,
    targetDimension,
    sourceDimension,
    sourceData
  ).trim();
}

function getDriverDimensionSortScore(row: Record<string, unknown>): number {
  return typeof row.score === 'number' ? row.score : Number.NEGATIVE_INFINITY;
}

function inferDriverDimensionFromIndicator(indicator: string): DriverReportTargetDimension {
  if (/(投诉|服务|礼让乘客|服务用语|乘客|沟通|安全管理|车辆技术)/i.test(indicator)) {
    return '服务态度';
  }
  if (
    /(起步|安全启动|观察|N档|手刹|关门|车门|禁启|安全带|转弯未刹车|右转弯未停车)/i.test(indicator)
  ) {
    return '安全评价';
  }
  if (
    /(急加速|急减速|急刹车|空档滑行|熄火滑行|超速|油耗|能耗|空调|平顺|进站|出站|鸣笛)/i.test(
      indicator
    )
  ) {
    return '能耗风险';
  }
  return '事故风险';
}

function dedupeDriverIndicatorTexts(values: string[]): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    const normalized = simplifyIndicatorLabel(trimmed);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    next.push(trimmed);
  }
  return next;
}

function collectDriverIndicatorCandidates(
  sourceData: Record<string, unknown> | null
): DriverIndicatorCandidate[] {
  if (!sourceData) return [];
  const candidates: DriverIndicatorCandidate[] = [];

  const pushCandidate = (
    rawIndicator: unknown,
    dimension: DriverReportTargetDimension,
    score: number | null,
    riskScore: number | null,
    count: number | null
  ) => {
    const indicator = simplifyIndicatorLabel(rawIndicator);
    if (!indicator || looksLikeLegacyDriverDimensionText(indicator)) return;
    candidates.push({ indicator, dimension, score, riskScore: riskScore ?? score, count });
  };

  const quotaItems = readArrayAtPath(sourceData, 'appendix.raw_data.quota_items') ?? [];
  for (const item of quotaItems) {
    if (!isRecord(item)) continue;
    const dimension = getDriverDimensionConfigByAlias(String(item.dimension ?? '').trim())?.target;
    if (!dimension) continue;
    pushCandidate(
      item.quota_name ?? item.name ?? item.indicator,
      dimension,
      parseAlertCount(item.score),
      parseAlertCount(item.final_risk_score ?? item.risk_score ?? item.original_value),
      parseAlertCount(item.count ?? item.alert_count)
    );
  }

  for (const config of DRIVER_REPORT_DIMENSION_ALIASES) {
    const sourceDimension = getDriverSourceDimension(sourceData, config.aliases);
    const dimensionScore = sourceDimension
      ? readNumberAtPath({ root: sourceDimension }, 'root.score')
      : null;
    const directCount = sourceDimension ? parseAlertCount(sourceDimension.alert_count) : null;
    const indicators = [
      ...(sourceDimension
        ? getStringArray(getNestedValue(sourceDimension, 'core_risk_indicators'))
        : []),
      simplifyIndicatorLabel(sourceDimension?.top_indicator),
    ].filter((item) => item.length > 0);
    for (const indicator of indicators) {
      pushCandidate(indicator, config.target, dimensionScore, null, directCount);
    }
  }

  const analysisItems = readArrayAtPath(sourceData, 'behavior_data_analysis.analysis_items') ?? [];
  for (const item of analysisItems) {
    if (!isRecord(item)) continue;
    const dimension = getDriverDimensionConfigByAlias(String(item.dimension ?? '').trim())?.target;
    const inferredDimension: DriverReportTargetDimension =
      dimension ??
      inferDriverDimensionFromIndicator(
        simplifyIndicatorLabel(item.top_indicator ?? item.indicator ?? item.title)
      );
    pushCandidate(
      item.top_indicator ?? item.indicator ?? item.title,
      inferredDimension,
      null,
      null,
      parseAlertCount(item.alert_count ?? item.count)
    );
  }

  const systemTags = readArrayAtPath(sourceData, 'performance_dashboard.system_risk.tags') ?? [];
  for (const tag of systemTags) {
    if (typeof tag !== 'string') continue;
    const indicator = simplifyIndicatorLabel(tag.replace(/\([^)]*\)/g, ''));
    if (!indicator) continue;
    pushCandidate(
      indicator,
      inferDriverDimensionFromIndicator(indicator),
      null,
      null,
      parseAlertCount(tag)
    );
  }

  const alertCounts =
    readRecordAtPath(sourceData, 'appendix.raw_data.alerts_counts') ??
    readRecordAtPath(sourceData, 'alerts_counts');
  if (alertCounts) {
    for (const [key, value] of Object.entries(alertCounts)) {
      pushCandidate(
        key,
        inferDriverDimensionFromIndicator(key),
        null,
        null,
        parseAlertCount(value)
      );
    }
  }

  const deduped = new Map<string, DriverIndicatorCandidate>();
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
    const leftScore = left.score ?? Number.NEGATIVE_INFINITY;
    const rightScore = right.score ?? Number.NEGATIVE_INFINITY;
    if (rightScore !== leftScore) return rightScore - leftScore;
    const leftCount = left.count ?? Number.NEGATIVE_INFINITY;
    const rightCount = right.count ?? Number.NEGATIVE_INFINITY;
    return rightCount - leftCount;
  });
}

function buildDriverMajorRiskFactors(
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string[] {
  const reportFactors = getStringArray(
    getNestedValue(report, 'management_summary.major_risk_factors')
  );
  const sourceFactors = collectDriverIndicatorCandidates(sourceData)
    .map((item) => item.indicator)
    .filter((item) => item.length > 0);
  return dedupeDriverIndicatorTexts([...sourceFactors, ...reportFactors]).slice(0, 4);
}

function buildDriverDashboardRowsV2(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const majorRiskFactors = buildDriverMajorRiskFactors(sourceData, report);
  const overallScore =
    readFirstNumberAtPaths(report, ['core_risk_assessment.overall_score']) ??
    readFirstNumberAtPaths(sourceData ?? {}, [
      'performance_dashboard.summary.overall_score',
      'performance_dashboard.dimensions.综合风险.score',
    ]);
  const overallRow = {
    dimension: '综合风险',
    score: overallScore,
    trend_text: buildDriverOverallTrendText(report, sourceData),
    core_risk_indicators: majorRiskFactors.length ? majorRiskFactors : [],
  };

  const detailRows = DRIVER_REPORT_TARGET_DIMENSIONS.map((target) => {
    const config = getDriverDimensionConfigByTarget(target);
    const aliases = config?.aliases ?? [target];
    const sourceDimension = getDriverSourceDimension(sourceData, aliases);
    const reportRow = findMappedDashboardRow(report, aliases);
    const analysisItem = findMappedAnalysisItem(report, aliases);
    const sourceIndicators = [
      ...getStringArray(sourceDimension?.core_risk_indicators),
      simplifyIndicatorLabel(sourceDimension?.top_indicator),
    ].filter((item) => item.length > 0);
    const reportIndicators = Array.isArray(reportRow?.core_risk_indicators)
      ? reportRow.core_risk_indicators
          .map((item) => (typeof item === 'string' ? item.trim() : ''))
          .filter((item) => item.length > 0)
      : [];
    const candidateIndicators = collectDriverIndicatorCandidates(sourceData)
      .filter((item) => item.dimension === target)
      .map((item) => item.indicator);
    const indicatorPool = [
      ...reportIndicators,
      ...sourceIndicators,
      simplifyIndicatorLabel(analysisItem?.top_indicator),
      ...candidateIndicators,
    ].filter((item) => item.length > 0);
    const normalizedIndicators = indicatorPool
      .map((item) => normalizeDriverAnalysisIndicatorText(item, target, sourceData, report))
      .filter((item) => item.length > 0 && !looksLikeLegacyDriverDimensionText(item));
    const indicators = dedupeDriverIndicatorTexts(normalizedIndicators).slice(0, 2);
    const score =
      (reportRow ? parseAlertCount(reportRow.score) : null) ??
      (sourceDimension ? readNumberAtPath({ root: sourceDimension }, 'root.score') : null);
    return {
      dimension: target,
      score,
      trend_text: buildNormalizedTrendText(reportRow, sourceDimension, sourceData, aliases),
      core_risk_indicators: indicators.length ? indicators : [],
    };
  });

  return orderDashboardRowsByOverallThenScore([overallRow, ...detailRows], '综合风险');
}

function findDriverIndicatorCandidate(
  sourceData: Record<string, unknown> | null,
  indicator: unknown,
  targetDimension?: DriverReportTargetDimension
): DriverIndicatorCandidate | null {
  const normalized = simplifyIndicatorLabel(indicator);
  if (!normalized) return null;
  const matches = collectDriverIndicatorCandidates(sourceData).filter((item) => {
    const candidate = simplifyIndicatorLabel(item.indicator);
    return (
      candidate === normalized || candidate.includes(normalized) || normalized.includes(candidate)
    );
  });
  if (targetDimension) {
    return matches.find((item) => item.dimension === targetDimension) ?? null;
  }
  return matches[0] ?? null;
}

function resolveDriverIndicatorRiskScore(
  indicator: string,
  score: number | null,
  sourceData: Record<string, unknown> | null,
  targetDimension?: DriverReportTargetDimension
): number | null {
  const matchedCandidate = findDriverIndicatorCandidate(sourceData, indicator, targetDimension);
  if (matchedCandidate?.riskScore != null && matchedCandidate.riskScore > 0) {
    return matchedCandidate.riskScore;
  }
  if (matchedCandidate?.score != null && matchedCandidate.score > 0) {
    return matchedCandidate.score;
  }
  return score;
}

function buildDriverAnalysisInsight(
  prefix: string,
  dimension: string,
  indicator: string,
  indicatorScore: number | null,
  sourceData: Record<string, unknown> | null
): string {
  const scoreText = indicatorScore != null ? trimNumberString(indicatorScore) : '—';
  const focusIndicators = buildDriverMajorRiskFactors(sourceData, {})
    .slice(0, 2)
    .map((item) => `{${item}}`)
    .join('、');
  return `${prefix}{${dimension}}（一级指标），其中风险值最高的基础指标是{${indicator}}{${scoreText}}分，【说明该维度风险贡献较为集中${focusIndicators ? `，建议同步关注${focusIndicators}的联动变化` : ''}。】`;
}

function buildDriverAnalysisItemsV2(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const rankedRows = rows
    .filter(
      (row): row is Record<string, unknown> & { dimension: DriverReportTargetDimension } =>
        typeof row.dimension === 'string' && row.dimension !== '综合风险'
    )
    .sort((left, right) => getDriverDimensionSortScore(right) - getDriverDimensionSortScore(left));

  return rankedRows.map((row, index) => {
    const dimension = row.dimension as DriverReportTargetDimension;
    const config = getDriverDimensionConfigByTarget(dimension);
    const aliases = config?.aliases ?? [dimension];
    const analysisItem = findMappedAnalysisItem(report, aliases);
    const sourceDimension = getDriverSourceDimension(sourceData, aliases);
    const rawIndicatorCandidate =
      analysisItem?.top_indicator ??
      sourceDimension?.top_indicator ??
      (Array.isArray(row.core_risk_indicators) ? row.core_risk_indicators[0] : null);
    const topIndicator = normalizeDriverAnalysisIndicatorText(
      rawIndicatorCandidate,
      dimension,
      sourceData,
      report
    );
    const alertCount = resolveIndicatorAlertCount(
      topIndicator,
      analysisItem,
      sourceData,
      sourceDimension
    );
    const indicatorScore = resolveDriverIndicatorRiskScore(
      topIndicator,
      typeof row.score === 'number' ? row.score : null,
      sourceData,
      dimension
    );
    return {
      rank_label: DRIVER_REPORT_ANALYSIS_PREFIXES[index] ?? `第${index + 1}`,
      dimension,
      top_indicator: topIndicator,
      alert_count: alertCount ?? '—',
      insight: buildDriverAnalysisInsight(
        DRIVER_REPORT_ANALYSIS_PREFIXES[index] ?? `第${index + 1}`,
        dimension,
        topIndicator,
        indicatorScore,
        sourceData
      ),
    };
  });
}

function listDriverRecommendationIndicators(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<{ indicator: string; dimension: DriverReportTargetDimension }> {
  const ranked = collectDriverIndicatorCandidates(sourceData).map((item) => ({
    indicator: item.indicator,
    dimension: item.dimension,
    score: item.score ?? Number.NEGATIVE_INFINITY,
    count: item.count ?? Number.NEGATIVE_INFINITY,
  }));

  const fallback = rows
    .filter(
      (row): row is Record<string, unknown> & { dimension: DriverReportTargetDimension } =>
        typeof row.dimension === 'string' && row.dimension !== '综合风险'
    )
    .flatMap((row) => {
      const dimension = row.dimension as DriverReportTargetDimension;
      const indicators = Array.isArray(row.core_risk_indicators)
        ? row.core_risk_indicators
            .map((item) => (typeof item === 'string' ? item.trim() : ''))
            .filter((item) => item.length > 0 && item !== '—')
        : [];
      return indicators.map((indicator) => ({
        indicator: normalizeDriverAnalysisIndicatorText(indicator, dimension, sourceData, report),
        dimension,
        score: typeof row.score === 'number' ? row.score : Number.NEGATIVE_INFINITY,
        count: Number.NEGATIVE_INFINITY,
      }));
    });

  const deduped = new Map<string, { indicator: string; dimension: DriverReportTargetDimension }>();
  for (const item of [...ranked, ...fallback]) {
    const key = `${item.dimension}:${simplifyIndicatorLabel(item.indicator)}`;
    if (!item.indicator || deduped.has(key)) continue;
    deduped.set(key, { indicator: item.indicator, dimension: item.dimension });
    if (deduped.size >= 4) break;
  }
  return Array.from(deduped.values());
}

function buildDriverRecommendationsV2(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const sourceRecommendations = listSourceRecommendations(sourceData);
  if (sourceRecommendations.length > 0) {
    return sourceRecommendations.map((candidate, index) => {
      const indicator =
        (typeof candidate.indicator === 'string' && candidate.indicator.trim()) ||
        (typeof candidate.title === 'string' && candidate.title.trim()) ||
        '';
      const actionText = replaceLegacyDriverDimensionMentions(
        (typeof candidate.action === 'string' && candidate.action.trim()) ||
          (typeof candidate.title === 'string' && candidate.title.trim()) ||
          ''
      );
      const expectedText = replaceLegacyDriverDimensionMentions(
        (typeof candidate.expected_effect === 'string' && candidate.expected_effect.trim()) ||
          (typeof candidate.detail === 'string' && candidate.detail.trim()) ||
          (typeof candidate.rationale === 'string' && candidate.rationale.trim()) ||
          ''
      );
      const policyReference =
        (typeof candidate.policy_reference === 'string' && candidate.policy_reference.trim()) ||
        '-';
      return {
        priority: index + 1,
        indicator,
        policy_reference: policyReference,
        suggestion: buildDriverRecommendationText(
          DRIVER_REPORT_SUGGESTION_PREFIXES[index] ?? '建议重点关注',
          indicator,
          actionText,
          expectedText
        ),
      };
    });
  }

  const rankedIndicators = listDriverRecommendationIndicators(rows, report, sourceData);
  return rankedIndicators.map((item, index) => {
    const actionText = NO_MANAGEMENT_SUGGESTION_TEXT;
    const expectedText = '';
    return {
      priority: index + 1,
      indicator: item.indicator,
      policy_reference: '—',
      suggestion: buildDriverRecommendationText(
        DRIVER_REPORT_SUGGESTION_PREFIXES[index] ?? '建议重点关注',
        item.indicator,
        actionText,
        expectedText
      ),
    };
  });
}

function buildDriverCoreRiskAssessmentV2(
  rows: Array<Record<string, unknown>>,
  analysisItems: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const overallScore =
    readFirstNumberAtPaths(report, ['core_risk_assessment.overall_score']) ??
    readFirstNumberAtPaths(sourceData ?? {}, [
      'performance_dashboard.summary.overall_score',
      'performance_dashboard.dimensions.综合风险.score',
    ]);
  const riskLevel = deriveRiskLevelLabel(
    readFirstStringAtPaths(report, [
      'core_risk_assessment.risk_level',
      'management_summary.risk_level',
    ]) ?? readFirstStringAtPaths(sourceData ?? {}, ['performance_dashboard.summary.overall_level']),
    overallScore
  );
  const rankInfo = buildManagementRankInfo(report, sourceData);
  const comparison = buildManagementComparisonText(
    rankInfo.position,
    rankInfo.total,
    rankInfo.percentile,
    '驾驶员'
  );
  const rankSentence =
    rankInfo.position != null && rankInfo.total != null && comparison.verb
      ? `综合表现位于所属单位第{${rankInfo.position}}名{(${rankInfo.position}/${rankInfo.total})}，显示其{${comparison.verb}}多数驾驶员`
      : rankInfo.position != null
        ? `综合排名为第{${rankInfo.position}}名`
        : '当前缺少完整排名快照';
  const focusIndicators = analysisItems
    .slice(0, 2)
    .map((item) => (typeof item.top_indicator === 'string' ? `{${item.top_indicator}}` : ''))
    .filter((item) => item.length > 0)
    .join('、');

  return {
    summary: `综合近期运行数据判断，该驾驶员综合风险值为{${
      overallScore != null ? trimNumberString(overallScore) : '—'
    }}分，当前处于 {${riskLevel}}状态，${rankSentence}，【${
      focusIndicators
        ? `需重点关注${focusIndicators}等基础指标的持续波动，若不及时干预，风险仍可能继续累积。`
        : '需持续跟踪重点行为风险与服务安全表现的联动变化。'
    }】`,
    overall_score: overallScore,
    risk_level: riskLevel,
    rank: {
      position: rankInfo.position,
      total: rankInfo.total,
      display: rankInfo.display,
    },
    comparison: comparison.label,
    attention_note: focusIndicators
      ? `【建议围绕${focusIndicators}持续跟踪整改闭环，并同步观察综合风险分是否回落。】`
      : '【建议持续跟踪驾驶行为、服务表现与安全操作的综合变化。】',
    detail_lines: [],
  };
}

function buildDriverManagementSummaryV2(
  report: Record<string, unknown>,
  coreRiskAssessment: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const driverName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.driver_name', 'name']) ??
    readFirstStringAtPaths(report, ['management_summary.driver_name']) ??
    '—';
  const driverId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.driver_id', 'identifier', 'id']) ??
    readFirstStringAtPaths(report, ['management_summary.driver_id']) ??
    '—';
  const fleetName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.fleet_name']) ??
    readFirstStringAtPaths(report, ['management_summary.fleet_name']) ??
    '—';
  const reportDate = buildManagementReportDate(report, sourceData);
  const overallScore = readFirstNumberAtPaths(coreRiskAssessment, ['overall_score']);
  const riskLevel =
    readFirstStringAtPaths(coreRiskAssessment, ['risk_level']) ||
    deriveRiskLevelLabel(
      readFirstStringAtPaths(sourceData ?? {}, ['performance_dashboard.summary.overall_level']),
      overallScore
    );
  const majorRiskFactors = buildDriverMajorRiskFactors(sourceData, report);
  const factorText = majorRiskFactors.length
    ? majorRiskFactors.map((item) => `{${item}}`).join('、')
    : '当前缺少完整的高风险因子明细';
  const driverIdText = driverId && driverId !== '—' ? `{（${driverId}）}` : '';

  return {
    report_date: reportDate,
    driver_name: driverName,
    driver_id: driverId,
    fleet_name: fleetName,
    risk_level: riskLevel,
    major_risk_factors: majorRiskFactors,
    summary_text: `${reportDate !== '—' ? `{${reportDate}}` : ''}驾驶员{${driverName}}${driverIdText}被系统预判为 {${riskLevel}} ，主要风险因素为${factorText}，需引起重视。`,
  };
}

function buildDriverLayout(summaryText: string): Record<string, unknown> {
  return {
    title: '驾驶员安全风险分析总结报告',
    summary: summaryText,
    header: {
      items: [
        { label: '驾驶员', value_path: 'management_summary.driver_name' },
        { label: '工号', value_path: 'management_summary.driver_id' },
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
        blocks: [
          { type: 'text', text_path: 'core_risk_assessment.summary' },
          { type: 'list', items_path: 'core_risk_assessment.detail_lines', ordered: true },
        ],
      },
      {
        title: '三、行为与数据关联分析',
        blocks: [
          { type: 'list', items_path: 'behavior_data_analysis.analysis_items', ordered: true },
        ],
      },
      {
        title: '四、针对性干预建议',
        blocks: [{ type: 'list', items_path: 'interventions.recommendations', ordered: true }],
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

function normalizeDriverManagementReport(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  if (readStringAtPath(report, 'error')) {
    return report;
  }

  const rows = buildDriverDashboardRowsV2(report, sourceData);
  const analysisItems = buildDriverAnalysisItemsV2(rows, report, sourceData);
  const recommendations = buildDriverRecommendationsV2(rows, report, sourceData);
  const coreRiskAssessment = buildDriverCoreRiskAssessmentV2(
    rows,
    analysisItems,
    report,
    sourceData
  );
  const managementSummary = buildDriverManagementSummaryV2(report, coreRiskAssessment, sourceData);

  return {
    report_type: 'driver_safety_summary_management',
    template_version: '20260305',
    report_role: 'management',
    layout: buildDriverLayout(
      typeof managementSummary.summary_text === 'string' ? managementSummary.summary_text : ''
    ),
    management_summary: managementSummary,
    dashboard_rows: rows,
    core_risk_assessment: coreRiskAssessment,
    behavior_data_analysis: { analysis_items: analysisItems },
    interventions: { recommendations },
    appendix: buildManagementReportAppendix(report, sourceData),
  };
}

function hasCompleteStructuredManagementReport(
  report: Record<string, unknown>,
  options: {
    reportType: string;
    targetDimensions: readonly string[];
    detailPrefixes: readonly string[];
  }
): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  if (readStringAtPath(report, 'report_type') !== options.reportType) {
    return false;
  }
  if (readStringAtPath(report, 'template_version') !== '20260305') {
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
  if (!Array.isArray(rows) || rows.length !== options.targetDimensions.length) {
    return false;
  }
  const dimensions = rows
    .map((row) => (isRecord(row) && typeof row.dimension === 'string' ? row.dimension.trim() : ''))
    .filter((item) => item.length > 0);
  if (dimensions.length !== options.targetDimensions.length) {
    return false;
  }
  if (!options.targetDimensions.every((dimension) => dimensions.includes(dimension))) {
    return false;
  }

  const analysisItems = getNestedValue(report, 'behavior_data_analysis.analysis_items');
  if (!Array.isArray(analysisItems) || analysisItems.length !== options.targetDimensions.length) {
    return false;
  }
  const recommendations = getNestedValue(report, 'interventions.recommendations');
  if (
    !Array.isArray(recommendations) ||
    recommendations.length !== options.targetDimensions.length
  ) {
    return false;
  }

  const coreSummary = readStringAtPath(report, 'core_risk_assessment.summary') ?? '';
  const detailLines = getNestedValue(report, 'core_risk_assessment.detail_lines');
  if (!Array.isArray(detailLines) || detailLines.length !== options.targetDimensions.length) {
    return false;
  }
  const detailText = detailLines.map((item) => String(item)).join('\n');
  if (
    !options.targetDimensions.every(
      (dimension) => coreSummary.includes(dimension) || detailText.includes(dimension)
    )
  ) {
    return false;
  }
  const requiredPhrase = '其中风险值最高的基础指标是';
  if (
    !detailLines.every(
      (item, index) =>
        typeof item === 'string' &&
        item.includes(options.detailPrefixes[index] ?? `第${index + 1}`) &&
        item.includes(requiredPhrase)
    )
  ) {
    return false;
  }

  return true;
}

function hasCompleteDriverManagementReport(report: Record<string, unknown>): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  if (readStringAtPath(report, 'report_type') !== 'driver_safety_summary_management') {
    return false;
  }
  if (readStringAtPath(report, 'template_version') !== '20260305') {
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
  if (!Array.isArray(rows) || rows.length !== DRIVER_REPORT_DASHBOARD_DIMENSIONS.length) {
    return false;
  }
  const dimensions = rows.map((row) =>
    isRecord(row) && typeof row.dimension === 'string' ? row.dimension.trim() : ''
  );
  if (
    dimensions[0] !== '综合风险' ||
    !DRIVER_REPORT_DASHBOARD_DIMENSIONS.every((dimension) => dimensions.includes(dimension))
  ) {
    return false;
  }

  const summaryText = readStringAtPath(report, 'management_summary.summary_text') ?? '';
  const coreSummary = readStringAtPath(report, 'core_risk_assessment.summary') ?? '';
  if (!summaryText || !coreSummary) {
    return false;
  }

  const detailLines = getNestedValue(report, 'core_risk_assessment.detail_lines');
  if (!Array.isArray(detailLines)) {
    return false;
  }

  const analysisItems = getNestedValue(report, 'behavior_data_analysis.analysis_items');
  if (
    !Array.isArray(analysisItems) ||
    analysisItems.length === 0 ||
    analysisItems.length > DRIVER_REPORT_TARGET_DIMENSIONS.length
  ) {
    return false;
  }
  const analysisDimensions = analysisItems.map((item) =>
    isRecord(item) && typeof item.dimension === 'string' ? item.dimension.trim() : ''
  );
  if (
    analysisDimensions.some(
      (dimension) =>
        !DRIVER_REPORT_TARGET_DIMENSIONS.includes(dimension as DriverReportTargetDimension)
    ) ||
    new Set(analysisDimensions).size !== analysisDimensions.length
  ) {
    return false;
  }

  const recommendations = getNestedValue(report, 'interventions.recommendations');
  if (
    !Array.isArray(recommendations) ||
    recommendations.length === 0 ||
    recommendations.length > 4
  ) {
    return false;
  }

  return true;
}

const VEHICLE_REPORT_TARGET_DIMENSIONS = ['综合风险', '故障风险', '能耗风险'] as const;

type VehicleReportTargetDimension = (typeof VEHICLE_REPORT_TARGET_DIMENSIONS)[number];

interface VehicleIndicatorCandidate {
  indicator: string;
  dimension: VehicleReportTargetDimension;
  score: number | null;
  riskScore: number | null;
  count: number | null;
  level: string | null;
}

const VEHICLE_REPORT_DIMENSION_CONFIGS: Array<{
  target: VehicleReportTargetDimension;
  aliases: string[];
  sourceDimensionPaths: string[];
  sourceScorePaths: string[];
  sourceTrendTextPaths: string[];
  sourceTrendDeltaPaths: string[];
}> = [
  {
    target: '综合风险',
    aliases: ['综合风险', '综合安全', '整体风险'],
    sourceDimensionPaths: [
      'performance_dashboard.dimensions.综合风险',
      'performance_dashboard.summary',
      'risk_profile',
    ],
    sourceScorePaths: [
      'performance_dashboard.dimensions.综合风险.score',
      'performance_dashboard.summary.overall_score',
      'risk_profile.overall',
    ],
    sourceTrendTextPaths: [
      'performance_dashboard.dimensions.综合风险.trend_text',
      'performance_dashboard.summary.trend_text',
      'risk_profile.trend_text',
    ],
    sourceTrendDeltaPaths: [
      'performance_dashboard.dimensions.综合风险.trend_delta',
      'performance_dashboard.summary.overall_trend_delta',
      'risk_profile.trend_delta',
    ],
  },
  {
    target: '故障风险',
    aliases: ['故障风险', '机械风险', '车辆健康', '车况风险'],
    sourceDimensionPaths: [
      'performance_dashboard.dimensions.故障风险',
      'health_status',
      'risk_profile',
    ],
    sourceScorePaths: [
      'performance_dashboard.dimensions.故障风险.score',
      'risk_profile.mechanical',
      'health_status.overall_score',
    ],
    sourceTrendTextPaths: [
      'performance_dashboard.dimensions.故障风险.trend_text',
      'health_status.trend_text',
    ],
    sourceTrendDeltaPaths: [
      'performance_dashboard.dimensions.故障风险.trend_delta',
      'health_status.trend_delta',
    ],
  },
  {
    target: '能耗风险',
    aliases: ['能耗风险', '运营风险', '运行风险', '能耗表现'],
    sourceDimensionPaths: [
      'performance_dashboard.dimensions.能耗风险',
      'energy_profile',
      'operation_profile',
      'risk_profile',
    ],
    sourceScorePaths: [
      'performance_dashboard.dimensions.能耗风险.score',
      'risk_profile.operation',
      'energy_profile.overall',
      'operation_profile.overall',
    ],
    sourceTrendTextPaths: [
      'performance_dashboard.dimensions.能耗风险.trend_text',
      'energy_profile.trend_text',
      'operation_profile.trend_text',
    ],
    sourceTrendDeltaPaths: [
      'performance_dashboard.dimensions.能耗风险.trend_delta',
      'energy_profile.trend_delta',
      'operation_profile.trend_delta',
    ],
  },
];

const VEHICLE_REPORT_ANALYSIS_PREFIXES = ['风险最高的一级指标是', '其次是', '再次是'];
const VEHICLE_REPORT_SUGGESTION_PREFIXES = ['风险最高的基础指标是', '其次是', '再次是', '最后是'];

function readFirstNumberAtPaths(source: Record<string, unknown>, paths: string[]): number | null {
  for (const path of paths) {
    const value = readNumberAtPath(source, path);
    if (value != null) return value;
  }
  return null;
}

function readFirstStringAtPaths(source: Record<string, unknown>, paths: string[]): string | null {
  for (const path of paths) {
    const value = readStringAtPath(source, path);
    if (value) return value;
  }
  return null;
}

function readFirstRecordAtPaths(
  source: Record<string, unknown>,
  paths: string[]
): Record<string, unknown> | null {
  for (const path of paths) {
    const value = readRecordAtPath(source, path);
    if (value) return value;
  }
  return null;
}

function readFirstArrayAtPaths(source: Record<string, unknown>, paths: string[]): unknown[] | null {
  for (const path of paths) {
    const value = readArrayAtPath(source, path);
    if (value) return value;
  }
  return null;
}

function humanizeVehicleViolationKey(key: string): string {
  const normalized = key.trim().toLowerCase();
  const mapping: Record<string, string> = {
    speeding: '超速',
    lane_departure: '偏离车道',
    harsh_brake: '急刹车',
    harsh_braking: '急刹车',
    rapid_acceleration: '急加速',
    sudden_acceleration: '急加速',
    irregular_stop_entry: '不规范进站',
    neutral_coasting: '空挡滑行',
    idling: '怠速',
    soc_consumption: 'SOC消耗异常',
  };
  return mapping[normalized] || key.trim();
}

function getVehicleDimensionConfigByTarget(
  target: string
): (typeof VEHICLE_REPORT_DIMENSION_CONFIGS)[number] | null {
  return VEHICLE_REPORT_DIMENSION_CONFIGS.find((item) => item.target === target) ?? null;
}

function normalizeVehicleDimensionName(value: unknown): VehicleReportTargetDimension | null {
  if (typeof value !== 'string') return null;
  const simplified = simplifyIndicatorLabel(value);
  if (!simplified) return null;
  for (const config of VEHICLE_REPORT_DIMENSION_CONFIGS) {
    if (
      config.aliases.some((alias) => {
        const normalizedAlias = simplifyIndicatorLabel(alias);
        return simplified === normalizedAlias || simplified.includes(normalizedAlias);
      })
    ) {
      return config.target;
    }
  }
  return null;
}

function looksLikeVehicleDimensionText(value: string): boolean {
  return normalizeVehicleDimensionName(value) != null;
}

function inferVehicleDimensionFromIndicator(indicator: string): VehicleReportTargetDimension {
  if (
    /(故障|报警|告警|电池|制动|刹车|发动机|电机|轮胎|胎压|温度|压力|振动|ABS|DCDC|绝缘|保养|维修|维保|工单|冷却|润滑|动力系统)/i.test(
      indicator
    )
  ) {
    return '故障风险';
  }
  if (
    /(能耗|超速|急加速|急刹车|油耗|电耗|SOC|空挡|滑行|进站|平顺|运行|速度|里程|充电|温差|黑点)/i.test(
      indicator
    )
  ) {
    return '能耗风险';
  }
  return '综合风险';
}

function buildVehicleSourceDimension(
  target: VehicleReportTargetDimension,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> | null {
  if (!sourceData) return null;
  const config = getVehicleDimensionConfigByTarget(target);
  if (!config) return null;
  const sourceDimension = readFirstRecordAtPaths(sourceData, config.sourceDimensionPaths);
  const score = readFirstNumberAtPaths(sourceData, config.sourceScorePaths);
  const trendText =
    (sourceDimension
      ? readFirstStringAtPaths({ root: sourceDimension }, ['root.trend_text'])
      : null) ||
    readFirstStringAtPaths(sourceData, config.sourceTrendTextPaths) ||
    '';
  const trendDelta =
    (sourceDimension
      ? readFirstNumberAtPaths({ root: sourceDimension }, ['root.trend_delta'])
      : null) || readFirstNumberAtPaths(sourceData, config.sourceTrendDeltaPaths);
  const topIndicator =
    (sourceDimension
      ? readFirstStringAtPaths({ root: sourceDimension }, ['root.top_indicator'])
      : null) || '';
  const alertCount =
    (sourceDimension
      ? readFirstNumberAtPaths({ root: sourceDimension }, ['root.alert_count'])
      : null) ?? null;
  const coreRiskIndicators = sourceDimension
    ? getStringArray(getNestedValue(sourceDimension, 'core_risk_indicators'))
    : [];

  if (
    !sourceDimension &&
    score == null &&
    !trendText &&
    trendDelta == null &&
    !topIndicator &&
    !coreRiskIndicators.length &&
    alertCount == null
  ) {
    return null;
  }

  return {
    score,
    trend_text: trendText,
    trend_delta: trendDelta,
    top_indicator: topIndicator,
    alert_count: alertCount,
    core_risk_indicators: coreRiskIndicators,
  };
}

function collectVehicleIndicatorCandidates(
  sourceData: Record<string, unknown> | null
): VehicleIndicatorCandidate[] {
  if (!sourceData) return [];
  const candidates: VehicleIndicatorCandidate[] = [];

  const pushCandidate = (
    rawIndicator: unknown,
    partial: Partial<VehicleIndicatorCandidate> = {}
  ) => {
    const indicator = simplifyIndicatorLabel(rawIndicator);
    if (!indicator || looksLikeVehicleDimensionText(indicator)) return;
    candidates.push({
      indicator,
      dimension: partial.dimension ?? inferVehicleDimensionFromIndicator(indicator),
      score: partial.score ?? null,
      riskScore: partial.riskScore ?? partial.score ?? null,
      count: partial.count ?? null,
      level: partial.level ?? null,
    });
  };

  const quotaItems = readArrayAtPath(sourceData, 'appendix.raw_data.quota_items') ?? [];
  for (const item of quotaItems) {
    if (!isRecord(item)) continue;
    pushCandidate(item.quota_name ?? item.name ?? item.indicator, {
      dimension:
        normalizeVehicleDimensionName(item.dimension) ??
        inferVehicleDimensionFromIndicator(
          simplifyIndicatorLabel(item.quota_name ?? item.name ?? item.indicator)
        ),
      score: parseAlertCount(item.score),
      riskScore: parseAlertCount(item.final_risk_score ?? item.risk_score ?? item.original_value),
      count: parseAlertCount(item.count ?? item.alert_count),
      level: typeof item.quota_level === 'string' ? item.quota_level.trim() : null,
    });
  }

  const highRiskIndicators = getNestedValue(sourceData, 'high_risk_indicators.indicators');
  if (Array.isArray(highRiskIndicators)) {
    for (const item of highRiskIndicators) {
      if (isRecord(item)) {
        pushCandidate(item.indicator ?? item.name ?? item.title ?? item.type, {
          dimension:
            normalizeVehicleDimensionName(item.dimension) ??
            inferVehicleDimensionFromIndicator(
              simplifyIndicatorLabel(item.indicator ?? item.name ?? item.title ?? item.type)
            ),
          score: parseAlertCount(item.score),
          riskScore: parseAlertCount(
            item.final_risk_score ?? item.risk_score ?? item.original_value
          ),
          count: parseAlertCount(item.alert_count ?? item.count ?? item.occurrences),
          level: typeof item.level === 'string' ? item.level.trim() : null,
        });
      } else {
        pushCandidate(item, {
          count: parseAlertCount(item),
        });
      }
    }
  }

  const systemTags = readArrayAtPath(sourceData, 'performance_dashboard.system_risk.tags') ?? [];
  for (const tag of systemTags) {
    pushCandidate(tag, {
      count: parseAlertCount(tag),
    });
  }

  const dashboardDimensions = readRecordAtPath(sourceData, 'performance_dashboard.dimensions');
  if (dashboardDimensions) {
    for (const [dimKey, dimValue] of Object.entries(dashboardDimensions)) {
      if (!isRecord(dimValue)) continue;
      const dimension = normalizeVehicleDimensionName(dimKey);
      const dimScore = typeof dimValue.score === 'number' ? dimValue.score : null;
      const dimRanking = typeof dimValue.rank_position === 'number' ? dimValue.rank_position : null;
      const coreRiskIndicators = Array.isArray(dimValue.core_risk_indicators)
        ? dimValue.core_risk_indicators.filter(
            (item): item is string => typeof item === 'string' && item.trim().length > 0
          )
        : [];
      for (const indicator of coreRiskIndicators) {
        pushCandidate(indicator, {
          dimension: dimension ?? inferVehicleDimensionFromIndicator(indicator),
          score: dimScore,
        });
      }
      if (typeof dimValue.top_indicator === 'string' && dimValue.top_indicator.trim()) {
        pushCandidate(dimValue.top_indicator, {
          dimension: dimension ?? inferVehicleDimensionFromIndicator(dimValue.top_indicator),
          score: dimScore,
        });
      }
    }
  }

  const quotaSummary = readArrayAtPath(sourceData, 'appendix.raw_data.quota_summary') ?? [];
  for (const summaryItem of quotaSummary) {
    if (!isRecord(summaryItem)) continue;
    const dimension = normalizeVehicleDimensionName(summaryItem.dimension);
    const dimScore = typeof summaryItem.score === 'number' ? summaryItem.score : null;
    const indicators = Array.isArray(summaryItem.indicators)
      ? summaryItem.indicators.filter((item): item is Record<string, unknown> => isRecord(item))
      : [];
    for (const ind of indicators) {
      const indicatorName =
        typeof ind.name === 'string'
          ? ind.name
          : typeof ind.quotaName === 'string'
            ? ind.quotaName
            : '';
      if (indicatorName) {
        pushCandidate(indicatorName, {
          dimension: dimension ?? inferVehicleDimensionFromIndicator(indicatorName),
          score: typeof ind.score === 'number' ? ind.score : dimScore,
          riskScore: parseAlertCount(
            ind.final_risk_score ?? ind.risk_score ?? ind.original_value ?? ind.score
          ),
        });
      }
    }
  }

  const alerts = readArrayAtPath(sourceData, 'alerts') ?? [];
  for (const item of alerts) {
    if (!isRecord(item)) continue;
    pushCandidate(item.type ?? item.indicator ?? item.title, {
      dimension: '故障风险',
      score: parseAlertCount(item.score),
      count: parseAlertCount(item.alert_count ?? item.count),
      level: typeof item.severity === 'string' ? item.severity.trim() : null,
    });
  }

  const openItems = readFirstArrayAtPaths(sourceData, ['maintenance.open_items']) ?? [];
  for (const item of openItems) {
    pushCandidate(item, { dimension: '故障风险' });
  }

  const violations = readRecordAtPath(sourceData, 'violations');
  if (violations) {
    for (const [key, value] of Object.entries(violations)) {
      const count = parseAlertCount(value);
      if (count == null || count <= 0) continue;
      const indicator = humanizeVehicleViolationKey(key);
      pushCandidate(indicator, {
        dimension: inferVehicleDimensionFromIndicator(indicator),
        count,
      });
    }
  }

  const alertCounts =
    readRecordAtPath(sourceData, 'appendix.raw_data.alerts_counts') ??
    readRecordAtPath(sourceData, 'alerts_counts');
  if (alertCounts) {
    for (const [key, value] of Object.entries(alertCounts)) {
      pushCandidate(key, {
        count: parseAlertCount(value),
      });
    }
  }

  const deduped = new Map<string, VehicleIndicatorCandidate>();
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
    const leftScore = left.score ?? Number.NEGATIVE_INFINITY;
    const rightScore = right.score ?? Number.NEGATIVE_INFINITY;
    if (rightScore !== leftScore) return rightScore - leftScore;
    const leftCount = left.count ?? Number.NEGATIVE_INFINITY;
    const rightCount = right.count ?? Number.NEGATIVE_INFINITY;
    return rightCount - leftCount;
  });
}

function dedupeVehicleIndicatorTexts(values: string[]): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    const normalized = simplifyIndicatorLabel(trimmed);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    next.push(trimmed);
  }
  return next;
}

function findVehicleIndicatorCandidate(
  sourceData: Record<string, unknown> | null,
  indicator: unknown,
  targetDimension?: VehicleReportTargetDimension
): VehicleIndicatorCandidate | null {
  const normalized = simplifyIndicatorLabel(indicator);
  if (!normalized) return null;
  const matches = collectVehicleIndicatorCandidates(sourceData).filter((item) => {
    const candidate = simplifyIndicatorLabel(item.indicator);
    return (
      candidate === normalized || candidate.includes(normalized) || normalized.includes(candidate)
    );
  });
  if (targetDimension) {
    return matches.find((item) => item.dimension === targetDimension) ?? null;
  }
  return matches[0] ?? null;
}

function resolveVehicleIndicatorDimension(
  indicator: unknown,
  sourceData: Record<string, unknown> | null,
  targetDimension?: VehicleReportTargetDimension
): VehicleReportTargetDimension | null {
  const normalized = simplifyIndicatorLabel(indicator);
  if (!normalized || looksLikeVehicleDimensionText(normalized)) return null;
  return (
    findVehicleIndicatorCandidate(sourceData, normalized, targetDimension)?.dimension ??
    inferVehicleDimensionFromIndicator(normalized)
  );
}

function buildVehicleMajorRiskFactors(
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string[] {
  const reportFactors = getStringArray(
    getNestedValue(report, 'management_summary.major_risk_factors')
  );
  const sourceFactors = collectVehicleIndicatorCandidates(sourceData)
    .map((item) => item.indicator)
    .filter((item) => item.length > 0);
  return dedupeVehicleIndicatorTexts([...sourceFactors, ...reportFactors]).slice(0, 4);
}

function getVehicleIndicatorFallback(
  target: VehicleReportTargetDimension,
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string {
  const majorRiskFactors = buildVehicleMajorRiskFactors(sourceData, report);
  if (target === '综合风险' && majorRiskFactors.length > 0) {
    return majorRiskFactors[0];
  }
  const dimensionCandidate = collectVehicleIndicatorCandidates(sourceData).find(
    (item) => item.dimension === target
  );
  if (dimensionCandidate?.indicator) {
    return dimensionCandidate.indicator;
  }
  return '';
}

function normalizeVehicleIndicatorText(
  rawIndicator: unknown,
  target: VehicleReportTargetDimension,
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string {
  const simplified = simplifyIndicatorLabel(rawIndicator);
  if (simplified && !looksLikeVehicleDimensionText(simplified)) {
    const matchedCandidate = findVehicleIndicatorCandidate(
      sourceData,
      simplified,
      target === '综合风险' ? undefined : target
    );
    if (matchedCandidate) {
      if (target === '综合风险' || matchedCandidate.dimension === target) {
        return matchedCandidate.indicator;
      }
      return getVehicleIndicatorFallback(target, sourceData, report);
    }
    const inferredDimension = inferVehicleDimensionFromIndicator(simplified);
    if (target === '综合风险' || inferredDimension === target) {
      return simplified;
    }
  }
  return getVehicleIndicatorFallback(target, sourceData, report);
}

function collectVehicleIndicatorsForTarget(
  target: VehicleReportTargetDimension,
  reportRow: Record<string, unknown> | null,
  sourceDimension: Record<string, unknown> | null,
  analysisItem: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string[] {
  const sourceCandidates = collectVehicleIndicatorCandidates(sourceData)
    .filter((item) => target === '综合风险' || item.dimension === target)
    .map((item) => item.indicator);
  const rawIndicators = [
    ...getStringArray(reportRow?.core_risk_indicators),
    ...getStringArray(sourceDimension?.core_risk_indicators),
    simplifyIndicatorLabel(sourceDimension?.top_indicator),
    simplifyIndicatorLabel(analysisItem?.top_indicator),
    ...sourceCandidates,
  ];
  const normalized = rawIndicators
    .map((item) => normalizeVehicleIndicatorText(item, target, sourceData, report))
    .filter((item): item is string => {
      if (!item || item === '—' || looksLikeVehicleDimensionText(item)) return false;
      return (
        target === '综合风险' || resolveVehicleIndicatorDimension(item, sourceData, target) === target
      );
    });
  const deduped = dedupeVehicleIndicatorTexts(normalized);
  const fallback = getVehicleIndicatorFallback(target, sourceData, report);
  return deduped.length ? deduped : fallback ? [fallback] : [];
}

function resolveVehicleIndicatorAlertCount(
  indicator: string,
  analysisItem: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null,
  sourceDimension: Record<string, unknown> | null,
  targetDimension?: VehicleReportTargetDimension
): number | null {
  const matchedCandidate = findVehicleIndicatorCandidate(sourceData, indicator, targetDimension);
  if (matchedCandidate?.count != null && matchedCandidate.count > 0) {
    return matchedCandidate.count;
  }
  const dimensionCount = parseAlertCount(sourceDimension?.alert_count);
  const sourceTopIndicator = simplifyIndicatorLabel(sourceDimension?.top_indicator);
  if (
    dimensionCount != null &&
    dimensionCount > 0 &&
    (!sourceTopIndicator || sourceTopIndicator === simplifyIndicatorLabel(indicator))
  ) {
    return dimensionCount;
  }
  if (matchedCandidate) {
    return null;
  }
  const direct = parseAlertCount(analysisItem?.alert_count);
  if (!sourceData && direct != null && direct > 0) return direct;
  return null;
}

function resolveVehicleDirectIndicatorCount(
  indicator: string,
  sourceData: Record<string, unknown> | null,
  targetDimension?: VehicleReportTargetDimension
): number | null {
  const matchedCandidate = findVehicleIndicatorCandidate(sourceData, indicator, targetDimension);
  if (matchedCandidate?.count != null && matchedCandidate.count > 0) {
    return matchedCandidate.count;
  }
  return null;
}

function resolveVehicleIndicatorRiskScore(
  indicator: string,
  sourceData: Record<string, unknown> | null,
  targetDimension?: VehicleReportTargetDimension
): number | null {
  const matchedCandidate = findVehicleIndicatorCandidate(sourceData, indicator, targetDimension);
  if (matchedCandidate?.riskScore != null && matchedCandidate.riskScore > 0) {
    return matchedCandidate.riskScore;
  }
  if (matchedCandidate?.score != null && matchedCandidate.score > 0) {
    return matchedCandidate.score;
  }
  return null;
}

function buildVehicleIndicatorEvidenceItems(
  indicators: string[],
  sourceData: Record<string, unknown> | null,
  targetDimension?: VehicleReportTargetDimension
): Array<{ indicator: string; risk_score: number | null }> {
  return dedupeVehicleIndicatorTexts(indicators).map((indicator) => ({
    indicator,
    risk_score: resolveVehicleIndicatorRiskScore(indicator, sourceData, targetDimension),
  }));
}

function getVehicleAnalysisRows(
  rows: Array<Record<string, unknown>>
): Array<Record<string, unknown>> {
  return rows
    .filter((row) => typeof row.dimension === 'string' && row.dimension !== '综合风险')
    .slice()
    .sort((left, right) => {
      const leftScore = typeof left.score === 'number' ? left.score : Number.NEGATIVE_INFINITY;
      const rightScore = typeof right.score === 'number' ? right.score : Number.NEGATIVE_INFINITY;
      return rightScore - leftScore;
    });
}

function buildVehicleAnalysisInsight(
  prefix: string,
  dimension: string,
  evidenceItems: Array<{ indicator: string; risk_score: number | null }>,
  score: number | null,
  index: number
): string {
  const indicatorEvidence = evidenceItems.length
    ? evidenceItems
        .map((item) =>
          item.risk_score != null
            ? `{${item.indicator}}{${trimNumberString(item.risk_score)}}分`
            : `{${item.indicator}}`
        )
        .join('、')
    : `{${dimension}}`;
  const scoreLabel = deriveRiskLevelLabel(null, score);
  const thresholdText = evidenceItems.some((item) => item.risk_score != null)
    ? `相关源数据为${indicatorEvidence}，风险贡献处于{${scoreLabel}}水平，`
    : `当前缺少基础指标风险分，但${indicatorEvidence}等基础指标需持续关注，`;
  const aiText =
    dimension === '故障风险'
      ? '【反映车辆设备状态与驾驶操作可能已形成双向影响，若持续存在将显著增加突发故障概率，是当前需要重点关注的风险来源。】'
      : '【表明驾驶节奏与车辆运行状态存在明显关联，长期将放大能耗波动并增加运营成本。】';
  if (index === 0) {
    return `${prefix}{${dimension}}（一级指标），${thresholdText}${aiText}`;
  }
  return `${prefix}{${dimension}}（一级指标），${thresholdText}${aiText}`;
}

function buildVehicleRecommendationText(
  prefix: string,
  indicator: string,
  actionText: string,
  expectedText: string
): string {
  const normalizedActionText = normalizeRecommendationActionText(actionText);
  const normalizedExpectedText = expectedText.trim();
  if (isNoManagementSuggestionText(normalizedActionText)) {
    return `${prefix}{${indicator}}，${NO_MANAGEMENT_SUGGESTION_TEXT}。`;
  }
  if (!normalizedExpectedText) {
    return `${prefix}{${indicator}}，建议开展${normalizedActionText}。`;
  }
  return `${prefix}{${indicator}}，建议开展${normalizedActionText}，${normalizedExpectedText}。`;
}
function buildVehicleDashboardRows(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const rows = VEHICLE_REPORT_DIMENSION_CONFIGS.map((config) => {
    const sourceDimension = buildVehicleSourceDimension(config.target, sourceData);
    const reportRow = findMappedDashboardRow(report, config.aliases);
    const analysisItem = findMappedAnalysisItem(report, config.aliases);
    const uniqueIndicators = collectVehicleIndicatorsForTarget(
      config.target,
      reportRow,
      sourceDimension,
      analysisItem,
      sourceData,
      report
    );
    const reportIndicatorCount = Array.isArray(reportRow?.core_risk_indicators)
      ? reportRow.core_risk_indicators.filter(
          (item) => typeof item === 'string' && item.trim().length > 0
        ).length
      : 0;
    const sourceIndicatorCount = Array.isArray(sourceDimension?.core_risk_indicators)
      ? sourceDimension.core_risk_indicators.filter(
          (item) => typeof item === 'string' && item.trim().length > 0
        ).length
      : 0;
    const inferredLimit = Math.max(
      reportIndicatorCount,
      sourceIndicatorCount,
      config.target === '综合风险' ? 4 : 3
    );
    const limit = Math.min(Math.max(inferredLimit, 1), 4);
    const score =
      (reportRow ? readFirstNumberAtPaths({ root: reportRow }, ['root.score']) : null) ??
      (sourceDimension ? readFirstNumberAtPaths({ root: sourceDimension }, ['root.score']) : null);

    return {
      dimension: config.target,
      score,
      trend_text: buildNormalizedTrendText(reportRow, sourceDimension, sourceData, config.aliases),
      core_risk_indicators: uniqueIndicators.length ? uniqueIndicators.slice(0, limit) : [],
    };
  });
  return orderDashboardRowsByOverallThenScore(rows, '综合风险');
}

function buildVehicleAnalysisItems(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  return getVehicleAnalysisRows(rows).map((row, index) => {
    const dimension = typeof row.dimension === 'string' ? row.dimension : '—';
    const config = getVehicleDimensionConfigByTarget(dimension);
    const analysisItem = config ? findMappedAnalysisItem(report, config.aliases) : null;
    const sourceDimension = config ? buildVehicleSourceDimension(config.target, sourceData) : null;
    const indicatorPool = [
      ...(Array.isArray(row.core_risk_indicators)
        ? row.core_risk_indicators.map((item) => (typeof item === 'string' ? item.trim() : ''))
        : []),
      simplifyIndicatorLabel(sourceDimension?.top_indicator),
      simplifyIndicatorLabel(analysisItem?.top_indicator),
    ].filter((item) => item.length > 0 && item !== '—');
    const normalizedIndicators = config
      ? indicatorPool
          .map((item) => normalizeVehicleIndicatorText(item, config.target, sourceData, report))
          .filter((item): item is string => item != null && item.length > 0 && item !== '—')
      : indicatorPool;
    const indicators = dedupeVehicleIndicatorTexts(normalizedIndicators);
    const fallbackIndicator = config
      ? getVehicleIndicatorFallback(config.target, sourceData, report)
      : null;
    const topIndicator = indicators[0] ?? fallbackIndicator ?? '';
    const evidenceItems = buildVehicleIndicatorEvidenceItems(
      indicators.length ? indicators : topIndicator ? [topIndicator] : [],
      sourceData,
      config?.target
    );
    const alertCount = resolveVehicleDirectIndicatorCount(topIndicator, sourceData, config?.target);
    const indicatorScore =
      evidenceItems[0]?.risk_score ??
      resolveVehicleIndicatorRiskScore(topIndicator, sourceData, config?.target);
    return {
      rank_label: VEHICLE_REPORT_ANALYSIS_PREFIXES[index] ?? `第${index + 1}`,
      dimension,
      top_indicator: topIndicator,
      alert_count: alertCount ?? '—',
      indicator_score: indicatorScore ?? '—',
      indicators: evidenceItems.map((item) => item.indicator),
      indicator_evidence: evidenceItems,
      has_missing_direct_count: evidenceItems.some((item) => item.risk_score == null),
      insight: buildVehicleAnalysisInsight(
        VEHICLE_REPORT_ANALYSIS_PREFIXES[index] ?? `第${index + 1}`,
        dimension,
        evidenceItems,
        typeof row.score === 'number' ? row.score : null,
        index
      ),
    };
  });
}

function listVehicleRecommendationIndicators(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<{ indicator: string; dimension: VehicleReportTargetDimension }> {
  const ranked = collectVehicleIndicatorCandidates(sourceData)
    .filter((item) => item.dimension !== '综合风险')
    .map((item) => ({
      indicator: item.indicator,
      dimension: item.dimension,
      score: item.score ?? Number.NEGATIVE_INFINITY,
      count: item.count ?? Number.NEGATIVE_INFINITY,
    }))
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      return right.count - left.count;
    });

  const fallback = getVehicleAnalysisRows(rows).flatMap((row) => {
    const dimension = normalizeVehicleDimensionName(row.dimension);
    if (!dimension || dimension === '综合风险') return [];
    const indicators = Array.isArray(row.core_risk_indicators)
      ? row.core_risk_indicators
          .map((item) => (typeof item === 'string' ? item.trim() : ''))
          .filter((item) => item.length > 0 && item !== '—')
      : [];
    return indicators.map((indicator) => ({
      indicator: normalizeVehicleIndicatorText(indicator, dimension, sourceData, report),
      dimension,
      score: typeof row.score === 'number' ? row.score : Number.NEGATIVE_INFINITY,
      count: Number.NEGATIVE_INFINITY,
    }));
  });

  const deduped = new Map<string, { indicator: string; dimension: VehicleReportTargetDimension }>();
  for (const item of [...ranked, ...fallback]) {
    const key = `${item.dimension}:${simplifyIndicatorLabel(item.indicator)}`;
    if (!item.indicator || deduped.has(key)) continue;
    deduped.set(key, { indicator: item.indicator, dimension: item.dimension });
    if (deduped.size >= 4) break;
  }
  return Array.from(deduped.values());
}

function buildVehicleRecommendations(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const sourceRecommendations = listSourceRecommendations(sourceData);
  if (sourceRecommendations.length > 0) {
    return sourceRecommendations.map((candidate, index) => {
      const indicator =
        (typeof candidate.indicator === 'string' && candidate.indicator.trim()) ||
        (typeof candidate.title === 'string' && candidate.title.trim()) ||
        '';
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
        '-';
      return {
        priority: index + 1,
        indicator,
        policy_reference: policyReference,
        suggestion: buildVehicleRecommendationText(
          VEHICLE_REPORT_SUGGESTION_PREFIXES[index] ?? '寤鸿閲嶇偣鍏虫敞',
          indicator,
          actionText,
          expectedText
        ),
      };
    });
  }

  const rankedIndicators = listVehicleRecommendationIndicators(rows, report, sourceData);
  return rankedIndicators.map((item, index) => {
    const indicator = item.indicator ?? '';
    const actionText = NO_MANAGEMENT_SUGGESTION_TEXT;
    const expectedText = '';
    return {
      priority: index + 1,
      indicator,
      policy_reference: '—',
      suggestion: buildVehicleRecommendationText(
        VEHICLE_REPORT_SUGGESTION_PREFIXES[index] ?? '建议重点关注',
        indicator,
        actionText,
        expectedText
      ),
    };
  });
}

function buildManagementRankInfo(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): { position: number | null; total: number | null; display: string; percentile: number | null } {
  const position =
    readFirstNumberAtPaths(report, ['core_risk_assessment.rank.position']) ??
    readFirstNumberAtPaths(sourceData ?? {}, [
      'appendix.raw_data.main.ranking',
      'appendix.raw_data.ranking_snapshot.rank_position',
      'performance_dashboard.dimensions.综合风险.rank_position',
    ]);
  const total =
    readFirstNumberAtPaths(report, ['core_risk_assessment.rank.total']) ??
    readFirstNumberAtPaths(sourceData ?? {}, [
      'appendix.raw_data.main.ranking_total',
      'appendix.raw_data.ranking_snapshot.rank_total',
      'performance_dashboard.dimensions.综合风险.rank_total',
    ]);
  const percentile = readFirstNumberAtPaths(sourceData ?? {}, [
    'appendix.raw_data.ranking_snapshot.percentile',
    'performance_dashboard.dimensions.综合风险.percentile',
  ]);
  const display =
    readFirstStringAtPaths(report, ['core_risk_assessment.rank.display']) ??
    readFirstStringAtPaths(sourceData ?? {}, [
      'appendix.raw_data.ranking_snapshot.display',
      'performance_dashboard.dimensions.综合风险.display',
    ]) ??
    (position != null && total != null
      ? `排名 ${position}/${total}`
      : position != null
        ? `当前排名第${position}`
        : '');
  return { position, total, display, percentile };
}
function buildManagementComparisonText(
  position: number | null,
  total: number | null,
  percentile: number | null,
  entityLabel = '车辆'
): { label: string; verb: string | null } {
  if (position == null || total == null || total <= 0) {
    return { label: '当前缺少完整排名快照', verb: null };
  }
  const betterThanMost = percentile != null ? percentile <= 50 : position <= Math.ceil(total / 2);
  return {
    label: betterThanMost ? `优于多数${entityLabel}` : `差于多数${entityLabel}`,
    verb: betterThanMost ? '优于' : '差于',
  };
}

function shiftIsoDate(value: string, offsetDays: number): string | null {
  const match = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const date = new Date(`${match[1]}-${match[2]}-${match[3]}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  date.setUTCDate(date.getUTCDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

function formatDateRangeCn(startValue: string | null, endValue: string | null): string | null {
  const startMatch = startValue?.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  const endMatch = endValue?.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!startMatch || !endMatch) return null;
  const startText = `${startMatch[1]}年${Number(startMatch[2])}月${Number(startMatch[3])}日`;
  const endText =
    startMatch[1] === endMatch[1]
      ? `${Number(endMatch[2])}月${Number(endMatch[3])}日`
      : `${endMatch[1]}年${Number(endMatch[2])}月${Number(endMatch[3])}日`;
  return `${startText}-${endText}`;
}

function buildManagementReportDate(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): string {
  void report;
  const start =
    readFirstStringAtPaths(sourceData ?? {}, [
      'appendix.raw_data.analysis_period.start',
      'appendix.raw_data.source_window.start',
    ]) ?? null;
  const end =
    readFirstStringAtPaths(sourceData ?? {}, [
      'appendix.raw_data.analysis_period.end',
      'appendix.raw_data.source_window.end',
    ]) ??
    readFirstStringAtPaths(sourceData ?? {}, ['appendix.raw_data.source_window.as_of']) ??
    null;
  const directRange = formatDateRangeCn(start, end);
  if (directRange) return directRange;
  const asOf = readFirstStringAtPaths(sourceData ?? {}, ['appendix.raw_data.source_window.as_of']);
  const windowDays = readFirstNumberAtPaths(sourceData ?? {}, [
    'appendix.raw_data.source_window.window_days',
  ]);
  if (asOf && windowDays != null && windowDays > 0) {
    const startDate = shiftIsoDate(asOf, 1 - windowDays);
    const range = formatDateRangeCn(startDate, asOf);
    if (range) return range;
  }
  return formatDateToCn(asOf) ?? '—';
}

function buildVehicleAttentionNote(analysisItems: Array<Record<string, unknown>>): string {
  const missingIndicatorScore = analysisItems.some((item) => {
    if (item.has_missing_direct_count === true) {
      return true;
    }
    const score = item.indicator_score;
    return score == null || score === '—';
  });
  if (missingIndicatorScore) {
    return '【部分维度当前缺少基础指标风险分，建议结合近30天故障告警、维修工单和驾驶关联行为明细进一步复核。】';
  }
  const focusIndicators = analysisItems
    .slice(0, 2)
    .map((item) => (typeof item.top_indicator === 'string' ? item.top_indicator : ''))
    .filter((item) => item.length > 0)
    .map((item) => `{${item}}`)
    .join('、');
  return focusIndicators
    ? `【建议围绕${focusIndicators}持续跟踪整改闭环，并同步观察综合风险分是否回落。】`
    : '【建议持续跟踪维修闭环与运行行为改善情况。】';
}

function buildVehicleCoreRiskAssessment(
  rows: Array<Record<string, unknown>>,
  analysisItems: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const plateNumber =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.plate_number', 'identifier']) ??
    readFirstStringAtPaths(report, ['management_summary.plate_number']) ??
    '—';
  const vehicleId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.vehicle_id', 'id']) ??
    readFirstStringAtPaths(report, ['management_summary.vehicle_id']) ??
    '—';
  const overallScore =
    readFirstNumberAtPaths(report, ['core_risk_assessment.overall_score']) ??
    readFirstNumberAtPaths(sourceData ?? {}, [
      'performance_dashboard.summary.overall_score',
      'risk_profile.overall',
    ]);
  const riskLevel = deriveRiskLevelLabel(
    readFirstStringAtPaths(report, [
      'core_risk_assessment.risk_level',
      'management_summary.risk_level',
    ]) ??
      readFirstStringAtPaths(sourceData ?? {}, [
        'performance_dashboard.summary.overall_level',
        'risk_profile.level',
      ]),
    overallScore
  );
  const rankInfo = buildManagementRankInfo(report, sourceData);
  const comparison = buildManagementComparisonText(
    rankInfo.position,
    rankInfo.total,
    rankInfo.percentile
  );
  const rankSentence =
    rankInfo.position != null && rankInfo.total != null && comparison.verb
      ? `综合表现位于所属单位第${rankInfo.position}名(${rankInfo.position}/${rankInfo.total})，显示其${comparison.verb}大多数车辆`
      : rankInfo.position != null
        ? `当前排名第${rankInfo.position}`
        : '当前缺少完整排名快照';
  const topIndicators = analysisItems
    .slice(0, 2)
    .map((item) => (typeof item.top_indicator === 'string' ? `{${item.top_indicator}}` : ''))
    .filter((item) => item.length > 0)
    .join('、');
  const summary = `综合近期运行数据判断，车辆{${plateNumber}}(自编号{${vehicleId}})综合风险值为{${
    overallScore != null ? trimNumberString(overallScore) : '—'
  }}分，当前处于{${riskLevel}}状态，${rankSentence}，【${
    topIndicators
      ? `当前需重点关注${topIndicators}的波动情况，若不及时干预，风险仍可能继续累积。`
      : '当前需持续跟踪故障风险与能耗风险的联动变化。'
  }】`;

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
    attention_note: buildVehicleAttentionNote(analysisItems),
    detail_lines: [],
  };
}

function buildVehicleManagementSummary(
  rows: Array<Record<string, unknown>>,
  coreRiskAssessment: Record<string, unknown>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const plateNumber =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.plate_number', 'identifier']) ??
    readFirstStringAtPaths(report, ['management_summary.plate_number']) ??
    '—';
  const vehicleId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.vehicle_id', 'id']) ??
    readFirstStringAtPaths(report, ['management_summary.vehicle_id']) ??
    '—';
  const vehicleModel =
    readFirstStringAtPaths(sourceData ?? {}, [
      'basic.vehicle_model',
      'basic.type',
      'basic.model',
    ]) ??
    readFirstStringAtPaths(report, ['management_summary.vehicle_model']) ??
    '—';
  const fleetName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.fleet_name']) ??
    readFirstStringAtPaths(report, ['management_summary.fleet_name']) ??
    '—';
  const overallScore = readFirstNumberAtPaths(coreRiskAssessment, ['overall_score']);
  const riskLevel =
    readFirstStringAtPaths(coreRiskAssessment, ['risk_level']) ||
    deriveRiskLevelLabel(
      readFirstStringAtPaths(sourceData ?? {}, [
        'performance_dashboard.summary.overall_level',
        'risk_profile.level',
      ]),
      overallScore
    );
  const reportDate = buildManagementReportDate(report, sourceData);
  const majorRiskFactors = buildVehicleMajorRiskFactors(sourceData, report);
  const factorText = majorRiskFactors.length
    ? majorRiskFactors.map((item) => `{${item}}`).join('、')
    : '当前缺少完整的高风险因子明细';
  const summaryText = `${
    reportDate !== '—' ? `{${reportDate}}` : ''
  }车辆{${plateNumber}}(自编号{${vehicleId}})被系统预判为{${riskLevel}}，主要风险因素为${factorText}，需引起重视。`;

  return {
    report_date: reportDate,
    plate_number: plateNumber,
    vehicle_id: vehicleId,
    vehicle_model: vehicleModel,
    fleet_name: fleetName,
    risk_level: riskLevel,
    major_risk_factors: majorRiskFactors,
    summary_text: summaryText,
  };
}

function buildVehicleLayout(summaryText: string): Record<string, unknown> {
  return {
    title: '车辆安全风险分析总结报告',
    summary: summaryText,
    header: {
      items: [
        { label: '车牌号', value_path: 'management_summary.plate_number' },
        { label: '自编号', value_path: 'management_summary.vehicle_id' },
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
          { type: 'list', items_path: 'behavior_data_analysis.analysis_items', ordered: false },
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

function buildManagementReportAppendix(
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

function normalizeVehicleManagementReport(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  if (readStringAtPath(report, 'error')) {
    return report;
  }

  const rows = buildVehicleDashboardRows(report, sourceData);
  const analysisItems = buildVehicleAnalysisItems(rows, report, sourceData);
  const recommendations = buildVehicleRecommendations(rows, report, sourceData);
  const coreRiskAssessment = buildVehicleCoreRiskAssessment(
    rows,
    analysisItems,
    report,
    sourceData
  );
  const managementSummary = buildVehicleManagementSummary(
    rows,
    coreRiskAssessment,
    report,
    sourceData
  );

  return {
    report_type: 'vehicle_safety_summary_management',
    template_version: '20260305',
    report_role: 'management',
    layout: buildVehicleLayout(
      typeof managementSummary.summary_text === 'string' ? managementSummary.summary_text : ''
    ),
    management_summary: managementSummary,
    dashboard_rows: rows,
    core_risk_assessment: coreRiskAssessment,
    behavior_data_analysis: { analysis_items: analysisItems },
    interventions: { recommendations },
    appendix: buildManagementReportAppendix(report, sourceData),
  };
}

function hasVehicleTemplateMarkerNotation(report: Record<string, unknown>): boolean {
  return hasStructuredReportTemplateMarkerNotation(report);
}

function hasCompleteVehicleManagementReport(report: Record<string, unknown>): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  if (readStringAtPath(report, 'report_type') !== 'vehicle_safety_summary_management') {
    return false;
  }
  if (readStringAtPath(report, 'template_version') !== '20260305') {
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
  if (!Array.isArray(rows) || rows.length !== VEHICLE_REPORT_TARGET_DIMENSIONS.length) {
    return false;
  }
  const dimensions = rows.map((row) =>
    isRecord(row) && typeof row.dimension === 'string' ? row.dimension.trim() : ''
  );
  if (
    dimensions[0] !== '综合风险' ||
    !VEHICLE_REPORT_TARGET_DIMENSIONS.every((dimension) => dimensions.includes(dimension))
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
    recommendations.length > 4
  ) {
    return false;
  }

  return true;
}

const UNIT_REPORT_TARGET_DIMENSIONS = [
  '综合风险',
  '驾驶员风险',
  '车辆风险',
  '线路风险',
  '站场风险',
] as const;
const UNIT_REPORT_ANALYSIS_DIMENSIONS = ['驾驶员风险', '车辆风险', '线路风险', '站场风险'] as const;
type UnitReportDimension = (typeof UNIT_REPORT_TARGET_DIMENSIONS)[number];
type UnitReportAnalysisDimension = (typeof UNIT_REPORT_ANALYSIS_DIMENSIONS)[number];

const UNIT_REPORT_ANALYSIS_PREFIXES = ['风险最高的一级指标是', '其次是', '再次是', '最后是'];
const UNIT_REPORT_SUGGESTION_PREFIXES = ['风险最高的基础指标是', '其次是', '再次是', '最后是'];

function normalizeUnitDimensionName(value: unknown): UnitReportDimension | null {
  if (typeof value !== 'string') return null;
  const simplified = simplifyIndicatorLabel(value);
  return (
    UNIT_REPORT_TARGET_DIMENSIONS.find(
      (dimension) => simplifyIndicatorLabel(dimension) === simplified
    ) ?? null
  );
}

function getUnitSourceDimension(
  sourceData: Record<string, unknown> | null,
  dimension: UnitReportDimension
): Record<string, unknown> | null {
  if (!sourceData) return null;
  return readRecordAtPath(sourceData, `performance_dashboard.dimensions.${dimension}`);
}

function collectUnitIndicatorNames(source: Record<string, unknown>): string[] {
  const names: string[] = [];
  const quotaItems = readArrayAtPath(source, 'appendix.raw_data.quota_items') ?? [];
  for (const item of quotaItems) {
    if (!isRecord(item)) continue;
    const indicator = simplifyIndicatorLabel(item.quota_name ?? item.name);
    if (indicator) {
      names.push(indicator);
    }
  }
  const quotaSummary = readArrayAtPath(source, 'appendix.raw_data.quota_summary') ?? [];
  for (const summary of quotaSummary) {
    if (!isRecord(summary)) continue;
    const indicators = Array.isArray(summary.indicators) ? summary.indicators : [];
    for (const item of indicators) {
      if (!isRecord(item)) continue;
      const indicator = simplifyIndicatorLabel(item.name);
      if (indicator) {
        names.push(indicator);
      }
    }
  }

  const systemTags = readArrayAtPath(source, 'performance_dashboard.system_risk.tags') ?? [];
  for (const item of systemTags) {
    const indicator = simplifyIndicatorLabel(item);
    if (indicator) {
      names.push(indicator);
    }
  }

  const recommendations = getNestedValue(source, 'interventions.recommendations');
  if (Array.isArray(recommendations)) {
    for (const item of recommendations) {
      if (!isRecord(item)) continue;
      const indicator = getRecommendationCandidateIndicator(item);
      if (indicator) {
        names.push(indicator);
      }
    }
  }

  return dedupeDriverIndicatorTexts(names);
}

function buildUnitIndicatorSet(source: Record<string, unknown>): Set<string> {
  return new Set(collectUnitIndicatorNames(source));
}

function buildUnitTrendText(
  row: Record<string, unknown> | null,
  sourceData: Record<string, unknown> | null,
  keys: unknown[]
): string {
  return resolveDashboardTrendText({
    sourceDimension: row,
    sourceData,
    keys,
    includeRouteComparison: true,
    allowOverallFallback: keys.includes('综合风险'),
    defaultText: '同比—，环比—，同单位比—，同线路比—',
  });
}

function getUnitCoreIndicators(
  row: Record<string, unknown> | null,
  allowedIndicators: Set<string>
): string[] {
  const indicators = getStringArray(getNestedValue(row ?? {}, 'core_risk_indicators'))
    .map((item) => simplifyIndicatorLabel(item))
    .filter((item) => item.length > 0 && item !== '—' && allowedIndicators.has(item));
  const topIndicator = simplifyIndicatorLabel(row?.top_indicator);
  const merged = dedupeDriverIndicatorTexts(
    [...indicators, topIndicator].filter(
      (item): item is string =>
        typeof item === 'string' && item.length > 0 && allowedIndicators.has(item)
    )
  );
  return merged;
}

function inferUnitRecommendationDimension(
  indicator: string,
  rows: Array<Record<string, unknown>>,
  sourceData: Record<string, unknown> | null
): UnitReportAnalysisDimension | null {
  const normalized = simplifyIndicatorLabel(indicator);
  if (!normalized) return null;

  const quotaItems = readArrayAtPath(sourceData ?? {}, 'appendix.raw_data.quota_items') ?? [];
  for (const item of quotaItems) {
    if (!isRecord(item)) continue;
    if (simplifyIndicatorLabel(item.quota_name ?? item.name) !== normalized) continue;
    const dimension = normalizeUnitDimensionName(item.dimension);
    if (dimension && dimension !== '综合风险') {
      return dimension as UnitReportAnalysisDimension;
    }
  }

  const quotaSummary = readArrayAtPath(sourceData ?? {}, 'appendix.raw_data.quota_summary') ?? [];
  for (const summary of quotaSummary) {
    if (!isRecord(summary)) continue;
    const dimension = normalizeUnitDimensionName(summary.dimension);
    if (!dimension || dimension === '综合风险') continue;
    const indicators = Array.isArray(summary.indicators) ? summary.indicators : [];
    if (
      indicators.some((item) => isRecord(item) && simplifyIndicatorLabel(item.name) === normalized)
    ) {
      return dimension as UnitReportAnalysisDimension;
    }
  }

  for (const row of rows) {
    const dimension = normalizeUnitDimensionName(row.dimension);
    if (!dimension || dimension === '综合风险') continue;
    const indicators = getStringArray(row.core_risk_indicators).map((item) =>
      simplifyIndicatorLabel(item)
    );
    if (indicators.includes(normalized)) {
      return dimension as UnitReportAnalysisDimension;
    }
  }

  return null;
}

function buildUnitDashboardRows(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const allowedIndicators = sourceData ? buildUnitIndicatorSet(sourceData) : new Set<string>();
  const rows = UNIT_REPORT_TARGET_DIMENSIONS.map((dimension) => {
    const sourceDimension = getUnitSourceDimension(sourceData, dimension);
    const reportRow = findMappedDashboardRow(report, [dimension]);
    const score =
      readFirstNumberAtPaths(reportRow ?? {}, ['score']) ??
      readFirstNumberAtPaths(sourceDimension ?? {}, ['score']);
    const coreRiskIndicators = getUnitCoreIndicators(
      sourceDimension ?? reportRow,
      allowedIndicators
    );
    return {
      dimension,
      score,
      trend_text: buildUnitTrendText(sourceDimension ?? reportRow, sourceData, [dimension]),
      core_risk_indicators: coreRiskIndicators,
      top_indicator: coreRiskIndicators[0] ?? '',
      alert_count:
        readFirstNumberAtPaths(sourceDimension ?? {}, ['alert_count']) ??
        readFirstNumberAtPaths(reportRow ?? {}, ['alert_count']),
    };
  });
  return orderDashboardRowsByOverallThenScore(rows, '综合风险');
}

function getUnitAnalysisRows(rows: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
  return rows
    .filter((row) => {
      const dimension = normalizeUnitDimensionName(row.dimension);
      if (!dimension || dimension === '综合风险') return false;
      const indicators = getStringArray(row.core_risk_indicators).filter((item) => item !== '—');
      return indicators.length > 0;
    })
    .sort((left, right) => {
      const leftScore = typeof left.score === 'number' ? left.score : Number.NEGATIVE_INFINITY;
      const rightScore = typeof right.score === 'number' ? right.score : Number.NEGATIVE_INFINITY;
      return rightScore - leftScore;
    })
    .slice(0, 4);
}

function resolveUnitIndicatorRiskScore(
  sourceData: Record<string, unknown> | null,
  dimension: UnitReportAnalysisDimension,
  indicator: string,
  fallbackScore: number | null
): number | null {
  const normalized = simplifyIndicatorLabel(indicator);
  if (!sourceData || !normalized) return fallbackScore;

  const quotaSummary = readArrayAtPath(sourceData, 'appendix.raw_data.quota_summary') ?? [];
  for (const summary of quotaSummary) {
    if (!isRecord(summary)) continue;
    const summaryDimension = normalizeUnitDimensionName(summary.dimension);
    if (summaryDimension !== dimension) continue;
    const indicators = Array.isArray(summary.indicators) ? summary.indicators : [];
    for (const item of indicators) {
      if (!isRecord(item)) continue;
      if (simplifyIndicatorLabel(item.name ?? item.quota_name ?? item.indicator) !== normalized) {
        continue;
      }
      const score = readFirstNumberAtPaths(item, [
        'final_risk_score',
        'risk_score',
        'original_value',
        'originalValue',
        'score',
      ]);
      if (score != null) return score;
    }
  }

  const quotaItems = readArrayAtPath(sourceData, 'appendix.raw_data.quota_items') ?? [];
  for (const item of quotaItems) {
    if (!isRecord(item)) continue;
    if (normalizeUnitDimensionName(item.dimension ?? item.first_quota_name) !== dimension) continue;
    if (simplifyIndicatorLabel(item.quota_name ?? item.name ?? item.indicator) !== normalized) {
      continue;
    }
    const score = readFirstNumberAtPaths(item, [
      'final_risk_score',
      'risk_score',
      'original_value',
      'originalValue',
      'score',
    ]);
    if (score != null) return score;
  }

  return fallbackScore;
}

function buildUnitAnalysisInsight(input: {
  prefix: string;
  dimension: UnitReportAnalysisDimension;
  indicator: string;
  indicatorScore: number | null;
}): string {
  const scoreText =
    input.indicatorScore != null ? `{${trimNumberString(input.indicatorScore)}}分` : `{—}分`;
  return `${input.prefix}{${input.dimension}}，其中风险值最高的基础指标是{${input.indicator}}${scoreText}，【说明该单位在${input.dimension.replace('风险', '')}侧存在需要跟踪的风险波动，应结合原始明细继续核验成因并推进闭环管理。】`;
}

function buildUnitAnalysisItems(
  rows: Array<Record<string, unknown>>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  return getUnitAnalysisRows(rows).map((row, index) => {
    const dimension = normalizeUnitDimensionName(row.dimension) as UnitReportAnalysisDimension;
    const indicators = getStringArray(row.core_risk_indicators).filter((item) => item !== '—');
    const topIndicator = indicators[0] ?? '';
    const alertCount = parseAlertCount(row.alert_count);
    const indicatorScore = resolveUnitIndicatorRiskScore(
      sourceData,
      dimension,
      topIndicator,
      typeof row.score === 'number' ? row.score : null
    );
    return {
      rank_label: UNIT_REPORT_ANALYSIS_PREFIXES[index] ?? `第${index + 1}`,
      dimension,
      top_indicator: topIndicator,
      alert_count: alertCount ?? '—',
      indicator_score: indicatorScore ?? '—',
      indicators,
      insight: buildUnitAnalysisInsight({
        prefix: UNIT_REPORT_ANALYSIS_PREFIXES[index] ?? `第${index + 1}`,
        dimension,
        indicator: topIndicator,
        indicatorScore,
      }),
    };
  });
}

function listUnitRecommendationIndicators(
  rows: Array<Record<string, unknown>>,
  sourceData: Record<string, unknown> | null
): Array<{
  indicator: string;
  dimension: UnitReportAnalysisDimension;
  score: number | null;
  count: number | null;
}> {
  const quotaSummary = readArrayAtPath(sourceData ?? {}, 'appendix.raw_data.quota_summary') ?? [];
  const candidates: Array<{
    indicator: string;
    dimension: UnitReportAnalysisDimension;
    score: number | null;
    count: number | null;
  }> = [];
  for (const summary of quotaSummary) {
    if (!isRecord(summary)) continue;
    const dimension = normalizeUnitDimensionName(String(summary.dimension ?? ''));
    if (!dimension || dimension === '综合风险') continue;
    const indicators = Array.isArray(summary.indicators) ? summary.indicators : [];
    for (const item of indicators) {
      if (!isRecord(item)) continue;
      const indicator = simplifyIndicatorLabel(item.name);
      if (!indicator) continue;
      candidates.push({
        indicator,
        dimension: dimension as UnitReportAnalysisDimension,
        score: readFirstNumberAtPaths(item, ['score']),
        count: readFirstNumberAtPaths(item, ['count']),
      });
    }
  }

  if (!candidates.length) {
    for (const row of getUnitAnalysisRows(rows)) {
      const dimension = normalizeUnitDimensionName(row.dimension);
      if (!dimension || dimension === '综合风险') continue;
      for (const indicator of getStringArray(row.core_risk_indicators)) {
        const normalized = simplifyIndicatorLabel(indicator);
        if (!normalized || normalized === '—') continue;
        candidates.push({
          indicator: normalized,
          dimension: dimension as UnitReportAnalysisDimension,
          score: typeof row.score === 'number' ? row.score : null,
          count: parseAlertCount(row.alert_count),
        });
      }
    }
  }

  const deduped = new Map<
    string,
    {
      indicator: string;
      dimension: UnitReportAnalysisDimension;
      score: number | null;
      count: number | null;
    }
  >();
  for (const candidate of candidates.sort((left, right) => {
    const scoreDelta = (right.score ?? -Infinity) - (left.score ?? -Infinity);
    if (scoreDelta !== 0) return scoreDelta;
    return (right.count ?? -Infinity) - (left.count ?? -Infinity);
  })) {
    const key = `${candidate.dimension}:${candidate.indicator}`;
    if (!deduped.has(key)) {
      deduped.set(key, candidate);
    }
    if (deduped.size >= 4) break;
  }
  return Array.from(deduped.values());
}

function buildUnitRecommendationText(
  prefix: string,
  indicator: string,
  actionText: string,
  expectedText: string
): string {
  const normalizedActionText = normalizeRecommendationActionText(actionText);
  const normalizedExpectedText = expectedText.trim();
  if (isNoManagementSuggestionText(normalizedActionText)) {
    return `${prefix}{${indicator}}，${NO_MANAGEMENT_SUGGESTION_TEXT}。`;
  }
  if (!normalizedExpectedText) {
    return `${prefix}{${indicator}}，建议开展{${normalizedActionText}}。`;
  }
  return `${prefix}{${indicator}}，建议开展{${normalizedActionText}}，【${normalizedExpectedText}】。`;
}

function buildUnitRecommendations(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  const sourceRecommendations = listSourceRecommendations(sourceData);
  if (sourceRecommendations.length > 0) {
    return sourceRecommendations.map((candidate, index) => {
      const indicator =
        getRecommendationCandidateIndicator(candidate) || `risk_indicator_${index + 1}`;
      const dimension =
        inferUnitRecommendationDimension(indicator, rows, sourceData) ??
        (typeof candidate.dimension === 'string'
          ? (candidate.dimension.trim() as UnitReportAnalysisDimension)
          : '车辆风险');
      const actionText =
        (typeof candidate.action === 'string' && candidate.action.trim()) ||
        (typeof candidate.title === 'string' && candidate.title.trim()) ||
        '';
      const expectedText =
        (typeof candidate.expected_effect === 'string' && candidate.expected_effect.trim()) ||
        (typeof candidate.detail === 'string' && candidate.detail.trim()) ||
        (typeof candidate.rationale === 'string' && candidate.rationale.trim()) ||
        (typeof candidate.policy_reference === 'string' && candidate.policy_reference.trim()) ||
        '';
      return {
        priority: index + 1,
        indicator,
        dimension,
        suggestion: buildUnitRecommendationText(
          UNIT_REPORT_SUGGESTION_PREFIXES[index] ?? '建议重点关注',
          indicator,
          actionText,
          expectedText
        ),
      };
    });
  }

  const rankedIndicators = listUnitRecommendationIndicators(rows, sourceData);
  return rankedIndicators.slice(0, 4).map((item, index) => {
    const actionText = NO_MANAGEMENT_SUGGESTION_TEXT;
    const expectedText = '';
    return {
      priority: index + 1,
      indicator: item.indicator,
      dimension: item.dimension,
      suggestion: buildUnitRecommendationText(
        UNIT_REPORT_SUGGESTION_PREFIXES[index] ?? '建议重点关注',
        item.indicator,
        actionText,
        expectedText
      ),
    };
  });
}

function readUnitHighRiskObjectRows(
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): Array<Record<string, unknown>> {
  const candidatePaths = [
    'core_risk_assessment.high_risk_objects.rows',
    'appendix.raw_data.high_risk_objects.rows',
    'appendix.raw_data.high_risk_rows',
    'appendix.raw_data.risk_objects.rows',
  ];

  for (const path of candidatePaths) {
    const items = readArrayAtPath(report, path) ?? readArrayAtPath(sourceData ?? {}, path);
    if (!Array.isArray(items)) continue;

    const normalizedRows = items.filter(isRecord).map((item, index) => ({
      rank: readFirstNumberAtPaths(item, ['rank', 'ranking', 'risk_rank']) ?? index + 1,
      sub_unit:
        readFirstStringAtPaths(item, ['sub_unit', 'unit', 'unit_name', 'organ_name']) ?? '—',
      driver: readFirstStringAtPaths(item, ['driver', 'driver_name', 'driver_display']) ?? '—',
      vehicle: readFirstStringAtPaths(item, ['vehicle', 'vehicle_name', 'plate_number']) ?? '—',
      route: readFirstStringAtPaths(item, ['route', 'route_name']) ?? '—',
      station: readFirstStringAtPaths(item, ['station', 'station_name', 'yard_name']) ?? '—',
    }));
    if (normalizedRows.length > 0) {
      return normalizedRows;
    }
  }

  return [];
}

function buildUnitHighRiskObjects(
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): Record<string, unknown> {
  const rows = readUnitHighRiskObjectRows(sourceData, report);
  const readCount = (paths: string[]): number | null =>
    readFirstNumberAtPaths(sourceData ?? {}, paths) ?? readFirstNumberAtPaths(report, paths);

  const unitCount =
    readCount([
      'core_risk_assessment.high_risk_objects.unit_count',
      'appendix.raw_data.high_risk_objects.unit_count',
      'appendix.raw_data.high_risk_objects_counts.unit_count',
    ]) ?? null;
  const driverCount =
    readCount([
      'core_risk_assessment.high_risk_objects.driver_count',
      'appendix.raw_data.high_risk_objects.driver_count',
      'appendix.raw_data.high_risk_objects_counts.driver_count',
    ]) ?? null;
  const vehicleCount =
    readCount([
      'core_risk_assessment.high_risk_objects.vehicle_count',
      'appendix.raw_data.high_risk_objects.vehicle_count',
      'appendix.raw_data.high_risk_objects_counts.vehicle_count',
    ]) ?? null;
  const routeCount =
    readCount([
      'core_risk_assessment.high_risk_objects.route_count',
      'appendix.raw_data.high_risk_objects.route_count',
      'appendix.raw_data.high_risk_objects_counts.route_count',
    ]) ?? null;
  const stationCount =
    readCount([
      'core_risk_assessment.high_risk_objects.station_count',
      'appendix.raw_data.high_risk_objects.station_count',
      'appendix.raw_data.high_risk_objects_counts.station_count',
    ]) ?? null;

  const summary =
    rows.length > 0 &&
    [unitCount, driverCount, vehicleCount, routeCount, stationCount].some((item) => item != null)
      ? `该单位目前有{${unitCount ?? rows.length}}个高风险下级单位，{${driverCount ?? rows.length}}位高风险驾驶员，{${vehicleCount ?? rows.length}}台高风险车辆，{${routeCount ?? rows.length}}条高风险线路，{${stationCount ?? rows.length}}个高风险站场，高风险对象如下：`
      : '';

  return {
    unit_count: unitCount,
    driver_count: driverCount,
    vehicle_count: vehicleCount,
    route_count: routeCount,
    station_count: stationCount,
    rows,
    summary,
  };
}

function buildUnitCoreRiskAssessment(
  analysisItems: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const organName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.organ_name', 'name']) ??
    readFirstStringAtPaths(report, ['management_summary.organ_name']) ??
    '—';
  const overallScore =
    readFirstNumberAtPaths(report, ['core_risk_assessment.overall_score']) ??
    readFirstNumberAtPaths(sourceData ?? {}, [
      'performance_dashboard.summary.overall_score',
      'performance_dashboard.dimensions.综合风险.score',
    ]);
  const riskLevel = deriveRiskLevelLabel(
    readFirstStringAtPaths(report, [
      'core_risk_assessment.risk_level',
      'management_summary.risk_level',
    ]) ??
      readFirstStringAtPaths(sourceData ?? {}, [
        'performance_dashboard.summary.overall_level',
        'performance_dashboard.system_risk.level',
      ]),
    overallScore
  );
  const rankInfo = buildManagementRankInfo(report, sourceData);
  const comparison = buildManagementComparisonText(
    rankInfo.position,
    rankInfo.total,
    rankInfo.percentile,
    '单位'
  );
  const rankSentence =
    rankInfo.position != null && rankInfo.total != null && comparison.verb
      ? `综合表现位于所属单位第{${rankInfo.position}}名{(${rankInfo.position}/${rankInfo.total})}，显示其{${comparison.verb}}多数单位`
      : rankInfo.position != null
        ? `综合排名为第{${rankInfo.position}}名`
        : '当前缺少完整排名快照';
  const topIndicators = analysisItems
    .slice(0, 2)
    .map((item) => (typeof item.top_indicator === 'string' ? `{${item.top_indicator}}` : ''))
    .filter((item) => item.length > 0)
    .join('、');
  const highRiskObjects = buildUnitHighRiskObjects(sourceData, report);
  const summary = `综合近期运行数据判断，单位{${organName}}综合风险值为{${
    overallScore != null ? trimNumberString(overallScore) : '—'
  }}分，当前处于{${riskLevel}}状态，${rankSentence}，【${
    topIndicators
      ? `当前需重点关注${topIndicators}等基础指标的波动情况，并围绕驾驶员、车辆、线路、站场四类风险推进闭环。`
      : '当前需持续跟踪驾驶员、车辆、线路、站场四类风险的联动变化。'
  }】`;
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
    attention_note: topIndicators
      ? `【建议围绕${topIndicators}开展专项复盘，避免单位风险进一步扩散。】`
      : '【建议持续跟踪单位风险指标和管理建议闭环情况。】',
    detail_lines: [],
    high_risk_object_summary: highRiskObjects.summary,
    high_risk_objects: {
      unit_count: highRiskObjects.unit_count,
      driver_count: highRiskObjects.driver_count,
      vehicle_count: highRiskObjects.vehicle_count,
      route_count: highRiskObjects.route_count,
      station_count: highRiskObjects.station_count,
      rows: highRiskObjects.rows,
    },
  };
}

function buildUnitMajorRiskFactors(
  sourceData: Record<string, unknown> | null,
  report: Record<string, unknown>
): string[] {
  const sourceTags =
    readArrayAtPath(sourceData ?? {}, 'performance_dashboard.system_risk.tags') ?? [];
  const reportFactors = readArrayAtPath(report, 'management_summary.major_risk_factors') ?? [];
  return dedupeDriverIndicatorTexts(
    [...sourceTags, ...reportFactors]
      .map((item) => simplifyIndicatorLabel(item))
      .filter((item) => item.length > 0)
  ).slice(0, 4);
}

function buildUnitManagementSummary(
  coreRiskAssessment: Record<string, unknown>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const organName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.organ_name', 'name']) ??
    readFirstStringAtPaths(report, ['management_summary.organ_name']) ??
    '—';
  const organId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.organ_id', 'identifier', 'id']) ??
    readFirstStringAtPaths(report, ['management_summary.organ_id']) ??
    '—';
  const overallScore = readFirstNumberAtPaths(coreRiskAssessment, ['overall_score']);
  const riskLevel =
    readFirstStringAtPaths(coreRiskAssessment, ['risk_level']) ||
    deriveRiskLevelLabel(
      readFirstStringAtPaths(sourceData ?? {}, [
        'performance_dashboard.summary.overall_level',
        'performance_dashboard.system_risk.level',
      ]),
      overallScore
    );
  const reportDate = buildManagementReportDate(report, sourceData);
  const majorRiskFactors = buildUnitMajorRiskFactors(sourceData, report);
  const factorText = majorRiskFactors.length
    ? majorRiskFactors.map((item) => `{${item}}`).join('、')
    : '当前缺少完整的高风险因子明细';
  const suggestionStatus = {
    pending_receive_count: readFirstNumberAtPaths(sourceData ?? {}, [
      'appendix.raw_data.suggestion_counts.pending_receive_count',
      'appendix.raw_data.main.pending_receive_count',
    ]),
    pending_confirm_count: readFirstNumberAtPaths(sourceData ?? {}, [
      'appendix.raw_data.suggestion_counts.pending_confirm_count',
      'appendix.raw_data.main.pending_confirm_count',
    ]),
    pending_optimize_count: readFirstNumberAtPaths(sourceData ?? {}, [
      'appendix.raw_data.suggestion_counts.pending_optimize_count',
      'appendix.raw_data.main.pending_optimize_count',
    ]),
  };
  const summaryText = `${
    reportDate !== '—' ? `{${reportDate}}` : ''
  }单位{${organName}}被系统预判为{${riskLevel}}，主要风险因素为${factorText}，需引起重视。【建议结合管理建议状态与四类风险分项推进闭环处置。】`;
  return {
    report_date: reportDate,
    organ_name: organName,
    organ_id: organId,
    risk_level: riskLevel,
    major_risk_factors: majorRiskFactors,
    suggestion_status: suggestionStatus,
    summary_text: summaryText,
  };
}

function buildUnitLayout(summaryText: string): Record<string, unknown> {
  return {
    title: '单位安全风险分析总结报告',
    summary: summaryText,
    header: {
      items: [
        { label: '单位名称', value_path: 'management_summary.organ_name' },
        { label: '单位ID', value_path: 'management_summary.organ_id' },
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
        blocks: [
          { type: 'text', text_path: 'core_risk_assessment.summary' },
          { type: 'text', text_path: 'core_risk_assessment.high_risk_object_summary' },
          {
            type: 'table',
            columns: [
              { title: '风险排名', key: 'rank' },
              { title: '下级单位', key: 'sub_unit' },
              { title: '驾驶员', key: 'driver' },
              { title: '车辆', key: 'vehicle' },
              { title: '线路', key: 'route' },
              { title: '站场', key: 'station' },
            ],
            rows_path: 'core_risk_assessment.high_risk_objects.rows',
          },
        ],
      },
      {
        title: '三、行为与数据关联分析',
        blocks: [
          { type: 'list', items_path: 'behavior_data_analysis.analysis_items', ordered: false },
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

function normalizeUnitManagementReport(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  if (readStringAtPath(report, 'error')) {
    return report;
  }

  const rows = buildUnitDashboardRows(report, sourceData);
  const analysisItems = buildUnitAnalysisItems(rows, sourceData);
  const recommendations = buildUnitRecommendations(rows, report, sourceData);
  const coreRiskAssessment = buildUnitCoreRiskAssessment(analysisItems, report, sourceData);
  const managementSummary = buildUnitManagementSummary(coreRiskAssessment, report, sourceData);

  return {
    report_type: 'unit_safety_summary_management',
    template_version: '20260409',
    report_role: 'management',
    layout: buildUnitLayout(
      typeof managementSummary.summary_text === 'string' ? managementSummary.summary_text : ''
    ),
    management_summary: managementSummary,
    dashboard_rows: rows,
    core_risk_assessment: coreRiskAssessment,
    behavior_data_analysis: { analysis_items: analysisItems },
    interventions: { recommendations },
    appendix: buildManagementReportAppendix(report, sourceData),
  };
}

function hasUnitTemplateMarkerNotation(report: Record<string, unknown>): boolean {
  return hasStructuredReportTemplateMarkerNotation(report);
}

function hasCompleteUnitManagementReport(report: Record<string, unknown>): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  if (readStringAtPath(report, 'report_type') !== 'unit_safety_summary_management') {
    return false;
  }
  if (readStringAtPath(report, 'template_version') !== '20260409') {
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
  if (!Array.isArray(rows) || rows.length !== UNIT_REPORT_TARGET_DIMENSIONS.length) {
    return false;
  }
  const dimensions = rows.map((row) =>
    isRecord(row) && typeof row.dimension === 'string' ? row.dimension.trim() : ''
  );
  if (
    dimensions[0] !== '综合风险' ||
    !UNIT_REPORT_TARGET_DIMENSIONS.every((dimension) => dimensions.includes(dimension))
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
  const analysisDimensions = analysisItems.map((item) =>
    isRecord(item) && typeof item.dimension === 'string' ? item.dimension.trim() : ''
  );
  if (
    analysisDimensions.some(
      (dimension) =>
        !UNIT_REPORT_ANALYSIS_DIMENSIONS.includes(dimension as UnitReportAnalysisDimension)
    ) ||
    new Set(analysisDimensions).size !== analysisDimensions.length
  ) {
    return false;
  }
  const recommendations = getNestedValue(report, 'interventions.recommendations');
  if (
    !Array.isArray(recommendations) ||
    recommendations.length === 0 ||
    recommendations.length > 4
  ) {
    return false;
  }

  const traceableIndicators = buildUnitIndicatorSet(report);
  if (traceableIndicators.size === 0) {
    return false;
  }

  const majorRiskFactors = readArrayAtPath(report, 'management_summary.major_risk_factors') ?? [];
  if (
    majorRiskFactors.some((item) => {
      const indicator = simplifyIndicatorLabel(item);
      return indicator.length > 0 && !traceableIndicators.has(indicator);
    })
  ) {
    return false;
  }

  if (
    rows.some((row) => {
      if (!isRecord(row)) return true;
      return getStringArray(row.core_risk_indicators).some(
        (item) => !traceableIndicators.has(simplifyIndicatorLabel(item))
      );
    })
  ) {
    return false;
  }

  if (
    analysisItems.some((item) => {
      if (!isRecord(item)) return true;
      const indicator = simplifyIndicatorLabel(item.top_indicator);
      return !indicator || !traceableIndicators.has(indicator);
    })
  ) {
    return false;
  }

  if (
    recommendations.some((item) => {
      if (!isRecord(item)) return true;
      const indicator = simplifyIndicatorLabel(item.indicator);
      const suggestion = typeof item.suggestion === 'string' ? item.suggestion.trim() : '';
      return !indicator || !traceableIndicators.has(indicator) || !suggestion;
    })
  ) {
    return false;
  }

  return true;
}

function hasAccidentTemplateMarkerNotation(report: Record<string, unknown>): boolean {
  const errorCode = readStringAtPath(report, 'error');
  if (errorCode) {
    return true;
  }

  const texts: string[] = [];

  const textPaths = [
    'section_1.event.description',
    'section_2.driver_info.behavior_data',
    'section_3.subjective_cause.items',
    'section_3.objective_cause.items',
    'section_4.measures',
  ];

  for (const path of textPaths) {
    const value = getNestedValue(report, path);
    if (typeof value === 'string' && value.trim()) {
      texts.push(value.trim());
    } else if (Array.isArray(value)) {
      for (const item of value) {
        if (typeof item === 'string' && item.trim()) {
          texts.push(item.trim());
        }
      }
    }
  }

  if (!texts.length) {
    return false;
  }

  const hasDataMarker = texts.some((text) => /\{[^{}\r\n]+\}/.test(text));
  const hasAiMarker = texts.some((text) => /\[[^【】\r\n]+\]/.test(text));
  return hasDataMarker && hasAiMarker;
}

function hasCompleteAccidentInvestigationReport(report: Record<string, unknown>): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  if (readStringAtPath(report, 'report_type') !== 'accident_investigation_summary') {
    return false;
  }
  if (readStringAtPath(report, 'template_version') !== '20260415') {
    return false;
  }

  const requiredRecords = [
    'layout',
    'basic',
    'section_1',
    'section_2',
    'section_3',
    'section_4',
    'trigger_analysis',
    'appendix',
  ];
  if (requiredRecords.some((path) => !isRecord(getNestedValue(report, path)))) {
    return false;
  }

  const eventDesc = readStringAtPath(report, 'section_1.event.description');
  if (!eventDesc) {
    return false;
  }
  if (!eventDesc.includes('{')) {
    return false;
  }

  const timeline = getNestedValue(report, 'section_1.response.timeline');
  if (!Array.isArray(timeline) || timeline.length === 0) {
    return false;
  }

  const behaviorData = readStringAtPath(report, 'section_2.driver_info.behavior_data');
  if (!behaviorData) {
    return false;
  }
  if (!behaviorData.includes('{')) {
    return false;
  }

  const canGps = getNestedValue(report, 'section_2.can_gps');
  const hasCanGps = Array.isArray(canGps) && canGps.length > 0;
  const behaviorDataIsPlaceholder = behaviorData === '{暂无数据}';
  if (!hasCanGps && !behaviorDataIsPlaceholder) {
    return false;
  }

  const subjectiveItems = getNestedValue(report, 'section_3.subjective_cause.items');
  if (!Array.isArray(subjectiveItems) || subjectiveItems.length < 2) {
    return false;
  }
  const hasSubjectiveMarkers = subjectiveItems.some((item) => {
    const text = typeof item === 'string' ? item : '';
    return text.includes('{') && (text.includes('[') || text.includes('{暂无数据}'));
  });
  if (!hasSubjectiveMarkers) {
    return false;
  }

  const objectiveItems = getNestedValue(report, 'section_3.objective_cause.items');
  if (!Array.isArray(objectiveItems) || objectiveItems.length < 1) {
    return false;
  }
  const hasObjectiveMarkers = objectiveItems.some((item) => {
    const text = typeof item === 'string' ? item : '';
    return text.includes('{') && (text.includes('[') || text.includes('{暂无数据}'));
  });
  if (!hasObjectiveMarkers) {
    return false;
  }

  const nature = readStringAtPath(report, 'section_3.nature');
  const normalizedNature = nature?.replace(/[{}]/g, '').trim() ?? '';
  if (!['主责', '同责', '次责', '无责', '全责', '暂无数据'].includes(normalizedNature)) {
    return false;
  }

  const measures = getNestedValue(report, 'section_4.measures');
  if (!Array.isArray(measures) || measures.length < 3) {
    return false;
  }
  const validMeasureCount = measures.filter((item) => {
    if (typeof item !== 'string') return false;
    const text = item.trim();
    if (!text) return false;
    return !(text.includes('数据缺失') || text.includes('待补充') || text.includes('待核实'));
  }).length;
  if (validMeasureCount < 3) {
    return false;
  }

  const appendixRawData = readRecordAtPath(report, 'appendix.raw_data');
  if (!appendixRawData || Object.keys(appendixRawData).length === 0) {
    const appendixRecord = readRecordAtPath(report, 'appendix');
    if (!appendixRecord || Object.keys(appendixRecord).length === 0) {
      return false;
    }
  }

  return true;
}

function wrapAccidentDataMarker(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '—';
  return trimmed.includes('{') ? trimmed : `{${trimmed}}`;
}

function readFirstMeaningfulRecordAtPaths(
  source: Record<string, unknown>,
  paths: string[]
): Record<string, unknown> | null {
  for (const path of paths) {
    const value = readRecordAtPath(source, path);
    if (value && Object.keys(value).length > 0) {
      return value;
    }
  }
  return null;
}

function unwrapAccidentSourceData(
  sourceData: Record<string, unknown> | null
): Record<string, unknown> | null {
  if (!sourceData) return null;
  const candidates = [
    getNestedValue(sourceData, 'records.0'),
    getNestedValue(sourceData, 'list.0'),
    getNestedValue(sourceData, 'rows.0'),
    getNestedValue(sourceData, 'data.records.0'),
    getNestedValue(sourceData, 'data.list.0'),
    getNestedValue(sourceData, 'result.records.0'),
    getNestedValue(sourceData, 'result.list.0'),
    getNestedValue(sourceData, 'result.0'),
  ];
  const nested = candidates.find(isRecord);
  if (!nested) return sourceData;
  return {
    ...sourceData,
    ...nested,
    appendix: isRecord(sourceData.appendix) ? sourceData.appendix : nested.appendix,
    suggestions: isRecord(sourceData.suggestions) ? sourceData.suggestions : nested.suggestions,
    driver_stat: sourceData.driver_stat ?? nested.driver_stat,
    behavior_stat: sourceData.behavior_stat ?? nested.behavior_stat,
    unit_stat: sourceData.unit_stat ?? nested.unit_stat,
  };
}

function readFirstBooleanAtPaths(source: Record<string, unknown>, paths: string[]): boolean | null {
  for (const path of paths) {
    const value = getNestedValue(source, path);
    if (typeof value === 'boolean') {
      return value;
    }
  }
  return null;
}

function normalizeAccidentVehiclePlate(value: string | null): string {
  if (!value) return '—';
  const [plate] = value.split('/');
  const trimmed = plate?.trim() ?? '';
  return trimmed || '—';
}

function normalizeAccidentVehicleIdentifier(value: string | null): string {
  if (!value) return '—';
  const [, identifier] = value.split('/');
  const trimmed = identifier?.trim() ?? '';
  return trimmed || '—';
}

function readAccidentLegacyBasic(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  return (
    readFirstMeaningfulRecordAtPaths(sourceData ?? {}, ['basic']) ??
    readFirstMeaningfulRecordAtPaths(report, ['basic']) ??
    {}
  );
}

function buildAccidentIncidentBasic(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const legacyBasic = readAccidentLegacyBasic(report, sourceData);
  const legacyVehicleId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.vehicle_id']) ??
    ([
      readFirstStringAtPaths(sourceData ?? {}, ['busLicenseNum']),
      readFirstStringAtPaths(sourceData ?? {}, ['busCode']),
    ]
      .filter(Boolean)
      .join('/') ||
      null) ??
    readFirstStringAtPaths(report, ['basic.vehicle_id']);

  return {
    incident_id:
      readFirstStringAtPaths(sourceData ?? {}, ['id', 'identifier', 'basic.incident_id']) ??
      readFirstStringAtPaths(report, ['basic.incident_id']) ??
      readFirstStringAtPaths(legacyBasic, ['incident_id']) ??
      '—',
    incident_date:
      readFirstStringAtPaths(sourceData ?? {}, [
        'basic.accident_date',
        'accident_date',
        'accidentDate',
        'date',
      ]) ??
      readFirstStringAtPaths(report, ['basic.incident_date']) ??
      readFirstStringAtPaths(legacyBasic, ['accident_date']) ??
      '—',
    driver_name:
      readFirstStringAtPaths(sourceData ?? {}, [
        'basic.driver_name',
        'driver_name',
        'driverName',
        'employeeName',
      ]) ??
      readFirstStringAtPaths(report, ['basic.driver_name']) ??
      '—',
    vehicle_plate:
      readFirstStringAtPaths(sourceData ?? {}, [
        'basic.vehicle_plate',
        'plate_number',
        'busLicenseNum',
      ]) ??
      readFirstStringAtPaths(report, ['basic.vehicle_plate']) ??
      normalizeAccidentVehiclePlate(legacyVehicleId),
    route_name:
      readFirstStringAtPaths(sourceData ?? {}, [
        'basic.route_name',
        'route_name',
        'lineName',
        'routeName',
      ]) ??
      readFirstStringAtPaths(report, ['basic.route_name']) ??
      '—',
    location:
      readFirstStringAtPaths(sourceData ?? {}, ['basic.location', 'location', 'accidentPlace']) ??
      readFirstStringAtPaths(report, ['basic.location']) ??
      '—',
    vehicle_identifier: normalizeAccidentVehicleIdentifier(legacyVehicleId),
  };
}

function buildAccidentReportTitle(
  basic: Record<string, unknown>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): string {
  const unitName =
    readFirstStringAtPaths(sourceData ?? {}, [
      'basic.unit_name',
      'unit_name',
      'basic.organization',
      'orgName',
      'deptName',
    ]) ??
    readFirstStringAtPaths(report, ['basic.unit_name', 'basic.organization']) ??
    'XX单位';
  return `{${unitName}}关于\n调查情况和整改措施报告`;
}

function buildAccidentSection1Event(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const basic = buildAccidentIncidentBasic(report, sourceData);
  const rawDesc =
    readFirstStringAtPaths(sourceData ?? {}, [
      'section_1.event.description',
      'basic.event_description',
      'accidentDesc',
      'section_1_event_and_response.accident_process.description',
    ]) ??
    readFirstStringAtPaths(report, [
      'section_1.event.description',
      'section_1_event_and_response.accident_process.description',
    ]) ??
    '';
  const weather =
    readFirstStringAtPaths(sourceData ?? {}, [
      'section_1_event_and_response.accident_process.weather',
    ]) ??
    readFirstStringAtPaths(report, ['section_1_event_and_response.accident_process.weather']) ??
    '';
  const accidentTime =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.accident_time', 'accident_time']) ??
    readFirstStringAtPaths(sourceData ?? {}, ['accidentDate']) ??
    readFirstStringAtPaths(report, ['basic.accident_time']) ??
    '';

  const formattedDesc =
    [accidentTime.trim(), String(basic.location ?? '').trim(), rawDesc.trim(), weather.trim()]
      .filter((item) => item && item !== '—')
      .join('，') || '事故发生经过数据缺失';

  return {
    title: '（一）事故发生经过',
    description: wrapAccidentDataMarker(formattedDesc),
  };
}

function buildAccidentSection1Response(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const rawTimeline =
    getNestedValue(sourceData ?? {}, 'section_1.response.timeline') ??
    getNestedValue(report, 'section_1.response.timeline') ??
    getNestedValue(
      sourceData ?? {},
      'section_1_event_and_response.emergency_response.reporting_flow'
    ) ??
    getNestedValue(report, 'section_1_event_and_response.emergency_response.reporting_flow');

  let timeline: unknown[];
  if (Array.isArray(rawTimeline)) {
    timeline = rawTimeline
      .map((item) => {
        if (typeof item === 'string') {
          return wrapAccidentDataMarker(item);
        }
        if (isRecord(item)) {
          const time = typeof item.time === 'string' ? item.time.trim() : '';
          const step = typeof item.step === 'string' ? item.step.trim() : '';
          return time || step ? wrapAccidentDataMarker([time, step].filter(Boolean).join(' ')) : '';
        }
        return '';
      })
      .filter((item) => typeof item === 'string' && item.trim().length > 0);
  } else {
    timeline = ['【信息上报流程数据缺失】'];
  }

  return {
    title: '（二）事故应急处置情况',
    timeline,
  };
}

function buildAccidentSection1Loss(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const injury =
    readFirstStringAtPaths(sourceData ?? {}, [
      'section_1.loss.injury',
      'basic.injury',
      'section_1_event_and_response.casualty_and_loss.injury',
    ]) ??
    readFirstStringAtPaths(report, [
      'section_1.loss.injury',
      'section_1_event_and_response.casualty_and_loss.injury',
    ]) ??
    '—';
  const economicValue =
    readFirstStringAtPaths(sourceData ?? {}, ['section_1.loss.economic', 'basic.economic_loss']) ??
    readFirstStringAtPaths(report, ['section_1.loss.economic']) ??
    null;
  const legacyEconomic =
    readFirstNumberAtPaths(sourceData ?? {}, [
      'section_1_event_and_response.casualty_and_loss.direct_loss_amount',
    ]) ??
    readFirstNumberAtPaths(report, [
      'section_1_event_and_response.casualty_and_loss.direct_loss_amount',
    ]);
  const economic =
    economicValue ?? (legacyEconomic != null ? trimNumberString(legacyEconomic) : '—');

  return {
    title: '（三）人员伤亡和直接经济损失情况',
    injury: injury === '—' ? '—' : wrapAccidentDataMarker(injury),
    economic: economic === '—' ? '—' : wrapAccidentDataMarker(`${economic}万`),
    items: [
      { label: '人员伤亡情况', value: injury === '—' ? '—' : wrapAccidentDataMarker(injury) },
      {
        label: '直接经济损失',
        value: economic === '—' ? '—' : wrapAccidentDataMarker(`${economic}万`),
      },
    ],
  };
}

function buildAccidentSection1(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  return {
    event: buildAccidentSection1Event(report, sourceData),
    response: buildAccidentSection1Response(report, sourceData),
    loss: buildAccidentSection1Loss(report, sourceData),
  };
}

function buildAccidentSection2UnitInfo(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<{ label: string; value: string }> {
  const rawData =
    readFirstMeaningfulRecordAtPaths(sourceData ?? {}, [
      'section_2.unit_info',
      'section_2_investigation.unit_and_route_overview',
    ]) ??
    readFirstMeaningfulRecordAtPaths(report, [
      'section_2.unit_info',
      'section_2_investigation.unit_and_route_overview',
    ]) ??
    {};

  return [
    {
      label: '营运车辆',
      value:
        (rawData.vehicle_count ?? rawData.operating_vehicles)
          ? wrapAccidentDataMarker(
              `${String(rawData.vehicle_count ?? rawData.operating_vehicles)}台`
            )
          : '—',
    },
    {
      label: '员工',
      value:
        (rawData.employee_count ?? rawData.employees)
          ? wrapAccidentDataMarker(`${String(rawData.employee_count ?? rawData.employees)}人`)
          : '—',
    },
    {
      label: '驾驶员',
      value:
        (rawData.driver_count ?? rawData.drivers)
          ? wrapAccidentDataMarker(`${String(rawData.driver_count ?? rawData.drivers)}人`)
          : '—',
    },
    {
      label: '上一年总里程',
      value:
        (rawData.total_mileage ?? rawData.year_total_mileage_wan_km)
          ? wrapAccidentDataMarker(
              `${String(rawData.total_mileage ?? rawData.year_total_mileage_wan_km)}万公里`
            )
          : '—',
    },
    {
      label: '营运线路',
      value:
        (rawData.route_count ?? rawData.operating_routes)
          ? wrapAccidentDataMarker(`${String(rawData.route_count ?? rawData.operating_routes)}条`)
          : '—',
    },
    {
      label: '事发线路',
      value:
        (rawData.route_name ?? rawData.incident_route)
          ? wrapAccidentDataMarker(String(rawData.route_name ?? rawData.incident_route))
          : '—',
    },
  ];
}

function buildAccidentSection2DriverBasic(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<{ label: string; value: string }> {
  const rawData =
    readFirstMeaningfulRecordAtPaths(sourceData ?? {}, [
      'section_2.driver_info',
      'section_2_investigation.driver_profile',
    ]) ??
    readFirstMeaningfulRecordAtPaths(report, [
      'section_2.driver_info',
      'section_2_investigation.driver_profile',
    ]) ??
    {};
  const driverStat =
    readFirstMeaningfulRecordAtPaths(sourceData ?? {}, ['driver_stat.result', 'driver_stat']) ??
    readFirstMeaningfulRecordAtPaths(report, ['driver_stat.result', 'driver_stat']);
  if (driverStat?.accidentCount != null && rawData.recent_accidents == null) {
    rawData.recent_accidents = String(driverStat.accidentCount);
  }
  if (driverStat?.trafficCount != null && rawData.recent_violations == null) {
    rawData.recent_violations = String(driverStat.trafficCount);
  }

  return [
    {
      label: '姓名',
      value:
        (rawData.driver_name ?? rawData.name)
          ? wrapAccidentDataMarker(String(rawData.driver_name ?? rawData.name))
          : '—',
    },
    { label: '性别', value: rawData.gender ? wrapAccidentDataMarker(String(rawData.gender)) : '—' },
    {
      label: '年龄',
      value: rawData.age ? wrapAccidentDataMarker(`${String(rawData.age)}岁`) : '—',
    },
    {
      label: '驾照类型',
      value:
        (rawData.license_type ?? rawData.license)
          ? wrapAccidentDataMarker(String(rawData.license_type ?? rawData.license))
          : '—',
    },
    {
      label: '驾照有效期',
      value: rawData.license_validity
        ? wrapAccidentDataMarker(String(rawData.license_validity))
        : '—',
    },
    {
      label: '近1年事故',
      value:
        (rawData.accident_count_1y ?? rawData.recent_accidents)
          ? wrapAccidentDataMarker(
              `${String(rawData.accident_count_1y ?? rawData.recent_accidents)}起`
            )
          : '—',
    },
    {
      label: '近1年违法',
      value:
        (rawData.violation_count_1y ?? rawData.recent_violations)
          ? wrapAccidentDataMarker(
              `${String(rawData.violation_count_1y ?? rawData.recent_violations)}起`
            )
          : '—',
    },
  ];
}

function readAccidentBehaviorStatItems(
  source: Record<string, unknown>
): Array<{ name: string; count: number }> {
  const rawItems =
    readFirstArrayAtPaths(source, [
      'behavior_stat.result',
      'behavior_stat.data.result',
      'behavior_stat',
    ]) ?? [];

  return rawItems
    .filter(isRecord)
    .map((item) => {
      const name =
        readFirstStringAtPaths(item, [
          'eventName',
          'eventType',
          'behavior_type_name',
          'name',
        ]) ?? '';
      const count = readFirstNumberAtPaths(item, [
        'eventNum',
        'eventCount',
        'behavior_event_count',
        'count',
      ]);
      return { name, count };
    })
    .filter((item): item is { name: string; count: number } => {
      return Boolean(item.name) && item.count != null;
    });
}

function formatAccidentBehaviorItems(items: Array<{ name: string; count: number }>): string {
  return items.map((item) => `{${item.name} ${trimNumberString(item.count)} 次}`).join('，');
}

function buildAccidentSection2DriverBehavior(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): string {
  const behaviorStatItems = [
    ...readAccidentBehaviorStatItems(sourceData ?? {}),
    ...readAccidentBehaviorStatItems(report),
  ];
  if (behaviorStatItems.length > 0) {
    return formatAccidentBehaviorItems(behaviorStatItems);
  }

  const rawBehavior =
    getNestedValue(sourceData ?? {}, 'section_2.driver_info.behavior_data') ??
    getNestedValue(report, 'section_2.driver_info.behavior_data');

  if (typeof rawBehavior === 'string' && rawBehavior.trim()) {
    return wrapAccidentDataMarker(rawBehavior);
  }

  const behaviorMap =
    readRecordAtPath(sourceData ?? {}, 'section_2_investigation.driver_profile.behavior_counts') ??
    readRecordAtPath(report, 'section_2_investigation.driver_profile.behavior_counts');
  if (behaviorMap) {
    const items = [
      typeof behaviorMap.fatigue_yawn === 'number'
        ? `{疲劳打哈欠 ${behaviorMap.fatigue_yawn} 次}`
        : '',
      typeof behaviorMap.zebra_crossing_acceleration === 'number'
        ? `{斑马线加速 ${behaviorMap.zebra_crossing_acceleration} 次}`
        : '',
      typeof behaviorMap.start_sudden_acceleration === 'number'
        ? `{起步急加速 ${behaviorMap.start_sudden_acceleration} 次}`
        : '',
      typeof behaviorMap.zebra_crossing_no_yield === 'number'
        ? `{斑马线未礼让行人 ${behaviorMap.zebra_crossing_no_yield} 次}`
        : '',
      typeof behaviorMap.sudden_acceleration === 'number'
        ? `{急加速 ${behaviorMap.sudden_acceleration} 次}`
        : '',
      typeof behaviorMap.irregular_stop_entry === 'number'
        ? `{不规范进站 ${behaviorMap.irregular_stop_entry} 次}`
        : '',
      typeof behaviorMap.neutral_coasting === 'number'
        ? `{空档滑行 ${behaviorMap.neutral_coasting} 次}`
        : '',
      typeof behaviorMap.left_turn_no_brake === 'number'
        ? `{左转弯未刹车 ${behaviorMap.left_turn_no_brake} 次}`
        : '',
      typeof behaviorMap.improper_handbrake_ratio === 'number'
        ? `{违规使用手刹（占比 ${Math.round(Number(behaviorMap.improper_handbrake_ratio) * 100)}%）}`
        : '',
    ].filter(Boolean);
    if (items.length > 0) {
      return items.join('，');
    }
  }

  const driverStatBehaviorItems =
    readFirstArrayAtPaths(sourceData ?? {}, [
      'driver_stat.result.behaviorCounts',
      'driver_stat.behaviorCounts',
    ]) ??
    readFirstArrayAtPaths(report, ['driver_stat.result.behaviorCounts', 'driver_stat.behaviorCounts']);
  if (driverStatBehaviorItems && driverStatBehaviorItems.length > 0) {
    const items = driverStatBehaviorItems
      .filter(isRecord)
      .map((item) => {
        const name =
          readFirstStringAtPaths(item, ['eventType', 'eventName', 'behavior_type_name', 'name']) ??
          '';
        const count = readFirstNumberAtPaths(item, [
          'eventCount',
          'eventNum',
          'behavior_event_count',
          'count',
        ]);
        return name && count != null ? `{${name} ${trimNumberString(count)} 次}` : '';
      })
      .filter((item) => item.trim());
    if (items.length > 0) {
      return items.join('，');
    }
  }

  const behaviorArray =
    getNestedValue(sourceData ?? {}, 'basic.behavior_summary') ??
    getNestedValue(report, 'section_2.driver_info.behavior_summary');

  if (Array.isArray(behaviorArray) && behaviorArray.length > 0) {
    const items = behaviorArray
      .map((item) => {
        if (typeof item === 'string') {
          return wrapAccidentDataMarker(item);
        }
        if (isRecord(item)) {
          const name = typeof item.name === 'string' ? item.name : '';
          const count = typeof item.count === 'number' ? item.count : null;
          if (name && count != null) {
            return `{${name}${count}次}`;
          }
          return name ? `{${name}}` : '';
        }
        return '';
      })
      .filter((item) => item.trim());
    return items.length > 0 ? items.join('，') : '{暂无数据}';
  }

  return '{暂无数据}';
}

function buildAccidentSection2DriverAttendance(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<{ label: string; value: string }> {
  const rawData =
    readFirstMeaningfulRecordAtPaths(sourceData ?? {}, [
      'driver_stat.result',
      'driver_stat',
      'section_2.driver_info.attendance',
      'section_2_investigation.driver_profile.work_hours',
    ]) ??
    readFirstMeaningfulRecordAtPaths(report, [
      'driver_stat.result',
      'driver_stat',
      'section_2.driver_info.attendance',
      'section_2_investigation.driver_profile.work_hours',
    ]) ??
    {};
  const overtimeHours =
    rawData.workTimeOver ??
    rawData.overtime_hours ??
    (typeof rawData.overtime === 'boolean' ? (rawData.overtime ? 1 : 0) : null);
  if (rawData.workTime != null && rawData.work_hours == null) {
    rawData.work_hours = String(rawData.workTime);
  }
  if (rawData.workDay != null && rawData.consecutive_days == null) {
    rawData.consecutive_days = String(rawData.workDay);
  }

  return [
    {
      label: '事发当日工时',
      value:
        (rawData.work_hours ?? rawData.daily_hours)
          ? wrapAccidentDataMarker(`${String(rawData.work_hours ?? rawData.daily_hours)}小时`)
          : '—',
    },
    {
      label: '连续工作天数',
      value:
        (rawData.consecutive_days ?? rawData.consecutive_work_days)
          ? wrapAccidentDataMarker(
              `${String(rawData.consecutive_days ?? rawData.consecutive_work_days)}天`
            )
          : '—',
    },
    {
      label: '超时小时',
      value: overtimeHours != null ? wrapAccidentDataMarker(`${String(overtimeHours)}小时`) : '—',
    },
  ];
}

function buildAccidentSection2Driver(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const physicalExam =
    readFirstStringAtPaths(sourceData ?? {}, [
      'section_2.driver_info.physical_exam',
      'section_2_investigation.driver_profile.medical_exam_2024',
    ]) ??
    readFirstStringAtPaths(report, [
      'section_2.driver_info.physical_exam',
      'section_2_investigation.driver_profile.medical_exam_2024',
    ]) ??
    '—';

  return {
    basic: buildAccidentSection2DriverBasic(report, sourceData),
    behavior_data: buildAccidentSection2DriverBehavior(report, sourceData),
    behavior_summary: [],
    physical_exam: physicalExam === '—' ? '—' : wrapAccidentDataMarker(physicalExam),
    attendance: buildAccidentSection2DriverAttendance(report, sourceData),
  };
}

function buildAccidentSection2Vehicle(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<{ label: string; value: string }> {
  const rawData =
    readFirstMeaningfulRecordAtPaths(sourceData ?? {}, [
      'section_2.vehicle_info',
      'section_2_investigation.vehicle_profile',
    ]) ??
    readFirstMeaningfulRecordAtPaths(report, [
      'section_2.vehicle_info',
      'section_2_investigation.vehicle_profile',
    ]) ??
    {};
  const legacyVehicleId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.vehicle_id']) ??
    readFirstStringAtPaths(report, ['basic.vehicle_id']);
  const annualInspectionValid = readFirstBooleanAtPaths(rawData, ['annual_inspection_valid']);
  const insuranceValid = readFirstBooleanAtPaths(rawData, ['insurance_valid']);
  const insuranceStatus =
    typeof rawData.insurance_status === 'string' && rawData.insurance_status.trim()
      ? rawData.insurance_status
      : annualInspectionValid != null || insuranceValid != null
        ? `${annualInspectionValid === false ? '年审无效' : '年审有效'}/${insuranceValid === false ? '保险无效' : '保险有效'}`
        : '';

  return [
    {
      label: '车辆型号',
      value:
        (rawData.vehicle_model ?? rawData.model)
          ? wrapAccidentDataMarker(String(rawData.vehicle_model ?? rawData.model))
          : '—',
    },
    {
      label: '车牌号',
      value:
        normalizeAccidentVehiclePlate(legacyVehicleId) !== '—'
          ? wrapAccidentDataMarker(normalizeAccidentVehiclePlate(legacyVehicleId))
          : rawData.plate_number
            ? wrapAccidentDataMarker(String(rawData.plate_number))
            : '—',
    },
    {
      label: '自编号',
      value:
        normalizeAccidentVehicleIdentifier(legacyVehicleId) !== '—'
          ? wrapAccidentDataMarker(normalizeAccidentVehicleIdentifier(legacyVehicleId))
          : rawData.vehicle_id
            ? wrapAccidentDataMarker(String(rawData.vehicle_id))
            : '—',
    },
    { label: '年审/保险', value: insuranceStatus ? wrapAccidentDataMarker(insuranceStatus) : '—' },
    {
      label: '最近保养日期',
      value: rawData.last_maintenance
        ? wrapAccidentDataMarker(String(rawData.last_maintenance))
        : '—',
    },
    {
      label: '设备状态',
      value:
        (rawData.device_status ?? rawData.equipment_status)
          ? wrapAccidentDataMarker(String(rawData.device_status ?? rawData.equipment_status))
          : '—',
    },
  ];
}

function buildAccidentSection2CanGps(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<{ label: string; value: string }> {
  const rawData =
    readFirstMeaningfulRecordAtPaths(sourceData ?? {}, [
      'section_2.can_gps',
      'section_2_investigation.replay_and_can',
    ]) ??
    readFirstMeaningfulRecordAtPaths(report, [
      'section_2.can_gps',
      'section_2_investigation.replay_and_can',
    ]) ??
    {};
  const accidentTime =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.accident_time', 'accidentDate']) ??
    readFirstStringAtPaths(report, ['basic.accident_time']) ??
    (typeof rawData.accident_time === 'string' ? rawData.accident_time : null);

  return [
    { label: '事故发生时间', value: accidentTime ? wrapAccidentDataMarker(accidentTime) : '—' },
    {
      label: '车速',
      value:
        (rawData.speed ?? rawData.speed_kmh)
          ? wrapAccidentDataMarker(`${String(rawData.speed ?? rawData.speed_kmh)}公里/小时`)
          : '—',
    },
    {
      label: '加速度',
      value:
        (rawData.acceleration ?? rawData.acceleration_mps2)
          ? wrapAccidentDataMarker(
              `${String(rawData.acceleration ?? rawData.acceleration_mps2)}m/s²`
            )
          : '—',
    },
    {
      label: '制动踏板开度',
      value:
        (rawData.brake_pedal ?? rawData.brake_pedal_opening)
          ? wrapAccidentDataMarker(String(rawData.brake_pedal ?? rawData.brake_pedal_opening))
          : '—',
    },
    {
      label: '加速踏板开度',
      value:
        (rawData.accel_pedal ?? rawData.throttle_opening)
          ? wrapAccidentDataMarker(String(rawData.accel_pedal ?? rawData.throttle_opening))
          : '—',
    },
    { label: '档位', value: rawData.gear ? wrapAccidentDataMarker(String(rawData.gear)) : '—' },
  ];
}

function buildAccidentSection2(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  return {
    unit_info: buildAccidentSection2UnitInfo(report, sourceData),
    driver_info: buildAccidentSection2Driver(report, sourceData),
    vehicle_info: buildAccidentSection2Vehicle(report, sourceData),
    can_gps: buildAccidentSection2CanGps(report, sourceData),
  };
}

function normalizeAccidentCauseItems(rawItems: unknown, missingLabel: string): string[] {
  if (!Array.isArray(rawItems)) return [`{暂无数据}，[${missingLabel}]`];
  const items = rawItems
    .map((item) => {
      if (typeof item !== 'string') return '';
      if (item.includes('{') && item.includes('[')) return item;
      if (item.includes('{')) return `[${item}]`;
      if (item.includes('[')) return `{证据数据缺失}，${item}`;
      return `{证据数据缺失}，[${item}]`;
    })
    .filter((item) => item.trim().length > 0);
  return items.length > 0 ? items : [`{暂无数据}，[${missingLabel}]`];
}

function buildAccidentSection3SubjectiveCause(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const rawItems =
    getNestedValue(sourceData ?? {}, 'section_3.subjective_cause.items') ??
    getNestedValue(report, 'section_3.subjective_cause.items') ??
    getNestedValue(sourceData ?? {}, 'section_3_cause_and_nature.subjective_causes') ??
    getNestedValue(report, 'section_3_cause_and_nature.subjective_causes');
  const fallbackOpinion = readFirstStringAtPaths(sourceData ?? {}, ['driverHandleOpinion']);
  const effectiveItems = rawItems ?? (fallbackOpinion ? [fallbackOpinion] : null);
  const items = normalizeAccidentCauseItems(effectiveItems, '主观原因分析数据缺失');

  return {
    title: '（一）主观原因分析',
    items: items
      .concat(['{暂无数据}，[主观原因补充材料未提供]'])
      .slice(0, Math.max(2, items.length)),
  };
}

function buildAccidentSection3ObjectiveCause(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const rawItems =
    getNestedValue(sourceData ?? {}, 'section_3.objective_cause.items') ??
    getNestedValue(report, 'section_3.objective_cause.items') ??
    getNestedValue(sourceData ?? {}, 'section_3_cause_and_nature.objective_causes') ??
    getNestedValue(report, 'section_3_cause_and_nature.objective_causes');
  const fallbackCause = readFirstStringAtPaths(sourceData ?? {}, ['accidentCause']);
  const effectiveItems = rawItems ?? (fallbackCause ? [`事故原因：${fallbackCause}`] : null);

  return {
    title: '（二）客观原因分析',
    items: normalizeAccidentCauseItems(effectiveItems, '客观原因分析数据缺失'),
  };
}

function buildAccidentSection3Nature(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): string {
  const rawNature =
    readFirstStringAtPaths(sourceData ?? {}, [
      'section_3.nature',
      'basic.responsibility',
      'section_3_cause_and_nature.accident_nature',
      'accidentLiability',
    ]) ??
    readFirstStringAtPaths(report, [
      'section_3.nature',
      'section_3_cause_and_nature.accident_nature',
    ]) ??
    '';

  const normalized = rawNature.trim();
  const liabilityCodeMap: Record<string, string> = {
    '048001': '无责',
    '048002': '次责',
    '048003': '同责',
    '048004': '主责',
    '048005': '全责',
  };
  const mappedNature = liabilityCodeMap[normalized] ?? normalized;
  return ['主责', '同责', '次责', '无责', '全责'].includes(mappedNature)
    ? `{${mappedNature}}`
    : '【事故性质/责任认定数据缺失】';
}

function buildAccidentSection3(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  return {
    subjective_cause: buildAccidentSection3SubjectiveCause(report, sourceData),
    objective_cause: buildAccidentSection3ObjectiveCause(report, sourceData),
    nature: buildAccidentSection3Nature(report, sourceData),
  };
}

function buildAccidentSection4Measures(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): string[] {
  const rawMeasures = getNestedValue(sourceData ?? {}, 'section_4.measures');

  if (Array.isArray(rawMeasures) && rawMeasures.length >= 3) {
    return rawMeasures
      .map((item) => (typeof item === 'string' ? wrapAccidentDataMarker(item) : ''))
      .filter((item) => item.trim().length > 0);
  }

  const suggestionMeasures = [
    ...(readArrayAtPath(sourceData ?? {}, 'suggestions.driver_suggestions') ?? []),
    ...(readArrayAtPath(sourceData ?? {}, 'suggestions.route_suggestions') ?? []),
    ...(readArrayAtPath(sourceData ?? {}, 'suggestions.bus_suggestions') ?? []),
  ]
    .filter(isRecord)
    .map((item) => {
      const indicator = readFirstStringAtPaths(item, ['quota_name', 'indicator', 'title']);
      const content = readFirstStringAtPaths(item, ['suggested_content', 'action', 'content']);
      if (!content) return null;
      return wrapAccidentDataMarker(indicator ? `${indicator}：${content}` : content);
    })
    .filter((item): item is string => Boolean(item && item.trim()));
  if (suggestionMeasures.length > 0) {
    return [
      ...suggestionMeasures,
      ...Array(Math.max(0, 3 - suggestionMeasures.length)).fill(NO_MANAGEMENT_SUGGESTION_TEXT),
    ].slice(0, Math.max(3, suggestionMeasures.length));
  }

  const rawOpinionMeasures = [
    readFirstStringAtPaths(sourceData ?? {}, ['improveMeasures']),
    readFirstStringAtPaths(sourceData ?? {}, ['teamLeaderOpinion']),
    readFirstStringAtPaths(sourceData ?? {}, ['safetyOfficerOpinion']),
    readFirstStringAtPaths(sourceData ?? {}, ['branchLeaderOpinion']),
  ]
    .filter((item): item is string => Boolean(item && item.trim()))
    .map((item) => wrapAccidentDataMarker(item));
  if (rawOpinionMeasures.length > 0) {
    return [
      ...rawOpinionMeasures,
      ...Array(Math.max(0, 3 - rawOpinionMeasures.length)).fill(NO_MANAGEMENT_SUGGESTION_TEXT),
    ].slice(0, Math.max(3, rawOpinionMeasures.length));
  }

  const legacyMeasureGroups = [
    readFirstArrayAtPaths(sourceData ?? {}, [
      'section_4_rectification_plan.awareness_and_responsibility',
    ]),
    readFirstArrayAtPaths(sourceData ?? {}, [
      'section_4_rectification_plan.targeted_training_and_controls',
    ]),
    readFirstArrayAtPaths(sourceData ?? {}, [
      'section_4_rectification_plan.risk_control_and_prevention',
    ]),
    readFirstArrayAtPaths(sourceData ?? {}, [
      'section_4_rectification_plan.online_offline_supervision',
    ]),
    readFirstArrayAtPaths(sourceData ?? {}, [
      'section_4_rectification_plan.accountability_and_culture',
    ]),
  ];
  const flattened = legacyMeasureGroups
    .flatMap((group) => (Array.isArray(group) ? group : []))
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => wrapAccidentDataMarker(item));
  if (flattened.length >= 3) {
    return flattened;
  }

  return [
    NO_MANAGEMENT_SUGGESTION_TEXT,
    NO_MANAGEMENT_SUGGESTION_TEXT,
    NO_MANAGEMENT_SUGGESTION_TEXT,
  ];
}

function buildAccidentSection4(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  return {
    measures: buildAccidentSection4Measures(report, sourceData),
  };
}

function buildAccidentTriggerAnalysis(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const matchedSignals =
    getNestedValue(sourceData ?? {}, 'trigger_analysis.matched_signals') ??
    getNestedValue(report, 'trigger_analysis.matched_signals');

  const missingData =
    getNestedValue(sourceData ?? {}, 'trigger_analysis.missing_data') ??
    getNestedValue(report, 'trigger_analysis.missing_data');

  return {
    matched_signals: Array.isArray(matchedSignals) ? matchedSignals : [],
    missing_data: Array.isArray(missingData) ? missingData : [],
  };
}

function buildAccidentLayout(reportTitle: string): Record<string, unknown> {
  return {
    title: reportTitle,
    summary: '',
    sections: [
      {
        title: '一、事故发生经过及应急处置情况',
        blocks: [
          { type: 'text', text_path: 'section_1.event.title' },
          { type: 'text', text_path: 'section_1.event.description' },
          { type: 'text', text_path: 'section_1.response.title' },
          { type: 'list', items_path: 'section_1.response.timeline', ordered: false },
          { type: 'text', text_path: 'section_1.loss.title' },
          { type: 'kv', items_path: 'section_1.loss.items' },
        ],
      },
      {
        title: '二、事故调查情况',
        blocks: [
          { type: 'kv', items_path: 'section_2.unit_info' },
          { type: 'kv', items_path: 'section_2.driver_info.basic' },
          { type: 'text', text_path: 'section_2.driver_info.behavior_data' },
          { type: 'kv', items_path: 'section_2.driver_info.attendance' },
          { type: 'kv', items_path: 'section_2.vehicle_info' },
          { type: 'kv', items_path: 'section_2.can_gps' },
        ],
      },
      {
        title: '三、事故调查原因分析及事故性质',
        blocks: [
          { type: 'text', text_path: 'section_3.subjective_cause.title' },
          { type: 'list', items_path: 'section_3.subjective_cause.items', ordered: true },
          { type: 'text', text_path: 'section_3.objective_cause.title' },
          { type: 'list', items_path: 'section_3.objective_cause.items', ordered: true },
          { type: 'text', text_path: 'section_3.nature' },
        ],
      },
      {
        title: '四、整改措施和下阶段计划',
        blocks: [{ type: 'list', items_path: 'section_4.measures', ordered: true }],
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

function normalizeAccidentInvestigationReport(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const normalizedSourceData = unwrapAccidentSourceData(sourceData);
  if (
    readStringAtPath(report, 'error') &&
    (!normalizedSourceData || Object.keys(normalizedSourceData).length === 0)
  ) {
    return report;
  }

  const basic = buildAccidentIncidentBasic(report, normalizedSourceData);
  const reportTitle = buildAccidentReportTitle(basic, report, normalizedSourceData);
  const section1 = buildAccidentSection1(report, normalizedSourceData);
  const section2 = buildAccidentSection2(report, normalizedSourceData);
  const section3 = buildAccidentSection3(report, normalizedSourceData);
  const section4 = buildAccidentSection4(report, normalizedSourceData);
  const triggerAnalysis = buildAccidentTriggerAnalysis(report, normalizedSourceData);
  const appendix = buildManagementReportAppendix(report, normalizedSourceData);

  return {
    report_type: 'accident_investigation_summary',
    template_version: '20260415',
    layout: buildAccidentLayout(reportTitle),
    report_title: reportTitle,
    basic,
    section_1: section1,
    section_2: section2,
    section_3: section3,
    section_4: section4,
    trigger_analysis: triggerAnalysis,
    appendix,
  };
}

export {
  readStringAtPath,
  hasStructuredReportTemplateMarkerNotation,
  hasDriverTemplateMarkerNotation,
  readNumberAtPath,
  readArrayAtPath,
  readRecordAtPath,
  trimNumberString,
  formatPercentValue,
  resolveDashboardTrendText,
  formatDateToCn,
  normalizeRiskLevelLabel,
  hasMeaningfulRiskLevelLabel,
  deriveRiskLevelLabel,
  simplifyIndicatorLabel,
  getStringArray,
  parseAlertCount,
  findMappedDashboardRow,
  findMappedAnalysisItem,
  listRecommendationCandidates,
  hasCompleteStructuredManagementReport,
  hasCompleteDriverManagementReport,
  readFirstNumberAtPaths,
  readFirstStringAtPaths,
  readFirstRecordAtPaths,
  readFirstArrayAtPaths,
  buildManagementRankInfo,
  buildManagementComparisonText,
  buildManagementReportDate,
  normalizeDriverManagementReport,
  normalizeVehicleManagementReport,
  normalizeUnitManagementReport,
  hasVehicleTemplateMarkerNotation,
  hasUnitTemplateMarkerNotation,
  hasCompleteVehicleManagementReport,
  hasCompleteUnitManagementReport,
  hasAccidentTemplateMarkerNotation,
  hasCompleteAccidentInvestigationReport,
  normalizeAccidentInvestigationReport,
};
