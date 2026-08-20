import type {
  StructuredManagementReportRuntimeConfig,
  StructuredManagementReportWorkerToolName,
  StructuredReportWorkerToolName,
  WorkerToolName,
} from './worker-runner';
import {
  hasCompleteAccidentInvestigationReport,
  hasAccidentTemplateMarkerNotation,
  normalizeAccidentInvestigationReport,
} from './structured-report-normalizers';
import {
  hasCompleteDriverManagementReport,
  hasDriverTemplateMarkerNotation,
  normalizeDriverManagementReport,
} from './driver-report-normalizer';
import {
  hasCompleteVehicleManagementReport,
  hasVehicleTemplateMarkerNotation,
  normalizeVehicleManagementReport,
} from './vehicle-report-normalizer';
import {
  hasCompleteUnitManagementReport,
  hasUnitTemplateMarkerNotation,
  normalizeUnitManagementReport,
} from './unit-report-normalizer';
import {
  hasCompleteRouteManagementReport,
  hasRouteTemplateMarkerNotation,
  normalizeRouteManagementReport,
} from './route-report-normalizer';
import {
  hasCompleteStationManagementReport,
  hasStationTemplateMarkerNotation,
  normalizeStationManagementReport,
} from './station-report-normalizer';
import { getStructuredReportDataSourceConfig } from './structured-report-data-sources';
import { collapseWhitespace } from '../../shared/text';
import { getNestedValue } from '../../shared/object-path';

function isStructuredManagementReportWorkerToolName(
  value: WorkerToolName
): value is StructuredManagementReportWorkerToolName {
  return (
    value === 'generate_driver_report' ||
    value === 'generate_vehicle_report' ||
    value === 'generate_unit_report' ||
    value === 'generate_route_report' ||
    value === 'generate_station_report' ||
    value === 'generate_accident_investigation_report'
  );
}

function isStructuredReportWorkerToolName(
  value: WorkerToolName
): value is StructuredReportWorkerToolName {
  return (
    value === 'generate_driver_report' ||
    value === 'generate_vehicle_report' ||
    value === 'generate_unit_report' ||
    value === 'generate_route_report' ||
    value === 'generate_station_report' ||
    value === 'generate_accident_investigation_report'
  );
}

function cleanExtractedEntityToken(value: string): string {
  return value
    .trim()
    .replace(/^[“"'`‘’「『（(【\[]+/, '')
    .replace(/[”"'`’」』）)】\].,，。！？!?:：；;]+$/g, '')
    .replace(/的$/u, '')
    .trim();
}

function normalizeRouteLookupToken(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[“”"'`]/g, '')
    .replace(/[（）()【】\[\]<>《》]/g, '')
    .replace(/\s+/g, '')
    .replace(/路$/u, '');
}

function extractRequestedRouteNameFromWorkerPrompt(prompt: string): string | null {
  const match = prompt.match(/请生成线路[「“"](.+?)[」”"]/);
  const candidate = cleanExtractedEntityToken(match?.[1] ?? '');
  return candidate || null;
}

function isRequestedRoutePayloadMatch(
  requestedRouteName: string | null,
  payload: Record<string, unknown>
): boolean {
  if (!requestedRouteName) return true;
  const requested = normalizeRouteLookupToken(requestedRouteName);
  if (!requested) return true;
  const candidates = [
    payload.name,
    payload.identifier,
    getNestedValue(payload, 'basic.route_name'),
    getNestedValue(payload, 'basic.route_id'),
    getNestedValue(payload, 'route_name'),
    getNestedValue(payload, 'route_id'),
    getNestedValue(payload, 'id'),
  ]
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => normalizeRouteLookupToken(item));
  return candidates.some(
    (item) => item === requested || item.includes(requested) || requested.includes(item)
  );
}

function normalizeUnitLookupToken(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/[“”"'`]/g, '')
    .replace(/[（）()【】\[\]<>《》]/g, '')
    .replace(/\s+/g, '');
}

function hasHyphenNumberFleetSuffix(value: string): boolean {
  return /-\s*(?:\d+|[一二三四五六七八九十]+)\s*车队/u.test(value.normalize('NFKC'));
}

function extractRequestedUnitNameFromWorkerPrompt(prompt: string): string | null {
  const quoted = prompt.match(/请生成单位[「“"](.+?)[」”"]/);
  const prefetched = prompt.match(/Generate the unit safety report for (.+?) using only/u);
  const candidate = cleanExtractedEntityToken(quoted?.[1] ?? prefetched?.[1] ?? '');
  return candidate || null;
}

function isRequestedUnitPayloadMatch(
  requestedUnitName: string | null,
  payload: Record<string, unknown>
): boolean {
  if (!requestedUnitName) return true;
  const requested = normalizeUnitLookupToken(requestedUnitName);
  if (!requested) return true;
  const requiresExactFleet = hasHyphenNumberFleetSuffix(requestedUnitName);
  const candidates = [
    payload.name,
    payload.identifier,
    getNestedValue(payload, 'basic.organ_name'),
    getNestedValue(payload, 'basic.organ_id'),
    getNestedValue(payload, 'organ_name'),
    getNestedValue(payload, 'organ_id'),
    getNestedValue(payload, 'id'),
  ]
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => normalizeUnitLookupToken(item));

  if (requiresExactFleet) {
    return candidates.some((item) => item === requested || item.includes(requested));
  }
  return candidates.some(
    (item) => item === requested || item.includes(requested) || requested.includes(item)
  );
}

const STRUCTURED_MANAGEMENT_REPORT_RUNTIME_CONFIGS: Record<
  StructuredManagementReportWorkerToolName,
  StructuredManagementReportRuntimeConfig
> = {
  generate_driver_report: {
    reportType: 'driver_safety_summary_management',
    noDataError: {
      error: 'driver_not_found',
      message: '未找到该驾驶员，请确认姓名或工号后重试',
    },
    formatMismatchError: 'driver_report_format_mismatch',
    missingDataRetryLimit: 2,
    maxDataToolCallsWithoutHit: null,
    normalizeReport: normalizeDriverManagementReport,
    hasCompleteReport: hasCompleteDriverManagementReport,
    hasTemplateMarkerNotation: hasDriverTemplateMarkerNotation,
  },
  generate_vehicle_report: {
    reportType: 'vehicle_safety_summary_management',
    noDataError: {
      error: 'vehicle_not_found',
      message: '未找到该车辆画像数据，请确认车牌号后重试',
    },
    formatMismatchError: 'vehicle_report_format_mismatch',
    missingDataRetryLimit: 2,
    maxDataToolCallsWithoutHit: null,
    normalizeReport: normalizeVehicleManagementReport,
    hasCompleteReport: hasCompleteVehicleManagementReport,
    hasTemplateMarkerNotation: hasVehicleTemplateMarkerNotation,
  },
  generate_unit_report: {
    reportType: 'unit_safety_summary_management',
    noDataError: {
      error: 'unit_not_found',
      message: '未找到该单位画像数据，请确认单位名称后重试',
    },
    formatMismatchError: 'unit_report_format_mismatch',
    missingDataRetryLimit: 2,
    maxDataToolCallsWithoutHit: null,
    normalizeReport: normalizeUnitManagementReport,
    hasCompleteReport: hasCompleteUnitManagementReport,
    hasTemplateMarkerNotation: hasUnitTemplateMarkerNotation,
    extractRequestedEntityToken: extractRequestedUnitNameFromWorkerPrompt,
    doesGetPayloadMatchRequestedEntity: isRequestedUnitPayloadMatch,
  },
  generate_route_report: {
    reportType: 'route_safety_summary_management',
    noDataError: {
      error: 'route_not_found',
      message: '未找到该线路，请确认线路名称或线路编号后重试',
    },
    formatMismatchError: 'route_report_format_mismatch',
    missingDataRetryLimit: 2,
    maxDataToolCallsWithoutHit: 4,
    normalizeReport: normalizeRouteManagementReport,
    hasCompleteReport: hasCompleteRouteManagementReport,
    hasTemplateMarkerNotation: hasRouteTemplateMarkerNotation,
    extractRequestedEntityToken: extractRequestedRouteNameFromWorkerPrompt,
    doesGetPayloadMatchRequestedEntity: isRequestedRoutePayloadMatch,
  },
  generate_station_report: {
    reportType: 'station_safety_summary_management',
    noDataError: {
      error: 'station_not_found',
      message: '未找到该站场画像数据，请确认站场名称后重试',
    },
    formatMismatchError: 'station_report_format_mismatch',
    missingDataRetryLimit: 2,
    maxDataToolCallsWithoutHit: 4,
    normalizeReport: normalizeStationManagementReport,
    hasCompleteReport: hasCompleteStationManagementReport,
    hasTemplateMarkerNotation: hasStationTemplateMarkerNotation,
  },
  generate_accident_investigation_report: {
    reportType: 'accident_investigation_summary',
    noDataError: {
      error: 'incident_not_found',
      message: '未找到该事故记录，请确认事故编号或关键信息后重试',
    },
    formatMismatchError: 'accident_report_format_mismatch',
    missingDataRetryLimit: 2,
    maxDataToolCallsWithoutHit: 4,
    normalizeReport: normalizeAccidentInvestigationReport,
    hasCompleteReport: hasCompleteAccidentInvestigationReport,
    hasTemplateMarkerNotation: hasAccidentTemplateMarkerNotation,
  },
};

export function getStructuredManagementReportRuntimeConfig(
  workerTool: WorkerToolName
): StructuredManagementReportRuntimeConfig | null {
  return isStructuredManagementReportWorkerToolName(workerTool)
    ? (STRUCTURED_MANAGEMENT_REPORT_RUNTIME_CONFIGS[workerTool] ?? null)
    : null;
}

export function buildStructuredReportNoDataError(workerTool: WorkerToolName): string {
  const config = getStructuredManagementReportRuntimeConfig(workerTool);
  if (config) {
    return JSON.stringify(config.noDataError, null, 2);
  }
  return JSON.stringify(
    {
      error: 'source_data_not_found',
      message: '未查询到可用原始数据，无法生成结构化报告',
    },
    null,
    2
  );
}

export function buildStructuredReportFormatMismatchError(workerTool: WorkerToolName): string {
  const config = getStructuredManagementReportRuntimeConfig(workerTool);
  return JSON.stringify(
    {
      error: config?.formatMismatchError ?? 'structured_report_format_mismatch',
      message: '输出未按模板要求生成，请在前端手动重试',
    },
    null,
    2
  );
}

export function buildStructuredReportMissingDataPrompt(
  workerTool: WorkerToolName,
  mode: 'missing_read_call' | 'read_failed' | 'no_data_hit' | 'missing_get_hit'
): string {
  const dataSourceConfig = isStructuredReportWorkerToolName(workerTool)
    ? getStructuredReportDataSourceConfig(workerTool)
    : null;
  if (dataSourceConfig?.buildMissingDataPrompt) {
    return dataSourceConfig.buildMissingDataPrompt(mode);
  }
  if (mode === 'missing_read_call') {
    return '你尚未调用当前轮可用的数据工具。必须先获取真实数据后，再输出结构化 JSON 报告。禁止输出“暂无/建议事项”等占位内容。';
  }
  if (mode === 'read_failed') {
    return '你调用了数据工具，但读取未成功。请修正参数并重新查询，直到成功获取真实数据后再输出结构化 JSON。';
  }
  if (mode === 'missing_get_hit') {
    return '你尚未命中目标实体详情。请确认标识信息并重新获取完整数据，然后再输出报告。';
  }
  return '数据工具已成功调用，但未命中有效业务数据。请确认标识信息后重试；若仍无数据则直接返回 error JSON（不要输出占位报告）。';
}

function isStructuredReportRegenerationRequest(content: string): boolean {
  const normalized = collapseWhitespace(content);
  if (!normalized) return false;
  return (
    /(重新|重(?:新)?|再次|再)\s*(生成|出具|做|整理)?\s*(一份)?\s*(报告|画像|总结|分析)/.test(
      normalized
    ) ||
    /(生成|出具)\s*(一份)?\s*(新的|最新的)?\s*(报告|画像|总结|分析)/.test(normalized) ||
    /(报告|画像|总结|分析).{0,6}(重新|重(?:新)?|再次|再)(生成|出具|做|整理)/.test(normalized)
  );
}

export function isStructuredReportFollowUpQuery(content: string): boolean {
  const normalized = collapseWhitespace(content);
  if (!normalized) return false;
  if (isStructuredReportRegenerationRequest(normalized)) return false;

  const explicitFollowUpPattern =
    /(展开说说|展开一下|详细说说|具体说说|详细解释|具体解释|解释一下|说明一下|分析一下|讲讲|说说|为什么|为何|原因|依据|怎么看|怎么判断|哪里体现|什么意思|啥意思|怎么理解)/;
  if (explicitFollowUpPattern.test(normalized)) {
    return true;
  }

  const reportReferencePattern = /(这份|这个|上面|刚才|前面|报告里|报告中|里面|其中)/;
  const reportTopicPattern = /(指标|风险|建议|结论|趋势|原因|依据|明细)/;
  if (reportReferencePattern.test(normalized) && reportTopicPattern.test(normalized)) {
    return true;
  }

  const dimensionPattern =
    /(综合风险|故障风险|能耗风险|行为风险|安全风险|风险最高|最高风险|最低风险|指标)/;
  const questionPattern = /[?？]|(为什么|解释|说明|展开|详细|具体|原因|依据|怎么|如何)/;
  return dimensionPattern.test(normalized) && questionPattern.test(normalized);
}

export function buildStructuredReportFollowUpPrompt(
  sourceTool: StructuredReportWorkerToolName,
  userQuery: string
): string {
  const labelMap: Record<StructuredReportWorkerToolName, string> = {
    generate_driver_report: '驾驶员报告',
    generate_vehicle_report: '车辆报告',
    generate_unit_report: '单位报告',
    generate_route_report: '线路报告',
    generate_station_report: '站场报告',
    generate_accident_investigation_report: '事故调查报告',
  };
  const reportLabel = labelMap[sourceTool];
  return [
    `以下问题是基于上一轮${reportLabel}的详情追问。`,
    '请直接基于当前对话上下文做解释、展开或补充说明，不要重新生成整份结构化报告，不要输出整段 JSON。',
    '如果上下文里没有足够依据，直接明确说明，不要臆造新数据。',
    '如果用户问题里的排名、分值、指标归属或结论前提与上下文中的报告不一致，先明确纠正，再给出解释。',
    '不要顺着用户的错误前提继续展开；例如报告里静态风险并非第二，就必须先指出真实排名。',
    `用户问题：${userQuery.trim()}`,
  ].join('\n');
}
