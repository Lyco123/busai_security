import { getDefaultDriverProfilePartition } from '../../shared/driver-profile-mcp';
import { getDefaultRouteProfilePartition } from '../../shared/route-profile-mcp';
import { STATION_PROFILE_TOOL_NAME } from '../../shared/station-profile-mcp';
import { extractVehicleProfilePartitionFromText } from '../../shared/vehicle-profile-mcp';
import { isRecord } from '../../shared/guards';

export type StructuredReportDataSourceToolName =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_unit_report'
  | 'generate_route_report'
  | 'generate_station_report'
  | 'generate_accident_investigation_report';

export interface StructuredReportDataSourceConfig {
  mode: 'external_tool';
  toolAllowList?: string[];
  buildUnresolvedPrompt?: (entityToken: string, partition?: string | null) => string;
  buildResolvedPrompt?: (resolved: {
    displayName: string;
    entityId?: string | null;
    partition?: string | null;
  }) => string;
  buildPromptSourceData?: (sourceData: Record<string, unknown>) => Record<string, unknown>;
  buildResolvedPrefetchedPrompt?: (resolved: {
    displayName: string;
    entityId?: string | null;
    partition?: string | null;
    sourceData: Record<string, unknown>;
  }) => string;
  buildMissingDataPrompt?: (
    mode: 'missing_read_call' | 'read_failed' | 'no_data_hit' | 'missing_get_hit'
  ) => string;
}

export const DRIVER_PROFILE_MCP_TOOL_NAME = 'get_mcp_base_absDriverProfileMain_queryDriverProfile';
export const ROUTE_PROFILE_MCP_TOOL_NAME = 'get_mcp_base_absRouteProfileMain_queryRouteProfile';
export const STATION_PROFILE_MCP_TOOL_NAME = STATION_PROFILE_TOOL_NAME;
export const UNIT_PROFILE_MCP_TOOL_NAME = 'get_mcp_base_absCompanyProfileMain_queryCompanyProfile';
export const VEHICLE_PROFILE_MCP_TOOL_NAME = 'get_mcp_base_absBusProfileMain_queryByNumberplate';

export const DRIVER_REPORT_SOURCE_TOOL_NAME = 'get_driver_report_source';
export const VEHICLE_REPORT_SOURCE_TOOL_NAME = 'get_vehicle_report_source';
export const UNIT_REPORT_SOURCE_TOOL_NAME = 'get_unit_report_source';
export const ROUTE_REPORT_SOURCE_TOOL_NAME = 'get_route_report_source';
export const STATION_REPORT_SOURCE_TOOL_NAME = 'get_station_report_source';
export const ACCIDENT_REPORT_SOURCE_TOOL_NAME = 'get_accident_report_source';

export type ReportSourceToolName =
  | typeof DRIVER_REPORT_SOURCE_TOOL_NAME
  | typeof VEHICLE_REPORT_SOURCE_TOOL_NAME
  | typeof UNIT_REPORT_SOURCE_TOOL_NAME
  | typeof ROUTE_REPORT_SOURCE_TOOL_NAME
  | typeof STATION_REPORT_SOURCE_TOOL_NAME
  | typeof ACCIDENT_REPORT_SOURCE_TOOL_NAME;

export type ReportSourceToolDefinition = {
  name: ReportSourceToolName;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
};

export const REPORT_SOURCE_TOOL_DEFINITIONS: Record<
  ReportSourceToolName,
  ReportSourceToolDefinition
> = {
  [DRIVER_REPORT_SOURCE_TOOL_NAME]: {
    name: DRIVER_REPORT_SOURCE_TOOL_NAME,
    description:
      '获取驾驶员报告专用数据源。该工具会调用驾驶员画像相关 MCP 并返回报告生成可用的包装结构；普通咨询不要使用该包装结构替代原始 MCP 返回。',
    parameters: {
      type: 'object',
      properties: {
        driverName: { type: 'string', description: '驾驶员姓名。' },
        driver_name: { type: 'string', description: '驾驶员姓名，兼容字段。' },
        ppartition: { type: 'string', description: '画像日期分区，可选，格式 yyyyMMdd。' },
        partition: { type: 'string', description: '画像日期分区，兼容字段。' },
      },
    },
  },
  [VEHICLE_REPORT_SOURCE_TOOL_NAME]: {
    name: VEHICLE_REPORT_SOURCE_TOOL_NAME,
    description:
      '获取车辆报告专用数据源。该工具会调用车辆画像相关 MCP 并返回报告生成可用的包装结构；普通咨询不要使用该包装结构替代原始 MCP 返回。',
    parameters: {
      type: 'object',
      properties: {
        numberPlate: { type: 'string', description: '车牌号。' },
        number_plate: { type: 'string', description: '车牌号，兼容字段。' },
        ppartition: { type: 'string', description: '画像日期分区，可选，格式 yyyyMMdd。' },
        partition: { type: 'string', description: '画像日期分区，兼容字段。' },
      },
    },
  },
  [UNIT_REPORT_SOURCE_TOOL_NAME]: {
    name: UNIT_REPORT_SOURCE_TOOL_NAME,
    description:
      '获取单位报告专用数据源。该工具会调用单位画像相关 MCP 并返回报告生成可用的包装结构。',
    parameters: {
      type: 'object',
      properties: {
        organName: { type: 'string', description: '单位名称。' },
        organ_name: { type: 'string', description: '单位名称，兼容字段。' },
        ppartition: { type: 'string', description: '画像日期分区，可选，格式 yyyyMMdd。' },
        partition: { type: 'string', description: '画像日期分区，兼容字段。' },
      },
    },
  },
  [ROUTE_REPORT_SOURCE_TOOL_NAME]: {
    name: ROUTE_REPORT_SOURCE_TOOL_NAME,
    description:
      '获取线路报告专用数据源。该工具会调用线路画像相关 MCP 并返回报告生成可用的包装结构。',
    parameters: {
      type: 'object',
      properties: {
        routeName: { type: 'string', description: '线路名称或线路编号。' },
        route_name: { type: 'string', description: '线路名称或线路编号，兼容字段。' },
        ppartition: { type: 'string', description: '画像日期分区，可选，格式 yyyyMMdd。' },
        partition: { type: 'string', description: '画像日期分区，兼容字段。' },
      },
    },
  },
  [STATION_REPORT_SOURCE_TOOL_NAME]: {
    name: STATION_REPORT_SOURCE_TOOL_NAME,
    description:
      '获取站场报告专用数据源。该工具会调用站场画像相关 MCP 并返回报告生成可用的包装结构。',
    parameters: {
      type: 'object',
      properties: {
        busStationName: { type: 'string', description: '站场名称。' },
        stationName: { type: 'string', description: '站场名称，兼容字段。' },
        station_name: { type: 'string', description: '站场名称，兼容字段。' },
        ppartition: { type: 'string', description: '画像日期分区，可选，格式 yyyyMMdd。' },
        partition: { type: 'string', description: '画像日期分区，兼容字段。' },
      },
    },
  },
  [ACCIDENT_REPORT_SOURCE_TOOL_NAME]: {
    name: ACCIDENT_REPORT_SOURCE_TOOL_NAME,
    description:
      '获取事故调查报告专用数据源。该工具会调用事故详情 MCP 并返回报告生成可用的包装结构。',
    parameters: {
      type: 'object',
      properties: {
        driverName: { type: 'string', description: '肇事驾驶员姓名。' },
        driver_name: { type: 'string', description: '肇事驾驶员姓名，兼容字段。' },
        accidentDate: {
          type: 'string',
          description: '事故发生时间或日期分区，格式通常为 yyyyMMddHHmmss。',
        },
        accident_date: {
          type: 'string',
          description: '事故发生时间或日期分区，兼容字段。',
        },
      },
    },
  },
};

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function cloneJsonValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function pickRecordAtPath(
  sourceData: Record<string, unknown>,
  path: string
): Record<string, unknown> | null {
  const segments = path.split('.');
  let current: unknown = sourceData;
  for (const segment of segments) {
    if (!isPlainRecord(current) || !(segment in current)) {
      return null;
    }
    current = current[segment];
  }
  return isPlainRecord(current) ? cloneJsonValue(current) : null;
}

function pickArrayAtPath(sourceData: Record<string, unknown>, path: string): unknown[] | null {
  const segments = path.split('.');
  let current: unknown = sourceData;
  for (const segment of segments) {
    if (!isPlainRecord(current) || !(segment in current)) {
      return null;
    }
    current = current[segment];
  }
  return Array.isArray(current) ? cloneJsonValue(current) : null;
}

function pickValueAtPath(sourceData: Record<string, unknown>, path: string): unknown {
  const segments = path.split('.');
  let current: unknown = sourceData;
  for (const segment of segments) {
    if (!isPlainRecord(current) || !(segment in current)) {
      return null;
    }
    current = current[segment];
  }
  return cloneJsonValue(current);
}

function compactRecord(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => {
      if (entry == null) return false;
      if (Array.isArray(entry)) return entry.length > 0;
      if (isPlainRecord(entry)) return Object.keys(entry).length > 0;
      return true;
    })
  );
}

function buildManagementPromptSourceData(
  workerTool: StructuredReportDataSourceToolName,
  sourceData: Record<string, unknown>
): Record<string, unknown> {
  const appendixRawData = compactRecord({
    source_window: pickRecordAtPath(sourceData, 'appendix.raw_data.source_window'),
    main: pickRecordAtPath(sourceData, 'appendix.raw_data.main'),
    ranking_snapshot: pickRecordAtPath(sourceData, 'appendix.raw_data.ranking_snapshot'),
    alerts_counts: pickRecordAtPath(sourceData, 'appendix.raw_data.alerts_counts'),
    suggestion_counts: pickRecordAtPath(sourceData, 'appendix.raw_data.suggestion_counts'),
    quota_summary: pickArrayAtPath(sourceData, 'appendix.raw_data.quota_summary'),
    trend_summary:
      pickArrayAtPath(sourceData, 'appendix.raw_data.trend_summary') ??
      pickRecordAtPath(sourceData, 'appendix.raw_data.trend_summary'),
  });
  const appendixMain = pickRecordAtPath(sourceData, 'appendix.raw_data.main');
  const displayName =
    (typeof sourceData.name === 'string' && sourceData.name.trim()) ||
    (typeof sourceData.identifier === 'string' && sourceData.identifier.trim()) ||
    null;
  const entityId =
    (typeof sourceData.identifier === 'string' && sourceData.identifier.trim()) ||
    (typeof sourceData.id === 'string' && sourceData.id.trim()) ||
    null;
  const partition =
    (typeof appendixMain?.ppartition === 'string' && appendixMain.ppartition.trim()) ||
    (typeof appendixRawData.partition === 'string' && appendixRawData.partition.trim()) ||
    null;

  return compactRecord({
    source_contract: 'structured_report_prompt_source_v1',
    worker_tool: workerTool,
    entity: compactRecord({
      display_name: displayName,
      entity_id: entityId,
      partition,
    }),
    basic: pickRecordAtPath(sourceData, 'basic'),
    performance_dashboard: pickRecordAtPath(sourceData, 'performance_dashboard'),
    interventions: compactRecord({
      recommendations: pickArrayAtPath(sourceData, 'interventions.recommendations'),
    }),
    appendix: Object.keys(appendixRawData).length > 0 ? { raw_data: appendixRawData } : undefined,
  });
}

function buildManagementPromptSourceDataWithResolved(
  workerTool: StructuredReportDataSourceToolName,
  sourceData: Record<string, unknown>,
  resolved: {
    displayName: string;
    entityId?: string | null;
    partition?: string | null;
  }
): Record<string, unknown> {
  const promptSource = buildManagementPromptSourceData(workerTool, sourceData);
  const entity = isPlainRecord(promptSource.entity) ? promptSource.entity : {};
  promptSource.entity = compactRecord({
    ...entity,
    display_name:
      (typeof entity.display_name === 'string' && entity.display_name.trim()) ||
      resolved.displayName,
    entity_id:
      (typeof entity.entity_id === 'string' && entity.entity_id.trim()) ||
      resolved.entityId ||
      null,
    partition:
      (typeof entity.partition === 'string' && entity.partition.trim()) ||
      resolved.partition ||
      null,
  });
  return promptSource;
}

function buildAccidentPromptSourceData(
  sourceData: Record<string, unknown>
): Record<string, unknown> {
  const basic = pickRecordAtPath(sourceData, 'basic');
  const rawBasic = compactRecord({
    incident_id:
      basic?.incident_id ??
      sourceData.accidentNo ??
      sourceData.accidentUid ??
      sourceData.guid ??
      sourceData.id,
    accident_date: basic?.accident_date ?? sourceData.accidentDate,
    driver_name: basic?.driver_name ?? sourceData.driverName ?? sourceData.employeeName,
    employee_code: basic?.employee_code ?? sourceData.employeeCode,
    vehicle_plate: basic?.vehicle_plate ?? sourceData.busLicenseNum,
    vehicle_id:
      basic?.vehicle_id ??
      [sourceData.busLicenseNum, sourceData.busCode].filter(Boolean).join('/'),
    route_name: basic?.route_name ?? sourceData.lineName ?? sourceData.routeName,
    line_code: basic?.line_code ?? sourceData.lineCode,
    location: basic?.location ?? sourceData.accidentPlace,
    event_description: basic?.event_description ?? sourceData.accidentDesc,
    road_condition: basic?.road_condition ?? sourceData.roadCondition,
    organization: basic?.organization ?? sourceData.orgName ?? sourceData.deptName,
    motorcade: basic?.motorcade ?? sourceData.motorcade,
    responsibility: basic?.responsibility ?? sourceData.accidentLiability,
    accident_cause: basic?.accident_cause ?? sourceData.accidentCause,
    accident_aftermath: basic?.accident_aftermath ?? sourceData.accidentAftermath,
    accident_classify: basic?.accident_classify ?? sourceData.accidentClassify,
    collision_position: basic?.collision_position ?? sourceData.collisionPosition,
    opinion_status: basic?.opinion_status ?? sourceData.opinionStatus,
    audit_status: basic?.audit_status ?? sourceData.auditStatus,
  });
  const section1 = pickRecordAtPath(sourceData, 'section_1_event_and_response');
  const rawSection1 = compactRecord({
    accident_process: compactRecord({
      description: sourceData.accidentDesc,
      place: sourceData.accidentPlace,
      road_condition: sourceData.roadCondition,
      collision_position: sourceData.collisionPosition,
    }),
    emergency_response: compactRecord({
      accident_status: sourceData.accidentStatus,
      accident_follow_person: sourceData.accidentFollowPerson,
      accident_follow_date: sourceData.accidentFollowDate,
      video_extract_status: sourceData.videoExtractStatus,
      video_extract_date: sourceData.videoExtractDate,
    }),
    casualty_and_loss: compactRecord({
      injury:
        typeof sourceData.accidentDesc === 'string' && sourceData.accidentDesc.includes('无人员受伤')
          ? '无人员受伤'
          : undefined,
    }),
  });
  const section2 = pickRecordAtPath(sourceData, 'section_2_investigation');
  const rawSection2 = compactRecord({
    unit_and_route_overview: compactRecord({
      org_name: sourceData.orgName,
      dept_name: sourceData.deptName,
      motorcade: sourceData.motorcade,
      route_name: sourceData.lineName ?? sourceData.routeName,
      line_code: sourceData.lineCode,
    }),
    driver_profile: compactRecord({
      name: sourceData.driverName ?? sourceData.employeeName,
      employee_code: sourceData.employeeCode,
    }),
    vehicle_profile: compactRecord({
      plate_number: sourceData.busLicenseNum,
      vehicle_id: sourceData.busCode,
      model: sourceData.busModel,
    }),
  });
  const section3 = pickRecordAtPath(sourceData, 'section_3_cause_and_nature');
  const rawSection3 = compactRecord({
    accident_nature: sourceData.accidentLiability,
    subjective_causes: sourceData.driverHandleOpinion ? [sourceData.driverHandleOpinion] : undefined,
    objective_causes: sourceData.accidentCause ? [`事故原因：${sourceData.accidentCause}`] : undefined,
  });
  const section4 = pickRecordAtPath(sourceData, 'section_4_rectification_plan');
  const rawSection4 = compactRecord({
    awareness_and_responsibility: sourceData.improveMeasures
      ? [sourceData.improveMeasures]
      : undefined,
    targeted_training_and_controls: sourceData.teamLeaderOpinion
      ? [sourceData.teamLeaderOpinion]
      : undefined,
    risk_control_and_prevention: sourceData.safetyOfficerOpinion
      ? [sourceData.safetyOfficerOpinion]
      : undefined,
    accountability_and_culture: sourceData.branchLeaderOpinion
      ? [sourceData.branchLeaderOpinion]
      : undefined,
  });
  const suggestions = isRecord(sourceData.suggestions)
    ? (sourceData.suggestions as Record<string, unknown>)
    : null;
  const driverSuggestions =
    suggestions && Array.isArray(suggestions['driver_suggestions'])
      ? suggestions['driver_suggestions']
      : [];
  const routeSuggestions =
    suggestions && Array.isArray(suggestions['route_suggestions'])
      ? suggestions['route_suggestions']
      : [];
  const busSuggestions =
    suggestions && Array.isArray(suggestions['bus_suggestions'])
      ? suggestions['bus_suggestions']
      : [];

  return compactRecord({
    source_contract: 'structured_report_prompt_source_v1',
    worker_tool: 'generate_accident_investigation_report',
    entity: compactRecord({
      display_name:
        (typeof sourceData.report_title === 'string' && sourceData.report_title.trim()) ||
        (rawBasic.incident_id as string | undefined) ||
        (rawBasic.driver_name as string | undefined) ||
        null,
      entity_id: (rawBasic.incident_id as string | undefined) || null,
    }),
    basic: Object.keys(rawBasic).length > 0 ? rawBasic : basic,
    section_1_event_and_response:
      Object.keys(rawSection1).length > 0 ? rawSection1 : section1,
    section_2_investigation: Object.keys(rawSection2).length > 0 ? rawSection2 : section2,
    section_3_cause_and_nature: Object.keys(rawSection3).length > 0 ? rawSection3 : section3,
    section_4_rectification_plan: Object.keys(rawSection4).length > 0 ? rawSection4 : section4,
    behavior_stat: sourceData.behavior_stat,
    driver_stat: sourceData.driver_stat,
    unit_stat: sourceData.unit_stat,
    trigger_analysis: pickRecordAtPath(sourceData, 'trigger_analysis'),
    suggestions: compactRecord({
      driver: driverSuggestions.length > 0 ? driverSuggestions : undefined,
      route: routeSuggestions.length > 0 ? routeSuggestions : undefined,
      bus: busSuggestions.length > 0 ? busSuggestions : undefined,
    }),
  });
}

function buildStructuredPrefetchedPromptInternal(input: {
  workerTool: StructuredReportDataSourceToolName;
  displayName: string;
  entityId?: string | null;
  partition?: string | null;
  sourceData: Record<string, unknown>;
}): string {
  const labels: Record<StructuredReportDataSourceToolName, string> = {
    generate_driver_report: 'driver safety report',
    generate_vehicle_report: 'vehicle safety report',
    generate_unit_report: 'unit safety report',
    generate_route_report: 'route safety report',
    generate_station_report: 'station safety report',
    generate_accident_investigation_report: 'accident investigation report',
  };
  const promptSource = buildStructuredReportPromptSource(input.workerTool, input.sourceData, {
    displayName: input.displayName,
    entityId: input.entityId,
    partition: input.partition,
  });

  return [
    `Generate the ${labels[input.workerTool]} for ${input.displayName} using only the report_source below.`,
    'Do not call any tools.',
    'Do not re-query or re-resolve the target object.',
    'Use only the provided report_source to produce the final structured JSON output.',
    'If a field is unavailable, state that it is unavailable instead of inventing facts.',
    'report_source:',
    JSON.stringify(promptSource, null, 2),
  ].join('\n');
}

function buildDriverReportExternalToolInstructions(
  driverName: string,
  partition?: string | null
): string[] {
  const resolvedPartition = String(partition ?? '').trim() || getDefaultDriverProfilePartition();
  const toolArgs = `{"driverName":"${driverName}","ppartition":"${resolvedPartition}"}`;
  return [
    `1. 如当前轮未提供 report_source，可使用 ${DRIVER_REPORT_SOURCE_TOOL_NAME} 补查驾驶员报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}。若未指定画像日期，默认使用当日分区 ${resolvedPartition}。`,
    '3. 不要改用其他工具替代驾驶员画像数据源。',
    '4. 若未拿到有效业务数据，返回 {"error":"driver_not_found","message":"未找到该驾驶员，请确认姓名或工号后重试"}，不要输出占位报告。',
    '5. 严格按技能模板输出 JSON，不要输出 Markdown。',
    '6. 只能基于真实字段生成报告，不要编造次数、排名或建议。',
  ];
}

function buildVehicleReportExternalToolInstructions(
  numberPlate: string,
  partition?: string | null
): string[] {
  const resolvedPartition = String(partition ?? '').trim();
  const toolArgs = resolvedPartition
    ? `{"numberPlate":"${numberPlate}","ppartition":"${resolvedPartition}"}`
    : `{"numberPlate":"${numberPlate}"}`;
  return [
    `1. 如当前轮未提供 report_source，可使用 ${VEHICLE_REPORT_SOURCE_TOOL_NAME} 补查车辆报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}（未指定 ppartition 时默认查询最新画像日期）`,
    '3. 车牌号优先使用完整格式“粤A + 5 或 6 位字母/数字”，例如“粤A12345”或“粤A12345D”；如果用户只写了“A12345”或“A12345D”这类缺少省份简称的形式，先按完整车牌理解后再调用工具。',
    '4. 不要改用其他工具替代车辆画像数据源。',
    '5. 若未拿到有效业务数据，返回 {"error":"vehicle_not_found","message":"未找到该车辆画像数据，请确认车牌号后重试"}，不要输出占位报告。',
    '6. 严格按技能模板输出 JSON，最终一级指标只能是“综合风险 / 故障风险 / 能耗风险”。',
    '7. 只允许基于真实字段生成报告，不要编造告警次数、排名或建议。',
  ];
}

function buildUnitReportExternalToolInstructions(
  organName: string,
  partition?: string | null
): string[] {
  const resolvedPartition = String(partition ?? '').trim();
  const toolArgs = resolvedPartition
    ? `{"organName":"${organName}","ppartition":"${resolvedPartition}"}`
    : `{"organName":"${organName}"}`;
  return [
    `1. 如当前轮未提供 report_source，可使用 ${UNIT_REPORT_SOURCE_TOOL_NAME} 补查单位报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}（未指定 ppartition 时默认查询最新画像日期）`,
    '3. 不要改用其他工具替代单位画像数据源。',
    '4. 若未拿到有效业务数据，返回 {"error":"unit_not_found","message":"未找到该单位画像数据，请确认单位名称后重试"}，不要输出占位报告。',
    '5. 严格按技能模板输出 JSON，最终一级指标只能是“综合风险 / 驾驶员风险 / 车辆风险 / 线路风险 / 站场风险”。',
    '6. 只允许基于真实字段生成报告，不要编造告警次数、排名、对象清单或建议。',
  ];
}

function buildRouteReportExternalToolInstructions(
  routeName: string,
  partition?: string | null
): string[] {
  const resolvedPartition = String(partition ?? '').trim() || getDefaultRouteProfilePartition();
  const toolArgs = `{"routeName":"${routeName}","ppartition":"${resolvedPartition}"}`;
  return [
    `1. 如当前轮未提供 report_source，可使用 ${ROUTE_REPORT_SOURCE_TOOL_NAME} 补查线路报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}。若未指定画像日期，默认使用当日分区 ${resolvedPartition}。`,
    '3. 不要改用其他工具替代线路画像数据源。',
    '4. 若未拿到有效业务数据，返回 {"error":"route_not_found","message":"未找到该线路，请确认线路名称或线路编号后重试"}，不要输出占位报告。',
    '5. 严格按技能模板输出 JSON，不要输出 Markdown。',
    '6. 只能基于真实字段生成报告，不要编造次数、排名或建议。',
  ];
}

function buildStationReportExternalToolInstructions(
  stationName: string,
  partition?: string | null
): string[] {
  const resolvedPartition = String(partition ?? '').trim();
  const toolArgs = resolvedPartition
    ? `{"busStationName":"${stationName}","ppartition":"${resolvedPartition}"}`
    : `{"busStationName":"${stationName}"}`;
  return [
    `1. 如当前轮未提供 report_source，可使用 ${STATION_REPORT_SOURCE_TOOL_NAME} 补查站场报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}（未指定 ppartition 时默认查询最新画像日期）。`,
    '3. 不要改用其他工具替代站场画像数据源。',
    '4. 若未拿到有效业务数据，返回 {"error":"station_not_found","message":"未找到该站场画像数据，请确认站场名称后重试"}，不要输出占位报告。',
    '5. 严格按技能模板输出 JSON，不要输出 Markdown。',
    '6. 只能基于真实字段生成报告，不要编造次数、排名、指标或建议。',
  ];
}

function buildAccidentReportExternalToolInstructions(
  driverName: string,
  accidentDate?: string | null
): string[] {
  const toolArgs = accidentDate
    ? `{"driverName":"${driverName}","accidentDate":"${accidentDate}"}`
    : `{"driverName":"${driverName}"}`;
  return [
    `1. If report_source is not provided, call ${ACCIDENT_REPORT_SOURCE_TOOL_NAME} to fetch accident investigation report source data.`,
    `2. Tool args: ${toolArgs}. driverName is the accident driver name; accidentDate is the accident time in yyyyMMddHHmmss format.`,
    '3. Do not use other tools as substitutes for accident investigation source data.',
    '4. Output must align with the accident analysis report template: four chapters and their subsections.',
    '5. Template annotation syntax is mandatory: use `{}` for source data insertions and `[]` for AI analysis judgments.',
    '6. section_1.event.description must include date, driver name, plate number, and location.',
    '7. section_2.driver_info.behavior_data must be extracted from behavior_stat.result eventName/eventNum; use driver_stat only for accident, violation, and work-hour fields.',
    '8. section_2.can_gps must be extracted from source CAN data.',
    '9. Every section_3.subjective_cause.items entry must include `{}` and `[]` annotations.',
    '10. section_3.nature must output a valid liability determination.',
    '11. section_4.measures must include at least three items.',
    '12. If no valid source data is found, return {"error":"incident_not_found"} and do not invent accident information.',
  ];
  return [
    `1. 如当前轮未提供 report_source，可使用 ${ACCIDENT_REPORT_SOURCE_TOOL_NAME} 补查事故调查报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}。driverName 为肇事驾驶员姓名，ppartition 为事故日期分区（yyyyMMdd）。`,
    '3. 不要改用其他工具替代事故调查数据源。',
    '4. 输出必须对齐《事故分析报告模板》的章节结构：四章（事故经过、调查情况、原因分析、整改措施）及子节。',
    '5. 模板标注语法（硬约束）：数据植入位用 `{}`，AI 分析判断用 `[]`。',
    '6. section_1.event.description 必须包含：日期、驾驶员姓名、车牌号、地点。',
    '7. section_2.driver_info.behavior_data 必须从源数据提取事发前1个月行为数据（疲劳次数、斑马线违规、急加速等）。',
    '8. section_2.can_gps 必须从源数据提取CAN数据（车速、加速度、踏板开度、档位）。',
    '9. section_3.subjective_cause.items 每条必须含 `{}` 和 `[]` 标注，至少2条。',
    '10. section_3.nature 输出有效责任认定（主责/同责/次责/无责）。',
    '11. section_4.measures 至少3条，按话术5节结构输出。',
    '12. 若最终仍未命中，不要编造事故信息；返回 {"error":"incident_not_found"}。',
  ];
}

function buildDriverReportExternalToolInstructionsLatestAware(
  driverName: string,
  partition?: string | null
): string[] {
  const resolvedPartition = String(partition ?? '').trim();
  const toolArgs = resolvedPartition
    ? `{"driverName":"${driverName}","ppartition":"${resolvedPartition}"}`
    : `{"driverName":"${driverName}"}`;
  return [
    `1. 如果当前轮未提供 report_source，可使用 ${DRIVER_REPORT_SOURCE_TOOL_NAME} 补查驾驶员报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}（未指定 ppartition 时默认查询最新画像日期）`,
    '3. 不要改用其他工具替代驾驶员画像数据源。',
    '4. 若未拿到有效业务数据，返回 {"error":"driver_not_found","message":"未找到该驾驶员，请确认姓名或工号后重试"}，不要输出占位报告。',
    '5. 严格按技能模板输出 JSON，不要输出 Markdown。',
    '6. 最终报告必须对齐“综合风险 + 四个一级指标”的固定五行看板，核心风险研判写成单段总结。',
    '7. 行为分析默认不重复分析综合风险；干预建议按全局高风险基础指标排序，不要求与分析项一一对应。',
    '8. 只能基于真实字段生成报告，不要编造次数、排名或建议。',
  ];
}

function buildRouteReportExternalToolInstructionsLatestAware(
  routeName: string,
  partition?: string | null
): string[] {
  const resolvedPartition = String(partition ?? '').trim();
  const toolArgs = resolvedPartition
    ? `{"routeName":"${routeName}","ppartition":"${resolvedPartition}"}`
    : `{"routeName":"${routeName}"}`;
  return [
    `1. 如果当前轮未提供 report_source，可使用 ${ROUTE_REPORT_SOURCE_TOOL_NAME} 补查线路报告数据源。`,
    `2. 若调用该工具，参数为：${toolArgs}（未指定 ppartition 时默认查询最新画像日期）`,
    '3. 不要改用其他工具替代线路画像数据源。',
    '4. 若未拿到有效业务数据，返回 {"error":"route_not_found","message":"未找到该线路，请确认线路名称或线路编号后重试"}，不要输出占位报告。',
    '5. 严格按技能模板输出 JSON，不要输出 Markdown。',
    '6. 只能基于真实字段生成报告，不要编造次数、排名或建议。',
  ];
}

export function extractVehicleReportPartition(value: string | null | undefined): string | null {
  const extracted = extractVehicleProfilePartitionFromText(value, '');
  return extracted.trim() ? extracted : null;
}

export function extractDriverReportPartition(value: string | null | undefined): string | null {
  const extracted = extractVehicleProfilePartitionFromText(value, '');
  return extracted.trim() ? extracted : null;
}

export function extractUnitReportPartition(value: string | null | undefined): string | null {
  const extracted = extractVehicleProfilePartitionFromText(value, '');
  return extracted.trim() ? extracted : null;
}

const STRUCTURED_REPORT_DATA_SOURCE_CONFIGS: Partial<
  Record<StructuredReportDataSourceToolName, StructuredReportDataSourceConfig>
> = {
  generate_driver_report: {
    mode: 'external_tool',
    toolAllowList: [DRIVER_REPORT_SOURCE_TOOL_NAME],
    buildPromptSourceData(sourceData) {
      return buildManagementPromptSourceData('generate_driver_report', sourceData);
    },
    buildResolvedPrefetchedPrompt(resolved) {
      return buildStructuredPrefetchedPromptInternal({
        workerTool: 'generate_driver_report',
        displayName: resolved.displayName,
        entityId: resolved.entityId,
        partition: resolved.partition,
        sourceData: resolved.sourceData,
      });
    },
    buildUnresolvedPrompt(entityToken: string, partition?: string | null) {
      return [
        `请生成驾驶员“${entityToken}”的安全报告。`,
        ...buildDriverReportExternalToolInstructionsLatestAware(entityToken, partition),
      ].join('\n');
    },
    buildResolvedPrompt(resolved) {
      return [
        `请生成驾驶员“${resolved.displayName}”的安全报告。`,
        `已确认目标驾驶员姓名为“${resolved.displayName}”${resolved.entityId ? `，工号为“${resolved.entityId}”` : ''}${resolved.partition ? `，报告日期为“${resolved.partition}”` : ''}。`,
        ...buildDriverReportExternalToolInstructionsLatestAware(
          resolved.displayName,
          resolved.partition
        ),
      ].join('\n');
    },
    buildMissingDataPrompt(mode) {
      if (mode === 'missing_read_call') {
        return `当前还没有拿到有效驾驶员画像数据。请先获取真实驾驶员画像数据，再输出结构化 JSON 报告。`;
      }
      if (mode === 'read_failed') {
        return `你调用了 ${DRIVER_REPORT_SOURCE_TOOL_NAME}，但调用未成功。请修正参数并重新调用，成功拿到真实数据后再输出报告。`;
      }
      if (mode === 'missing_get_hit') {
        return `你调用了 ${DRIVER_REPORT_SOURCE_TOOL_NAME}，但没有命中有效结果。请确认驾驶员姓名与日期分区后重试；若仍无数据，直接返回 error JSON。`;
      }
      return `${DRIVER_REPORT_SOURCE_TOOL_NAME} 已成功调用，但未返回有效业务数据。请不要输出占位报告，直接返回 error JSON。`;
    },
  },
  generate_vehicle_report: {
    mode: 'external_tool',
    toolAllowList: [VEHICLE_REPORT_SOURCE_TOOL_NAME],
    buildPromptSourceData(sourceData) {
      return buildManagementPromptSourceData('generate_vehicle_report', sourceData);
    },
    buildResolvedPrefetchedPrompt(resolved) {
      return buildStructuredPrefetchedPromptInternal({
        workerTool: 'generate_vehicle_report',
        displayName: resolved.displayName,
        entityId: resolved.entityId,
        partition: resolved.partition,
        sourceData: resolved.sourceData,
      });
    },
    buildUnresolvedPrompt(entityToken: string, partition?: string | null) {
      return [
        `请生成车辆“${entityToken}”的安全报告。`,
        ...buildVehicleReportExternalToolInstructions(entityToken, partition),
      ].join('\n');
    },
    buildResolvedPrompt(resolved) {
      return [
        `请生成车辆“${resolved.displayName}”的安全报告。`,
        `已确认目标车辆车牌号为“${resolved.displayName}”${resolved.entityId ? `，车辆标识为“${resolved.entityId}”` : ''}${resolved.partition ? `，报告日期为“${resolved.partition}”` : ''}。`,
        ...buildVehicleReportExternalToolInstructions(resolved.displayName, resolved.partition),
      ].join('\n');
    },
    buildMissingDataPrompt(mode) {
      if (mode === 'missing_read_call') {
        return `当前还没有拿到有效车辆画像数据。请先获取真实车辆画像数据，再输出结构化 JSON 报告。`;
      }
      if (mode === 'read_failed') {
        return `你调用了 ${VEHICLE_REPORT_SOURCE_TOOL_NAME}，但调用未成功。请修正参数并重新调用，成功拿到真实数据后再输出报告。`;
      }
      if (mode === 'missing_get_hit') {
        return `你调用了 ${VEHICLE_REPORT_SOURCE_TOOL_NAME}，但没有命中有效结果。请优先确认完整车牌号格式是否为“粤A + 5 或 6 位字母/数字”（例如“粤A12345”“粤A12345D”），并检查可选 ppartition 后重试；若仍无数据，直接返回 error JSON。`;
      }
      return `${VEHICLE_REPORT_SOURCE_TOOL_NAME} 已成功调用，但未返回有效业务数据。请不要输出占位报告，直接返回 error JSON。`;
    },
  },
  generate_unit_report: {
    mode: 'external_tool',
    toolAllowList: [UNIT_REPORT_SOURCE_TOOL_NAME],
    buildPromptSourceData(sourceData) {
      return buildManagementPromptSourceData('generate_unit_report', sourceData);
    },
    buildResolvedPrefetchedPrompt(resolved) {
      return buildStructuredPrefetchedPromptInternal({
        workerTool: 'generate_unit_report',
        displayName: resolved.displayName,
        entityId: resolved.entityId,
        partition: resolved.partition,
        sourceData: resolved.sourceData,
      });
    },
    buildUnresolvedPrompt(entityToken: string, partition?: string | null) {
      return [
        `请生成单位“${entityToken}”的安全风险分析总结报告（管理人员版）。`,
        ...buildUnitReportExternalToolInstructions(entityToken, partition),
      ].join('\n');
    },
    buildResolvedPrompt(resolved) {
      return [
        `请生成单位“${resolved.displayName}”的安全风险分析总结报告（管理人员版）。`,
        `已确认目标单位名称为“${resolved.displayName}”${resolved.entityId ? `，单位标识为“${resolved.entityId}”` : ''}${resolved.partition ? `，报告日期为“${resolved.partition}”` : ''}。`,
        ...buildUnitReportExternalToolInstructions(resolved.displayName, resolved.partition),
      ].join('\n');
    },
    buildMissingDataPrompt(mode) {
      if (mode === 'missing_read_call') {
        return `当前还没有拿到有效单位画像数据。请先获取真实单位画像数据，再输出结构化 JSON 报告。`;
      }
      if (mode === 'read_failed') {
        return `你调用了 ${UNIT_REPORT_SOURCE_TOOL_NAME}，但调用未成功。请修正参数并重新调用，成功拿到真实数据后再输出报告。`;
      }
      if (mode === 'missing_get_hit') {
        return `你调用了 ${UNIT_REPORT_SOURCE_TOOL_NAME}，但没有命中有效结果。请确认单位名称（及可选 ppartition）后重试；若仍无数据，直接返回 error JSON。`;
      }
      return `${UNIT_REPORT_SOURCE_TOOL_NAME} 已成功调用，但未返回有效业务数据。请不要输出占位报告，直接返回 error JSON。`;
    },
  },
  generate_route_report: {
    mode: 'external_tool',
    toolAllowList: [ROUTE_REPORT_SOURCE_TOOL_NAME],
    buildPromptSourceData(sourceData) {
      return buildManagementPromptSourceData('generate_route_report', sourceData);
    },
    buildResolvedPrefetchedPrompt(resolved) {
      return buildStructuredPrefetchedPromptInternal({
        workerTool: 'generate_route_report',
        displayName: resolved.displayName,
        entityId: resolved.entityId,
        partition: resolved.partition,
        sourceData: resolved.sourceData,
      });
    },
    buildUnresolvedPrompt(entityToken: string, partition?: string | null) {
      return [
        `请生成线路“${entityToken}”的安全风险分析总结报告（管理人员版）。`,
        ...buildRouteReportExternalToolInstructionsLatestAware(entityToken, partition),
      ].join('\n');
    },
    buildResolvedPrompt(resolved) {
      return [
        `请生成线路“${resolved.displayName}”的安全风险分析总结报告（管理人员版）。`,
        `已确认目标线路名称为“${resolved.displayName}”${resolved.entityId ? `，线路标识为“${resolved.entityId}”` : ''}${resolved.partition ? `，报告日期为“${resolved.partition}”` : ''}。`,
        ...buildRouteReportExternalToolInstructionsLatestAware(
          resolved.displayName,
          resolved.partition
        ),
      ].join('\n');
    },
    buildMissingDataPrompt(mode) {
      if (mode === 'missing_read_call') {
        return `当前还没有拿到有效线路画像数据。请先获取真实线路画像数据，再输出结构化 JSON 报告。`;
      }
      if (mode === 'read_failed') {
        return `你调用了 ${ROUTE_REPORT_SOURCE_TOOL_NAME}，但调用未成功。请修正参数并重新调用，成功拿到真实数据后再输出报告。`;
      }
      if (mode === 'missing_get_hit') {
        return `你调用了 ${ROUTE_REPORT_SOURCE_TOOL_NAME}，但没有命中有效结果。请确认线路名称与日期分区后重试；若仍无数据，直接返回 error JSON。`;
      }
      return `${ROUTE_REPORT_SOURCE_TOOL_NAME} 已成功调用，但未返回有效业务数据。请不要输出占位报告，直接返回 error JSON。`;
    },
  },
  generate_station_report: {
    mode: 'external_tool',
    toolAllowList: [STATION_REPORT_SOURCE_TOOL_NAME],
    buildPromptSourceData(sourceData) {
      return buildManagementPromptSourceData('generate_station_report', sourceData);
    },
    buildResolvedPrefetchedPrompt(resolved) {
      return buildStructuredPrefetchedPromptInternal({
        workerTool: 'generate_station_report',
        displayName: resolved.displayName,
        entityId: resolved.entityId,
        partition: resolved.partition,
        sourceData: resolved.sourceData,
      });
    },
    buildUnresolvedPrompt(entityToken: string, partition?: string | null) {
      return [
        `请生成站场“${entityToken}”的安全风险分析总结报告（管理人员版）。`,
        ...buildStationReportExternalToolInstructions(entityToken, partition),
      ].join('\n');
    },
    buildResolvedPrompt(resolved) {
      return [
        `请生成站场“${resolved.displayName}”的安全风险分析总结报告（管理人员版）。`,
        `已确认目标站场名称为“${resolved.displayName}”${resolved.entityId ? `，站场标识为“${resolved.entityId}”` : ''}${resolved.partition ? `，报告日期为“${resolved.partition}”` : ''}。`,
        ...buildStationReportExternalToolInstructions(resolved.displayName, resolved.partition),
      ].join('\n');
    },
    buildMissingDataPrompt(mode) {
      if (mode === 'missing_read_call') {
        return `当前还没有拿到有效站场画像数据。请先调用 ${STATION_REPORT_SOURCE_TOOL_NAME} 获取真实站场报告数据源，再输出结构化 JSON 报告。`;
      }
      if (mode === 'read_failed') {
        return `你调用了 ${STATION_REPORT_SOURCE_TOOL_NAME}，但调用未成功。请修正参数并重试，成功拿到真实数据后再输出报告。`;
      }
      if (mode === 'missing_get_hit') {
        return `你调用了 ${STATION_REPORT_SOURCE_TOOL_NAME}，但没有命中有效结果。请确认站场名称与可选 ppartition 后重试；若仍无数据，直接返回 error JSON。`;
      }
      return `${STATION_REPORT_SOURCE_TOOL_NAME} 已成功调用，但未返回有效业务数据。请不要输出占位报告，直接返回 error JSON。`;
    },
  },
  generate_accident_investigation_report: {
    mode: 'external_tool',
    toolAllowList: [ACCIDENT_REPORT_SOURCE_TOOL_NAME],
    buildPromptSourceData(sourceData) {
      return buildAccidentPromptSourceData(sourceData);
    },
    buildResolvedPrefetchedPrompt(resolved) {
      return buildStructuredPrefetchedPromptInternal({
        workerTool: 'generate_accident_investigation_report',
        displayName: resolved.displayName,
        entityId: resolved.entityId,
        partition: resolved.partition,
        sourceData: resolved.sourceData,
      });
    },
    buildUnresolvedPrompt(entityToken: string, partition?: string | null) {
      return [
        `请生成事故调查情况和整改措施报告（驾驶员："${entityToken}"${partition ? `，事故发生时间："${partition}"` : ''}）。`,
        ...buildAccidentReportExternalToolInstructions(entityToken, partition),
      ].join('\n');
    },
    buildResolvedPrompt(resolved) {
      return [
        `请生成事故调查情况和整改措施报告（驾驶员："${resolved.entityId ?? resolved.displayName}"${resolved.partition ? `，事故发生时间："${resolved.partition}"` : ''}）。`,
        `已确认目标事故为驾驶员"${resolved.displayName}"${resolved.entityId ? `，驾驶员姓名为"${resolved.entityId}"` : ''}${resolved.partition ? `，事故日期为"${resolved.partition}"` : ''}。`,
        ...buildAccidentReportExternalToolInstructions(
          resolved.entityId ?? resolved.displayName,
          resolved.partition
        ),
      ].join('\n');
    },
    buildMissingDataPrompt(mode) {
      if (mode === 'missing_read_call') {
        return '当前还没有拿到有效的事故案例数据。请先获取真实事故案例数据，再输出结构化 JSON 报告。';
      }
      if (mode === 'read_failed') {
        return `你调用了 ${ACCIDENT_REPORT_SOURCE_TOOL_NAME}，但调用未成功。请修正参数并重新查询，成功拿到真实数据后再输出报告。`;
      }
      if (mode === 'missing_get_hit') {
        return `你调用了 ${ACCIDENT_REPORT_SOURCE_TOOL_NAME}，但没有命中目标事故详情。请确认驾驶员姓名与事故日期后重试；若仍无数据，不要编造事故信息。`;
      }
      return `${ACCIDENT_REPORT_SOURCE_TOOL_NAME} 已成功调用，但未返回有效业务数据。请不要输出占位报告。`;
    },
  },
};

export function getStructuredReportDataSourceConfig(
  tool: StructuredReportDataSourceToolName
): StructuredReportDataSourceConfig | null {
  return STRUCTURED_REPORT_DATA_SOURCE_CONFIGS[tool] ?? null;
}

export function buildStructuredReportPromptSource(
  tool: StructuredReportDataSourceToolName,
  sourceData: Record<string, unknown>,
  resolved?: {
    displayName?: string | null;
    entityId?: string | null;
    partition?: string | null;
  }
): Record<string, unknown> {
  const config = getStructuredReportDataSourceConfig(tool);
  const promptSource = config?.buildPromptSourceData
    ? config.buildPromptSourceData(sourceData)
    : cloneJsonValue(sourceData);

  if (
    resolved &&
    tool !== 'generate_accident_investigation_report' &&
    (resolved.displayName || resolved.entityId || resolved.partition)
  ) {
    return buildManagementPromptSourceDataWithResolved(tool, promptSource, {
      displayName: resolved.displayName ?? '',
      entityId: resolved.entityId ?? null,
      partition: resolved.partition ?? null,
    });
  }

  if (
    resolved &&
    tool === 'generate_accident_investigation_report' &&
    (resolved.displayName || resolved.entityId)
  ) {
    const entity = isPlainRecord(promptSource.entity) ? promptSource.entity : {};
    promptSource.entity = compactRecord({
      ...entity,
      display_name:
        (typeof entity.display_name === 'string' && entity.display_name.trim()) ||
        resolved.displayName ||
        null,
      entity_id:
        (typeof entity.entity_id === 'string' && entity.entity_id.trim()) ||
        resolved.entityId ||
        (typeof entity.driver_name === 'string' && entity.driver_name.trim()) ||
        null,
    });
  }

  return promptSource;
}

export function buildStructuredReportPrefetchedPrompt(input: {
  workerTool: StructuredReportDataSourceToolName;
  displayName: string;
  entityId?: string | null;
  partition?: string | null;
  sourceData: Record<string, unknown>;
}): string {
  const config = getStructuredReportDataSourceConfig(input.workerTool);
  if (config?.buildResolvedPrefetchedPrompt) {
    return config.buildResolvedPrefetchedPrompt({
      displayName: input.displayName,
      entityId: input.entityId ?? null,
      partition: input.partition ?? null,
      sourceData: input.sourceData,
    });
  }
  return buildStructuredPrefetchedPromptInternal(input);
}
