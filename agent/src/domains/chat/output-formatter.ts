import { isRecord } from '../../shared/guards';
import { getNestedValue } from '../../shared/object-path';

const STRUCTURED_REPORT_WORKER_TOOLS = new Set([
  'generate_driver_report',
  'generate_vehicle_report',
  'generate_unit_report',
  'generate_route_report',
  'generate_station_report',
  'generate_accident_investigation_report',
]);

export type OutputFormat = 'json' | 'markdown';

export interface OutputFormatterEnv {
  OUTPUT_FORMAT?: string;
}

export function parseOutputFormat(envValue: string | undefined): OutputFormat {
  const normalized = String(envValue ?? 'markdown')
    .trim()
    .toLowerCase();
  if (normalized === 'json') return 'json';
  return 'markdown';
}

export function isStructuredReportTool(toolName: unknown): boolean {
  return typeof toolName === 'string' && STRUCTURED_REPORT_WORKER_TOOLS.has(toolName);
}

export function formatStructuredOutput(
  content: string,
  metadata: Record<string, unknown> | undefined,
  env: OutputFormatterEnv
): string {
  const format = parseOutputFormat(env.OUTPUT_FORMAT);

  if (format === 'json') {
    return content;
  }

  const toolName = metadata?.tool;
  if (!isStructuredReportTool(toolName)) {
    return content;
  }

  const typedToolName = toolName as string;

  try {
    const parsed = JSON.parse(content);
    if (!isRecord(parsed)) {
      return content;
    }

    if (typeof parsed.error === 'string') {
      return formatErrorReport(parsed);
    }

    return convertReportToMarkdown(parsed, typedToolName);
  } catch {
    return content;
  }
}

function formatErrorReport(report: Record<string, unknown>): string {
  const error = typeof report.error === 'string' ? report.error : 'unknown_error';
  const message = typeof report.message === 'string' ? report.message : '生成报告时发生错误';
  return `**错误：${error}**\n\n${message}`;
}

function convertReportToMarkdown(report: Record<string, unknown>, toolName: string): string {
  const layout = getNestedValue(report, 'layout');
  const lines: string[] = [];

  if (!isRecord(layout)) {
    return renderFallbackMarkdown(report, toolName);
  }

  const title = typeof layout.title === 'string' ? layout.title : '结构化报告';
  lines.push(`## ${title}`);
  lines.push('');

  const summary = typeof layout.summary === 'string' ? layout.summary : '';
  if (summary) {
    lines.push(cleanMarkerNotation(summary));
    lines.push('');
  }

  const header = layout.header;
  if (isRecord(header) && Array.isArray(header.items)) {
    const headerItems = header.items
      .map((item) => {
        if (!isRecord(item)) return null;
        const label = typeof item.label === 'string' ? item.label : '';
        const valuePath = typeof item.value_path === 'string' ? item.value_path : '';
        const value = valuePath ? readDisplayValue(report, valuePath) : '';
        const highlight = item.highlight === true;
        if (!label || !value) return null;
        return highlight ? `**${label}**：**${value}**` : `**${label}**：${value}`;
      })
      .filter((item): item is string => item !== null);

    if (headerItems.length > 0) {
      lines.push(headerItems.join(' | '));
      lines.push('');
    }
  }

  const sections = layout.sections;
  if (Array.isArray(sections)) {
    for (const section of sections) {
      if (!isRecord(section)) continue;
      const sectionTitle = typeof section.title === 'string' ? section.title : '';
      if (!sectionTitle) continue;

      const collapsible = section.collapsible === true;
      if (collapsible) {
        lines.push(`<details>`);
        lines.push(`<summary>${sectionTitle}</summary>`);
        lines.push('');
      } else {
        lines.push(`### ${sectionTitle}`);
        lines.push('');
      }

      const blocks = section.blocks;
      if (Array.isArray(blocks)) {
          for (const block of blocks) {
            renderBlock(lines, block, report, toolName);
          }
      }

      if (collapsible) {
        lines.push('');
        lines.push(`</details>`);
        lines.push('');
      } else {
        lines.push('');
      }
    }
  }

  return lines.join('\n').trim();
}

function renderBlock(
  lines: string[],
  block: unknown,
  report: Record<string, unknown>,
  toolName?: string
): void {
  if (!isRecord(block)) return;

  const blockType = typeof block.type === 'string' ? block.type : '';

  if (blockType === 'text') {
    const textPath = typeof block.text_path === 'string' ? block.text_path : '';
    if (textPath) {
      const text = readDisplayValue(report, textPath);
      if (text) {
        lines.push(cleanMarkerNotation(text));
        lines.push('');
      }
    }
    return;
  }

  if (blockType === 'table') {
    const rowsPath = typeof block.rows_path === 'string' ? block.rows_path : '';
    const columns = Array.isArray(block.columns) ? block.columns : [];

    if (!rowsPath || columns.length === 0) return;

    const rows = getNestedValue(report, rowsPath);
    if (!Array.isArray(rows) || rows.length === 0) return;

    const columnKeys = columns
      .map((col) => {
        if (!isRecord(col)) return null;
        return typeof col.key === 'string' ? col.key : null;
      })
      .filter((key): key is string => key !== null);

    const columnTitles = columns
      .map((col) => {
        if (!isRecord(col)) return '';
        return typeof col.title === 'string' ? col.title : '';
      })
      .filter((title) => title.length > 0);

    if (columnKeys.length === 0 || columnTitles.length === 0) return;

    lines.push(`| ${columnTitles.join(' | ')} |`);
    lines.push(`| ${columnTitles.map(() => '---').join(' | ')} |`);

    for (const row of rows) {
      if (!isRecord(row)) continue;
      const rowValues = columnKeys.map((key) => {
        const value = row[key];
        return formatTableCell(value);
      });
      lines.push(`| ${rowValues.join(' | ')} |`);
    }
    lines.push('');
    return;
  }

  if (blockType === 'dashboard') {
    const rowsPath = typeof block.rows_path === 'string' ? block.rows_path : 'dashboard_rows';
    const rows = getNestedValue(report, rowsPath);
    if (!Array.isArray(rows) || rows.length === 0) return;

    lines.push('| 核心维度 | 风险得分 | 趋势表现 | 核心风险指标 |');
    lines.push('| --- | --- | --- | --- |');
    for (const row of rows) {
      if (!isRecord(row)) continue;
      lines.push(
        `| ${formatTableCell(row.dimension)} | ${formatTableCell(row.score)} | ${formatTableCell(
          row.trend_text
        )} | ${formatTableCell(row.core_risk_indicators)} |`
      );
    }
    lines.push('');
    return;
  }

  if (blockType === 'list') {
    const itemsPath = typeof block.items_path === 'string' ? block.items_path : '';
    const ordered = block.ordered === true;

    if (!itemsPath) return;

    if (toolName === 'generate_vehicle_report' && itemsPath === 'interventions.recommendations') {
      const sourceLines = extractVehicleRawSuggestionLines(report);
      if (sourceLines.length > 0) {
        for (const line of sourceLines) {
          lines.push(`- ${cleanMarkerNotation(line)}`);
        }
        lines.push('');
        return;
      }
    }

    const items = getNestedValue(report, itemsPath);
    if (!Array.isArray(items) || items.length === 0) return;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const prefix = ordered ? `${i + 1}. ` : '- ';

      if (typeof item === 'string') {
        lines.push(`${prefix}${cleanMarkerNotation(item)}`);
      } else if (isRecord(item)) {
        const suggestion = typeof item.suggestion === 'string' ? item.suggestion : '';
        const insight = typeof item.insight === 'string' ? item.insight : '';
        const text = suggestion || insight || formatItemSummary(item);
        if (text) {
          lines.push(`${prefix}${cleanMarkerNotation(text)}`);
        }
      }
    }
    lines.push('');
    return;
  }

  if (blockType === 'json') {
    const dataPath = typeof block.data_path === 'string' ? block.data_path : '';
    const blockTitle = typeof block.title === 'string' ? block.title : '数据';

    if (!dataPath) return;

    const data = getNestedValue(report, dataPath);
    if (data == null) return;

    lines.push(`**${blockTitle}**`);
    lines.push('');
    lines.push('```json');
    lines.push(JSON.stringify(data, null, 2));
    lines.push('```');
    lines.push('');
    return;
  }
}

function formatTableCell(value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '—';
    return value
      .toFixed(2)
      .replace(/\.00$/, '')
      .replace(/(\.\d)0$/, '$1');
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed || trimmed === 'null' || trimmed === 'undefined') return '—';
    return cleanMarkerNotation(trimmed);
  }
  if (Array.isArray(value)) {
    const items = value.map((item) => formatTableCell(item)).filter((item) => item !== '—');
    return items.length > 0 ? items.join(', ') : '—';
  }
  if (isRecord(value)) {
    if (typeof value.display === 'string') return cleanMarkerNotation(value.display);
    return '—';
  }
  return String(value);
}

function formatItemSummary(item: Record<string, unknown>): string {
  const parts: string[] = [];

  const dimension = typeof item.dimension === 'string' ? item.dimension : '';
  const rankLabel = typeof item.rank_label === 'string' ? item.rank_label : '';
  const topIndicator = typeof item.top_indicator === 'string' ? item.top_indicator : '';
  const alertCount = item.alert_count;
  const indicatorScore = item.indicator_score;
  const priority = item.priority;
  const indicator = typeof item.indicator === 'string' ? item.indicator : '';

  if (rankLabel && dimension) {
    parts.push(`${rankLabel} ${dimension}`);
  }
  if (topIndicator) {
    parts.push(`指标：${topIndicator}`);
  }
  if (indicatorScore != null) {
    parts.push(`指标分：${formatTableCell(indicatorScore)}`);
  } else if (alertCount != null) {
    parts.push(`指标分：${formatTableCell(alertCount)}`);
  }
  if (priority != null) {
    parts.push(`优先级 ${priority}`);
  }
  if (indicator) {
    parts.push(`指标：${indicator}`);
  }

  return parts.length > 0 ? parts.join('；') : '';
}

function readDisplayValue(report: Record<string, unknown>, path: string): string {
  const value = getNestedValue(report, path);
  if (value == null) return '';
  if (typeof value === 'string') return cleanMarkerNotation(value.trim());
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (Array.isArray(value)) {
    return value.map((v) => String(v)).join(', ');
  }
  if (isRecord(value)) {
    if (typeof value.display === 'string') return cleanMarkerNotation(value.display);
  }
  return '';
}

function cleanMarkerNotation(text: string): string {
  return text.replace(/\{([^{}]+)\}/g, '$1').replace(/【([^【】]+)】/g, '$1');
}

function renderFallbackMarkdown(report: Record<string, unknown>, toolName: string): string {
  const lines: string[] = [];

  const reportType = typeof report.report_type === 'string' ? report.report_type : toolName;
  lines.push(`## ${reportType}`);
  lines.push('');

  const managementSummary = report.management_summary;
  if (isRecord(managementSummary)) {
    const driverName =
      typeof managementSummary.driver_name === 'string' ? managementSummary.driver_name : '';
    const driverId =
      typeof managementSummary.driver_id === 'string' ? managementSummary.driver_id : '';
    const riskLevel =
      typeof managementSummary.risk_level === 'string' ? managementSummary.risk_level : '';

    if (driverName) lines.push(`**驾驶员**：${driverName}`);
    if (driverId) lines.push(`**工号**：${driverId}`);
    if (riskLevel) lines.push(`**风险状态**：**${riskLevel}**`);
    lines.push('');

    const summaryText =
      typeof managementSummary.summary_text === 'string' ? managementSummary.summary_text : '';
    if (summaryText) {
      lines.push(cleanMarkerNotation(summaryText));
      lines.push('');
    }
  }

  const dashboardRows = report.dashboard_rows;
  if (Array.isArray(dashboardRows) && dashboardRows.length > 0) {
    lines.push(`### 多维绩效看板`);
    lines.push('');
    lines.push('| 核心维度 | 风险得分 | 趋势表现 | 核心风险指标 |');
    lines.push('| --- | --- | --- | --- |');
    for (const row of dashboardRows) {
      if (!isRecord(row)) continue;
      const dimension = formatTableCell(row.dimension);
      const score = formatTableCell(row.score);
      const trend = formatTableCell(row.trend_text);
      const indicators = formatTableCell(row.core_risk_indicators);
      lines.push(`| ${dimension} | ${score} | ${trend} | ${indicators} |`);
    }
    lines.push('');
  }

  const coreRiskAssessment = report.core_risk_assessment;
  if (isRecord(coreRiskAssessment)) {
    const summary =
      typeof coreRiskAssessment.summary === 'string' ? coreRiskAssessment.summary : '';
    if (summary) {
      lines.push(`### 核心风险研判`);
      lines.push('');
      lines.push(cleanMarkerNotation(summary));
      lines.push('');
    }
  }

  const analysisItems = getNestedValue(report, 'behavior_data_analysis.analysis_items');
  if (Array.isArray(analysisItems) && analysisItems.length > 0) {
    lines.push(`### 行为与数据关联分析`);
    lines.push('');
    for (let i = 0; i < analysisItems.length; i++) {
      const item = analysisItems[i];
      if (typeof item === 'string') {
        lines.push(`${i + 1}. ${cleanMarkerNotation(item)}`);
      } else if (isRecord(item)) {
        const insight = typeof item.insight === 'string' ? item.insight : '';
        if (insight) {
          lines.push(`${i + 1}. ${cleanMarkerNotation(insight)}`);
        }
      }
    }
    lines.push('');
  }

  const recommendationLines = buildRenderedRecommendationLines(report, toolName);
  if (recommendationLines.length > 0) {
    lines.push(`### \u9488\u5bf9\u6027\u5e72\u9884\u5efa\u8bae`);
    lines.push('');
    for (let i = 0; i < recommendationLines.length; i++) {
      lines.push(`${i + 1}. ${cleanMarkerNotation(recommendationLines[i])}`);
    }
    lines.push('');
  }

  return lines.join('\n').trim();
}

function buildRenderedRecommendationLines(report: Record<string, unknown>, toolName: string): string[] {
  const structuredLines = extractStructuredRecommendationLines(report);
  if (toolName !== 'generate_vehicle_report') {
    return structuredLines;
  }

  const sourceLines = extractVehicleRawSuggestionLines(report);
  if (sourceLines.length > 0) {
    return sourceLines;
  }

  if (structuredLines.some((item) => !looksLikePlaceholderRecommendation(item))) {
    return structuredLines;
  }

  return ['\u6682\u65e0\u5efa\u8bae'];
}

function extractStructuredRecommendationLines(report: Record<string, unknown>): string[] {
  const recommendations = getNestedValue(report, 'interventions.recommendations');
  if (!Array.isArray(recommendations)) return [];

  const lines: string[] = [];
  for (const item of recommendations) {
    if (typeof item === 'string' && item.trim()) {
      lines.push(item.trim());
      continue;
    }
    if (!isRecord(item)) continue;
    const suggestion = typeof item.suggestion === 'string' ? item.suggestion.trim() : '';
    if (suggestion) {
      lines.push(suggestion);
    }
  }
  return lines;
}

function extractVehicleRawSuggestionLines(report: Record<string, unknown>): string[] {
  const rawSuggestions = getNestedValue(report, 'appendix.raw_data.suggestions');
  if (!Array.isArray(rawSuggestions)) return [];

  const prefixes = [
    '\u98ce\u9669\u6700\u9ad8\u7684\u57fa\u7840\u6307\u6807\u662f',
    '\u5176\u6b21\u662f',
    '\u518d\u6b21\u662f',
    '\u6700\u540e\u662f',
  ];
  const lines: string[] = [];
  for (let i = 0; i < rawSuggestions.length && lines.length < 4; i += 1) {
    const item = rawSuggestions[i];
    if (!isRecord(item)) continue;
    const quotaName = typeof item.quota_name === 'string' ? item.quota_name.trim() : '';
    const suggestedContent = typeof item.suggested_content === 'string' ? item.suggested_content.trim() : '';
    if (!quotaName || !suggestedContent) continue;
    lines.push(`${prefixes[lines.length] ?? '\u5efa\u8bae\u5173\u6ce8'}${quotaName}\uff0c${suggestedContent}`);
  }
  return lines;
}

function looksLikePlaceholderRecommendation(text: string): boolean {
  const normalized = text.trim();
  if (!normalized) return true;
  return normalized.includes('?') || normalized.includes('\u6682\u65e0') || normalized.includes('\u672a\u63d0\u4f9b') || normalized.includes('\u5f85\u8865\u5145') || normalized.includes('{-}') || normalized.includes('{?}');
}
