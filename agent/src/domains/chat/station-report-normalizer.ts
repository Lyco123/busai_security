import { isRecord } from '../../shared/guards';
import { getNestedValue } from '../../shared/object-path';
import {
  buildManagementReportDate,
  deriveRiskLevelLabel,
  readArrayAtPath,
  readFirstNumberAtPaths,
  readFirstStringAtPaths,
  readRecordAtPath,
  resolveDashboardTrendText,
  readStringAtPath,
} from './structured-report-normalizers';

const NO_MANAGEMENT_SUGGESTION_TEXT = '当前暂无管理建议';
const STATION_REPORT_TARGET_DIMENSIONS = ['综合风险', '交通安全', '三防安全', '消防安全'] as const;
const STATION_DETAIL_DIMENSIONS = ['交通安全', '三防安全', '消防安全'] as const;
const ANALYSIS_PREFIXES = ['风险最高的一级指标是', '其次是', '最后是'];
const RECOMMENDATION_PREFIXES = ['风险最高的基础指标是', '其次是', '再次是', '最后是'];

type StationReportTargetDimension = (typeof STATION_REPORT_TARGET_DIMENSIONS)[number];

function formatScore(value: number | null): string {
  return value == null || !Number.isFinite(value) ? '暂无数据' : `${value}`;
}

function getStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') return item.trim();
        if (isRecord(item)) {
          return String(item.name ?? item.indicator ?? item.quota_name ?? '').trim();
        }
        return '';
      })
      .filter((item) => item.length > 0);
  }
  if (typeof value === 'string' && value.trim()) return [value.trim()];
  return [];
}

function uniqueStrings(items: string[]): string[] {
  return items.filter((item, index) => item && items.indexOf(item) === index);
}

function resolveStationTrendText(
  sourceData: Record<string, unknown> | null,
  dimension: StationReportTargetDimension,
  source: Record<string, unknown> | null,
  existing: Record<string, unknown> | null
): string {
  return resolveDashboardTrendText({
    reportRow: existing,
    sourceDimension: source,
    sourceData,
    keys: [dimension],
    includeRouteComparison: false,
    allowOverallFallback: dimension === STATION_REPORT_TARGET_DIMENSIONS[0],
    defaultText: '同比—，环比—，同单位比—',
  });
}
function buildStationRankInfo(position: number | null, total: number | null): Record<string, unknown> {
  return {
    position,
    total,
    display:
      position != null && total != null
        ? `排名 ${position}/${total}`
        : position != null
          ? `当前排名第 ${position}`
          : '暂无排名数据',
  };
}

function buildStationComparisonText(percentile: number | null): Record<string, unknown> {
  if (percentile == null || !Number.isFinite(percentile)) {
    return { label: '当前缺少完整排名对比', verb: null };
  }
  return {
    label: percentile <= 50 ? '优于多数站场' : '差于多数站场',
    verb: percentile <= 50 ? '优于' : '差于',
  };
}

function getSourceDimension(
  sourceData: Record<string, unknown> | null,
  dimension: StationReportTargetDimension
): Record<string, unknown> | null {
  return readRecordAtPath(sourceData ?? {}, `performance_dashboard.dimensions.${dimension}`);
}

function buildStationDashboardRows(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Array<Record<string, unknown>> {
  return STATION_REPORT_TARGET_DIMENSIONS.map((dimension) =>
    buildStationDashboardRow(dimension, report, sourceData)
  );
}

function buildStationDashboardRow(
  dimension: StationReportTargetDimension,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const source = getSourceDimension(sourceData, dimension);
  const existingRows = readArrayAtPath(report, 'dashboard_rows') ?? [];
  const existing = existingRows
    .filter(isRecord)
    .find((row) => String(row.dimension ?? '').trim() === dimension);
  const score =
    readFirstNumberAtPaths(source ?? {}, ['score', 'risk_score']) ??
    readFirstNumberAtPaths(existing ?? {}, ['score', 'risk_score']);
  const riskLevel = deriveRiskLevelLabel(
    readFirstStringAtPaths(source ?? {}, ['risk_level', 'risk_label']) ??
      readFirstStringAtPaths(existing ?? {}, ['risk_level', 'risk_label']),
    score
  );
  const rankInfo = buildStationRankInfo(
    readFirstNumberAtPaths(source ?? {}, ['rank_position', 'rank', 'ranking']),
    readFirstNumberAtPaths(source ?? {}, ['rank_total', 'total', 'ranking_total'])
  );
  const comparison = buildStationComparisonText(readFirstNumberAtPaths(source ?? {}, ['percentile']));
  const indicators = uniqueStrings([
    ...getStringArray(getNestedValue(source ?? {}, 'core_risk_indicators')),
    ...getStringArray(getNestedValue(source ?? {}, 'top_indicator')),
    ...getStringArray(getNestedValue(existing ?? {}, 'core_risk_indicators')),
  ]);

  return {
    dimension,
    score: formatScore(score),
    risk_level: riskLevel,
    trend_text: resolveStationTrendText(sourceData, dimension, source, existing ?? null),
    rank_info: rankInfo,
    comparison,
    core_risk_indicators: indicators,
  };
}

function collectMajorRiskFactors(rows: Array<Record<string, unknown>>): string[] {
  return uniqueStrings(
    rows.flatMap((row) => getStringArray(getNestedValue(row, 'core_risk_indicators')))
  ).slice(0, 4);
}

function getOrderedDetailRows(rows: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
  return STATION_DETAIL_DIMENSIONS.map((dimension) =>
    rows.find((row) => String(row.dimension ?? '') === dimension)
  )
    .filter((row): row is Record<string, unknown> => Boolean(row))
    .sort((left, right) => {
      const leftScore = Number(left.score);
      const rightScore = Number(right.score);
      return (Number.isFinite(rightScore) ? rightScore : -Infinity) -
        (Number.isFinite(leftScore) ? leftScore : -Infinity);
    });
}

function buildStationManagementSummary(
  rows: Array<Record<string, unknown>>,
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  const stationName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.station_name', 'name', 'entity.display_name']) ??
    readFirstStringAtPaths(report, ['management_summary.station_name', 'basic.station_name']) ??
    '未知站场';
  const stationId =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.station_id', 'identifier', 'id']) ??
    readFirstStringAtPaths(report, ['management_summary.station_id', 'basic.station_id']) ??
    '';
  const organName =
    readFirstStringAtPaths(sourceData ?? {}, ['basic.organ_name']) ??
    readFirstStringAtPaths(report, ['management_summary.organ_name']) ??
    '';
  const overallRow = rows[0] ?? {};
  const overallScore = String(overallRow.score ?? '暂无数据');
  const riskLevel = String(overallRow.risk_level ?? '暂无数据');
  const reportDate = buildManagementReportDate(report, sourceData);
  const majorRiskFactors = collectMajorRiskFactors(rows);
  const factorText = majorRiskFactors.length ? majorRiskFactors.join('、') : '暂无突出基础指标';
  const summaryText = `${reportDate !== '—' ? `${reportDate}，` : ''}${stationName}站场被系统预判为${riskLevel}，综合风险值为${overallScore}分，主要风险因素为${factorText}，需结合多维绩效看板持续跟踪。`;

  return {
    station_name: stationName,
    station_id: stationId,
    organ_name: organName,
    report_date: reportDate,
    overall_score: overallScore,
    overall_risk_level: riskLevel,
    major_risk_factors: majorRiskFactors,
    summary_text: summaryText,
  };
}

function buildStationAnalysisItems(rows: Array<Record<string, unknown>>): string[] {
  return getOrderedDetailRows(rows)
    .map((row, index) => {
      const indicators = getStringArray(getNestedValue(row, 'core_risk_indicators'));
      if (!indicators.length) return null;
      const dimension = String(row.dimension ?? '站场风险');
      const riskLevel = String(row.risk_level ?? '暂无数据');
      const score = String(row.score ?? '暂无数据');
      const indicatorText = indicators
        .slice(0, 3)
        .map((indicator) => `${indicator}`)
        .join('、');
      const prefix = ANALYSIS_PREFIXES[index] ?? `第${index + 1}`;
      return `${prefix}${dimension}（一级指标），这是因为${indicatorText}需要重点关注，该维度风险得分为${score}分，当前处于${riskLevel}状态。`;
    })
    .filter((item): item is string => Boolean(item));
}

function buildStationRecommendations(
  rows: Array<Record<string, unknown>>,
  sourceData: Record<string, unknown> | null
): string[] {
  const sourceRecommendations = readArrayAtPath(sourceData ?? {}, 'interventions.recommendations');
  const suggestionByIndicator = new Map<string, string>();
  if (sourceRecommendations) {
    for (const item of sourceRecommendations) {
      if (!isRecord(item)) continue;
      const indicator = readFirstStringAtPaths(item, ['indicator', 'quota_name', 'dimension']);
      const action = readFirstStringAtPaths(item, ['action', 'suggestion', 'suggested_content', 'content']);
      if (indicator && action) suggestionByIndicator.set(indicator, action);
    }
  }

  const recommendations = collectMajorRiskFactors(rows)
    .slice(0, 4)
    .map((indicator, index) => {
      const prefix = RECOMMENDATION_PREFIXES[index] ?? '建议重点关注';
      const action =
        suggestionByIndicator.get(indicator) ??
        `建议建立${indicator}指标监测台账，数据超标时及时干预，避免风险扩散。`;
      return `${prefix}${indicator}，${action}`;
    })
    .filter((item) => item.trim().length > 0);
  if (recommendations.length > 0) return recommendations;
  return [`风险最高的基础指标是综合风险，${NO_MANAGEMENT_SUGGESTION_TEXT}`];
}

function buildStationCoreRiskAssessment(rows: Array<Record<string, unknown>>): Record<string, unknown> {
  const overallRow = rows[0] ?? {};
  const rankInfo = isRecord(overallRow.rank_info) ? overallRow.rank_info : {};
  const comparison = isRecord(overallRow.comparison) ? overallRow.comparison : {};
  const position = rankInfo.position;
  const total = rankInfo.total;
  const rankText =
    position != null && total != null
      ? `综合表现位于所属单位第${position}名（${position}/${total}）`
      : position != null
        ? `综合表现位于所属单位第${position}名`
        : '当前缺少完整排名数据';
  const comparisonLabel =
    typeof comparison.label === 'string' ? comparison.label : '当前缺少完整排名对比';
  return {
    summary: `综合近期运行数据判断，该站场综合风险值为${String(
      overallRow.score ?? '暂无数据'
    )}分，当前处于${String(overallRow.risk_level ?? '暂无数据')}状态，${rankText}，显示其${comparisonLabel}。`,
    key_dimensions: rows.map((row) => ({
      dimension: row.dimension,
      risk_level: row.risk_level,
      score: row.score,
      core_risk_indicators: row.core_risk_indicators,
    })),
  };
}

function buildStationAppendix(
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

function buildStationLayout(summary: string): Record<string, unknown> {
  return {
    title: '站场安全风险分析总结报告（管理人员版）',
    summary,
    sections: [
      {
        title: '一、多维绩效看板',
        blocks: [{ type: 'dashboard', rows_path: 'dashboard_rows' }],
      },
      {
        title: '二、核心风险研判',
        blocks: [{ type: 'text', text_path: 'core_risk_assessment.summary' }],
      },
      {
        title: '三、行为与数据关联分析',
        blocks: [{ type: 'list', items_path: 'behavior_data_analysis.analysis_items' }],
      },
      {
        title: '四、针对性干预建议',
        blocks: [{ type: 'list', items_path: 'interventions.recommendations' }],
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

export function normalizeStationManagementReport(
  report: Record<string, unknown>,
  sourceData: Record<string, unknown> | null
): Record<string, unknown> {
  if (readStringAtPath(report, 'error')) {
    return report;
  }

  const rows = buildStationDashboardRows(report, sourceData);
  const analysisItems = buildStationAnalysisItems(rows);
  const recommendations = buildStationRecommendations(rows, sourceData);
  const coreRiskAssessment = buildStationCoreRiskAssessment(rows);
  const managementSummary = buildStationManagementSummary(rows, report, sourceData);

  return {
    report_type: 'station_safety_summary_management',
    template_version: '20260305',
    report_role: 'management',
    layout: buildStationLayout(String(managementSummary.summary_text ?? '')),
    management_summary: managementSummary,
    dashboard_rows: rows,
    core_risk_assessment: coreRiskAssessment,
    behavior_data_analysis: { analysis_items: analysisItems },
    interventions: { recommendations },
    appendix: buildStationAppendix(report, sourceData),
  };
}

export function hasStationTemplateMarkerNotation(report: Record<string, unknown>): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  return hasCompleteStationManagementReport(report);
}

export function hasCompleteStationManagementReport(report: Record<string, unknown>): boolean {
  if (readStringAtPath(report, 'error')) {
    return true;
  }
  if (readStringAtPath(report, 'report_type') !== 'station_safety_summary_management') {
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
  if (!Array.isArray(rows) || rows.length !== STATION_REPORT_TARGET_DIMENSIONS.length) {
    return false;
  }
  const dimensions = rows
    .map((row) => (isRecord(row) && typeof row.dimension === 'string' ? row.dimension.trim() : ''))
    .filter((item) => item.length > 0);
  if (!STATION_REPORT_TARGET_DIMENSIONS.every((dimension) => dimensions.includes(dimension))) {
    return false;
  }

  const summaryText = readStringAtPath(report, 'management_summary.summary_text') ?? '';
  const coreSummary = readStringAtPath(report, 'core_risk_assessment.summary') ?? '';
  const recommendations = getNestedValue(report, 'interventions.recommendations');
  return Boolean(
    summaryText &&
      coreSummary &&
      Array.isArray(recommendations) &&
      recommendations.length > 0 &&
      recommendations.length <= 5
  );
}
