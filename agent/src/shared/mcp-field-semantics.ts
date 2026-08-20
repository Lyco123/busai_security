import { isRecord } from './guards';
import {
  PROFILE_COUNT_SEMANTICS,
  PROFILE_RISK_SCORE_SEMANTICS,
  PROFILE_SOURCE_SCORE_SEMANTICS,
  PROFILE_SUGGESTION_SCORE_SEMANTICS,
  PROFILE_WEIGHTED_VALUE_SEMANTICS,
} from './profile-quota-tree';

const MCP_FIELD_ALIAS_PATCH_ID = 'ai-security-mcp-field-alias-hotfix-20260610';

const RISK_DIRECTION_SEMANTICS =
  '风险分、风险值、风险贡献字段均按数值越高风险越高解释；完成率、合格率、下降率等非风险指标按字段自身语义解释。';

const COMPARISON_SCORE_SEMANTICS =
  'DriverRiskScoreItemVO 中 convertedScore/current_converted_risk_score 才是当前换算后风险分；previousPeriodRiskValue 等 RiskValue 字段是变化率或差异率，不是上期绝对分数。';

const CURRENT_PAGE_SEMANTICS =
  'records 或 accidentDescList 通常只是当前页结果；涉及总数时必须使用 total/total_record_count 或专门 count 字段，不能用当前页数组长度代替总量。';

type ToolSemanticContext = {
  toolName: string;
  profileQuery: boolean;
  suggestion: boolean;
  trend: boolean;
  riskComparison: boolean;
  blackspot: boolean;
  routeList: boolean;
  busList: boolean;
  busParkList: boolean;
  busStationList: boolean;
  employeeList: boolean;
  organAccident: boolean;
  driverCheck: boolean;
  behaviorStat: boolean;
  accidentList: boolean;
  organAccidentCount: boolean;
  driverAccidentCount: boolean;
  accidentBusInfo: boolean;
};

type McpFieldSemanticsPatchOptions = {
  stripAmbiguousFields?: boolean;
};

const PROFILE_QUERY_TOOLS = new Set([
  'get_mcp_base_absBusProfileMain_queryByNumberplate',
  'get_mcp_base_absCompanyProfileMain_queryCompanyProfile',
  'get_mcp_base_absDriverProfileMain_queryDriverProfile',
  'get_mcp_base_absRouteProfileMain_queryRouteProfile',
  'get_mcp_base_adsAccidentProfileMain_queryAccidentProfile',
  'get_mcp_base_absBusStationProfileMain_queryBusStationProfile',
]);

const SUGGESTION_TOOLS = new Set([
  'get_mcp_suggest_absBusSuggestedSub_queryByBusNameAndDate',
  'get_mcp_suggest_absDriverSuggestedSub_queryByDriverNameAndDate',
  'get_mcp_suggest_absRouteSuggestedSub_queryByRouteNameAndDate',
  'get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate',
  'get_mcp_suggest_absBusStationSuggestedSub_queryByBusStationNameAndDate',
]);

const TREND_TOOLS = new Set([
  'get_mcp_base_absCompanyProfileMain_quotaScoreTrend',
  'get_mcp_base_absDriverProfileMain_getQuotaScoreTop',
  'get_mcp_base_absDriverProfileMain_quotaScoreTrend',
]);

const RISK_COMPARISON_TOOLS = new Set([
  'get_mcp_base_absBusProfileMain_busRiskScore',
  'get_mcp_base_absCompanyProfileMain_getKeyRisk',
  'get_mcp_base_absDriverProfileMain_driverRiskScore',
  'get_mcp_base_absRouteProfileMain_routeRiskScore',
  'get_mcp_base_absBusStationProfileMain_stationRiskScore',
]);

function isMcpToolName(toolName: string): boolean {
  return toolName.startsWith('get_mcp_') || toolName.startsWith('post_mcp_');
}

function buildContext(toolName: string): ToolSemanticContext | null {
  if (!isMcpToolName(toolName)) return null;
  return {
    toolName,
    profileQuery: PROFILE_QUERY_TOOLS.has(toolName),
    suggestion: SUGGESTION_TOOLS.has(toolName),
    trend: TREND_TOOLS.has(toolName),
    riskComparison: RISK_COMPARISON_TOOLS.has(toolName),
    blackspot: toolName === 'get_mcp_blackspot_adsEventBlackSpot_queryConfirmedBlackSpots',
    routeList: toolName === 'post_mcp_ods_odsJituanBsRoute_list',
    busList: toolName === 'post_mcp_base_odsJituanBsBus_list',
    busParkList: toolName === 'post_mcp_ods_odsJituanBsBusPark_list',
    busStationList: toolName === 'post_mcp_ods_odsJituanBsBusStation_list',
    employeeList: toolName === 'post_mcp_ods_odsJituanBsEmployee_list',
    organAccident: toolName === 'get_mcp_ods_odsJituanBsEmployee_getOrganAccident',
    driverCheck:
      toolName === 'get_mcp_ods_odsJituanBsEmployee_getDriverCheckCount' ||
      toolName === 'get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount',
    behaviorStat: toolName === 'get_mcp_ods_odsJituanBsEmployee_getBehaviorStat',
    accidentList: toolName === 'get_mcp_ods_odsJituanBsEmployee_getAccidentList',
    organAccidentCount: toolName === 'get_mcp_base_absCompanyProfileMain_getOrganAccidentCount',
    driverAccidentCount: toolName === 'get_mcp_ods_odsJituanBsEmployee_getDriverAccidentCount',
    accidentBusInfo: toolName === 'get_mcp_base_absBusProfileMain_getAccidentBusInfo',
  };
}

function hasOwn(record: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function copyAlias(record: Record<string, unknown>, sourceKey: string, aliasKey: string): void {
  if (!hasOwn(record, sourceKey) || record[sourceKey] === undefined || hasOwn(record, aliasKey)) {
    return;
  }
  record[aliasKey] = record[sourceKey];
}

function addText(record: Record<string, unknown>, key: string, value: string): void {
  if (!hasOwn(record, key)) {
    record[key] = value;
  }
}

function addProfileQuotaAliases(
  record: Record<string, unknown>,
  context: ToolSemanticContext,
  options: McpFieldSemanticsPatchOptions
): void {
  const looksLikeMetric =
    hasOwn(record, 'quotaId') ||
    hasOwn(record, 'quotaName') ||
    hasOwn(record, 'quotaLevel') ||
    hasOwn(record, 'parentId');
  let scoreWasMapped = false;
  let originalValueWasMapped = false;

  copyAlias(record, 'quotaId', 'metric_id');
  copyAlias(record, 'quotaName', 'metric_name');
  copyAlias(record, 'quotaLevel', 'metric_level');
  copyAlias(record, 'parentId', 'parent_metric_id');
  copyAlias(record, 'firstQuotaName', 'root_metric_name');
  copyAlias(record, 'weightRate', 'metric_weight_rate');
  copyAlias(record, 'riskData', 'raw_business_value');

  if (hasOwn(record, 'score')) {
    if (context.trend && hasOwn(record, 'ppartition') && !looksLikeMetric) {
      copyAlias(record, 'score', 'trend_source_metric_score');
      scoreWasMapped = true;
    } else if (context.suggestion || hasOwn(record, 'suggestedContent')) {
      copyAlias(record, 'score', 'source_metric_score');
      copyAlias(record, 'score', 'risk_priority_score');
      addText(record, 'score_semantics', PROFILE_SUGGESTION_SCORE_SEMANTICS);
      scoreWasMapped = true;
    } else if (looksLikeMetric) {
      copyAlias(record, 'score', 'source_metric_score');
      addText(record, 'score_semantics', PROFILE_SOURCE_SCORE_SEMANTICS);
      scoreWasMapped = true;
    } else if (context.profileQuery) {
      copyAlias(record, 'score', 'overall_risk_score');
      scoreWasMapped = true;
    }
  }

  if (hasOwn(record, 'originalValue')) {
    if (context.trend && hasOwn(record, 'ppartition') && !looksLikeMetric) {
      copyAlias(record, 'originalValue', 'trend_final_risk_score');
      copyAlias(record, 'originalValue', 'trend_final_risk_contribution');
    } else {
      if (!options.stripAmbiguousFields) {
        copyAlias(record, 'originalValue', 'original_value');
      }
      copyAlias(record, 'originalValue', 'final_risk_score');
      copyAlias(record, 'originalValue', 'final_risk_contribution');
    }
    addText(record, 'final_score_semantics', PROFILE_RISK_SCORE_SEMANTICS);
    originalValueWasMapped = true;
  }

  if (hasOwn(record, 'ppartition') && context.trend && !looksLikeMetric) {
    copyAlias(record, 'ppartition', 'trend_period_label');
  }

  if (options.stripAmbiguousFields) {
    if (scoreWasMapped) delete record.score;
    if (originalValueWasMapped) delete record.originalValue;
  }
}

function addPendingCountAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'pendingReceiveCount', 'pending_accept_suggestion_count');
  copyAlias(record, 'pendingConfirmCount', 'pending_intervention_count');
  copyAlias(record, 'pendingOptimizeCount', 'pending_optimization_count');
}

function addIdentityAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'organId', 'organization_id');
  copyAlias(record, 'organName', 'organization_name');
  copyAlias(record, 'routeId', 'route_id');
  copyAlias(record, 'routeIds', 'related_route_ids');
  copyAlias(record, 'routeName', 'route_name');
  copyAlias(record, 'employeeId', 'driver_id');
  copyAlias(record, 'driverId', 'driver_id');
  copyAlias(record, 'employeeCode', 'driver_code');
  copyAlias(record, 'employeeName', 'driver_name');
  copyAlias(record, 'driverName', 'driver_name');
  copyAlias(record, 'busId', 'vehicle_id');
  copyAlias(record, 'busName', 'vehicle_plate_no');
  copyAlias(record, 'numberPlate', 'vehicle_plate_no');
  copyAlias(record, 'busLicenseNum', 'vehicle_plate_no');
  copyAlias(record, 'busCode', 'vehicle_self_no');
  copyAlias(record, 'lineName', 'route_name');
  copyAlias(record, 'lineCode', 'route_code');
  copyAlias(record, 'busStationId', 'bus_station_id');
  copyAlias(record, 'busStationName', 'bus_station_name');
  copyAlias(record, 'manageOrgName', 'managing_org_name');
}

function addSuggestionAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'suggestedContent', 'management_suggestion');
  copyAlias(record, 'acceptStatu', 'accept_status_code');
  copyAlias(record, 'acceptStatu_dictText', 'accept_status_text');
  copyAlias(record, 'disposeStatu', 'dispose_status_code');
  copyAlias(record, 'disposeStatu_dictText', 'dispose_status_text');
  copyAlias(record, 'optimizeStatus', 'optimize_status_code');
  copyAlias(record, 'optimizeStatus_dictText', 'optimize_status_text');
  copyAlias(record, 'optimizeScoreBefore', 'risk_score_before_optimization');
  copyAlias(record, 'optimizeScore', 'risk_score_after_optimization');
}

function addRiskComparisonAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'currentRiskValue', 'current_raw_risk_value');
  copyAlias(record, 'convertedScore', 'current_converted_risk_score');
  copyAlias(record, 'previousPeriodRiskValue', 'mom_risk_value_change_rate_percent');
  copyAlias(record, 'previousPeriodScore', 'previous_period_converted_risk_score');
  copyAlias(record, 'lastYearSameDateRiskValue', 'yoy_risk_value_change_rate_percent');
  copyAlias(record, 'lastYearSameDateScore', 'last_year_same_date_converted_risk_score');
  copyAlias(record, 'organAvgRiskValue', 'organ_average_risk_value_change_rate_percent');
  copyAlias(record, 'organAvgScore', 'organ_average_converted_risk_score');
  copyAlias(record, 'routeAvgRiskValue', 'route_average_risk_value_change_rate_percent');
  copyAlias(record, 'routeAvgScore', 'route_average_converted_risk_score');
  copyAlias(record, 'previousPeriodRiskValue0', 'previous_period_raw_risk_value');
  copyAlias(record, 'lastYearSameDateRiskValue0', 'last_year_same_date_raw_risk_value');
  copyAlias(record, 'organAvgRiskValue0', 'organ_average_raw_risk_value');
  copyAlias(record, 'routeAvgRiskValue0', 'route_average_raw_risk_value');
  addText(record, 'risk_comparison_semantics', COMPARISON_SCORE_SEMANTICS);
}

function addListAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'records', 'current_page_records');
  copyAlias(record, 'total', 'total_record_count');
  copyAlias(record, 'totalCount', 'total_record_count');
  copyAlias(record, 'pageNo', 'page_number');
  copyAlias(record, 'pageSize', 'page_size');
}

function addBusinessListAliases(record: Record<string, unknown>, context: ToolSemanticContext): void {
  if (context.routeList || context.busList || context.busParkList || context.busStationList || context.employeeList) {
    copyAlias(record, 'organName', 'owning_org_name');
  }
  if (context.routeList) {
    copyAlias(record, 'busCount', 'registered_vehicle_count_on_route');
    copyAlias(record, 'driverCount', 'registered_driver_count_on_route');
  }
  if (context.busList || context.employeeList) {
    copyAlias(record, 'routeName', 'bound_route_name');
  }
  if (context.busParkList) {
    copyAlias(record, 'busParkName', 'bus_park_name');
    copyAlias(record, 'parkName', 'bus_park_name');
    copyAlias(record, 'serviceVehicleCount', 'service_vehicle_count');
    copyAlias(record, 'usingOrgCount', 'using_org_count');
  }
  if (context.busStationList) {
    copyAlias(record, 'stationType', 'station_type_code');
    copyAlias(record, 'stationType_dictText', 'station_type_text');
    copyAlias(record, 'stationProperties', 'station_property_code');
    copyAlias(record, 'stationProperties_dictText', 'station_property_text');
  }
}

function addBlackspotAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'blackType', 'blackspot_type_code');
  copyAlias(record, 'blackType_dictText', 'blackspot_type_text');
  copyAlias(record, 'eventType', 'event_type_code');
  copyAlias(record, 'eventLevel', 'event_level_code');
  copyAlias(record, 'eventLevel_dictText', 'event_level_text');
  copyAlias(record, 'eventCount', 'blackspot_event_count');
  copyAlias(record, 'clusterSize', 'clustered_event_count');
  copyAlias(record, 'startDate', 'warning_start_date');
  copyAlias(record, 'endDate', 'warning_end_date');
  copyAlias(record, 'longitude', 'longitude_wgs84_or_gcj02');
  copyAlias(record, 'latitude', 'latitude_wgs84_or_gcj02');
}

function addStatisticsAliases(record: Record<string, unknown>, context: ToolSemanticContext): void {
  if (context.organAccident) {
    copyAlias(record, 'accidentCount', 'organization_accident_count');
    copyAlias(record, 'accidentDescList', 'accident_description_page_items');
  }

  if (context.organAccidentCount) {
    copyAlias(record, 'accidentCount', 'organization_accident_count_in_window');
    copyAlias(record, 'trafficCount', 'organization_traffic_violation_count_in_window');
  }

  if (context.driverAccidentCount) {
    copyAlias(record, 'accidentCount', 'driver_accident_count_in_window');
    copyAlias(record, 'trafficCount', 'driver_traffic_violation_count_in_window');
    copyAlias(record, 'workTime', 'driver_work_hours_in_window');
    copyAlias(record, 'workDay', 'driver_work_days_in_window');
    copyAlias(record, 'workTimeOver', 'driver_overtime_hours_in_window');
    copyAlias(record, 'eventType', 'behavior_type_name');
    copyAlias(record, 'eventCount', 'behavior_event_count_in_behavior_window');
  }

  if (context.driverCheck) {
    copyAlias(record, 'allCount', 'planned_pre_trip_check_count');
    copyAlias(record, 'actualCount', 'actual_pre_trip_check_count');
    copyAlias(record, 'qualifiedCount', 'qualified_pre_trip_check_count');
    copyAlias(record, 'unqualifiedCount', 'unqualified_pre_trip_check_count');
    copyAlias(record, 'completePer', 'pre_trip_check_completion_rate_percent');
    copyAlias(record, 'unqualifiedPer', 'pre_trip_check_unqualified_rate_percent');
  }

  if (context.behaviorStat) {
    copyAlias(record, 'eventType', 'behavior_type_code');
    copyAlias(record, 'eventName', 'behavior_type_name');
    copyAlias(record, 'eventNum', 'behavior_event_count');
    copyAlias(record, 'ranking', 'behavior_count_rank');
  }

  copyAlias(record, 'ppartitionStart', 'statistics_start_date');
  copyAlias(record, 'ppartitionEnd', 'statistics_end_date');
}

function addAccidentListAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'accidentDate', 'accident_time');
  copyAlias(record, 'accidentPlace', 'accident_location');
  copyAlias(record, 'accidentDesc', 'accident_description');
  copyAlias(record, 'accidentLiability', 'liability_code');
  copyAlias(record, 'accidentLiability_dictText', 'liability_text');
  copyAlias(record, 'opinionStatus', 'handling_opinion_status_code');
  copyAlias(record, 'opinionStatus_dictText', 'handling_opinion_status_text');
  copyAlias(record, 'isBlackspot', 'is_blackspot_related');
}

function addAccidentBusInfoAliases(record: Record<string, unknown>): void {
  copyAlias(record, 'speed', 'accident_moment_speed');
  copyAlias(record, 'acceleration', 'accident_moment_acceleration');
  copyAlias(record, 'brakePedal', 'accident_moment_brake_pedal_percent');
  copyAlias(record, 'acceleratorPedal', 'accident_moment_accelerator_pedal_percent');
  copyAlias(record, 'gear', 'accident_moment_gear');
  copyAlias(record, 'gearAfter', 'post_accident_gear');
  copyAlias(record, 'blackSpotCount', 'related_blackspot_count');
  copyAlias(record, 'fault', 'vehicle_fault_info');
  copyAlias(record, 'maintainType', 'maintenance_type');
  copyAlias(record, 'maintainTime', 'maintenance_time');
  copyAlias(record, 'accidentDate', 'accident_time');
}

function patchRecord(
  record: Record<string, unknown>,
  context: ToolSemanticContext,
  options: McpFieldSemanticsPatchOptions
): Record<string, unknown> {
  addIdentityAliases(record);
  addListAliases(record);
  addProfileQuotaAliases(record, context, options);
  addPendingCountAliases(record);

  if (context.suggestion || hasOwn(record, 'suggestedContent')) addSuggestionAliases(record);
  if (context.riskComparison || hasOwn(record, 'currentRiskValue')) addRiskComparisonAliases(record);
  if (context.blackspot) addBlackspotAliases(record);
  if (context.routeList || context.busList || context.busParkList || context.busStationList || context.employeeList) {
    addBusinessListAliases(record, context);
  }
  if (
    context.organAccident ||
    context.organAccidentCount ||
    context.driverAccidentCount ||
    context.driverCheck ||
    context.behaviorStat
  ) {
    addStatisticsAliases(record, context);
  }
  if (context.accidentList) addAccidentListAliases(record);
  if (context.accidentBusInfo) addAccidentBusInfoAliases(record);

  return record;
}

function patchValue(value: unknown, context: ToolSemanticContext, options: McpFieldSemanticsPatchOptions): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => patchValue(item, context, options));
  }
  if (!isRecord(value)) {
    return value;
  }

  const cloned: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(value)) {
    cloned[key] = patchValue(child, context, options);
  }
  return patchRecord(cloned, context, options);
}

function buildTopLevelAliases(context: ToolSemanticContext): Record<string, string> {
  const aliases: Record<string, string> = {
    'score': '按所在对象解释；画像指标为 source_metric_score，画像 main 为 overall_risk_score，建议明细为 risk_priority_score',
    'originalValue': 'final_risk_score / final_risk_contribution',
    'weightRate': 'metric_weight_rate',
    'riskData': 'raw_business_value',
    'quotaId': 'metric_id',
    'quotaName': 'metric_name',
    'organId': 'organization_id',
    'organName': 'organization_name',
    'routeId': 'route_id',
    'routeName': 'route_name',
    'driverName': 'driver_name',
    'employeeName': 'driver_name',
    'busStationName': 'bus_station_name',
    'records': 'current_page_records',
    'total': 'total_record_count',
  };

  if (context.riskComparison) {
    Object.assign(aliases, {
      currentRiskValue: 'current_raw_risk_value',
      convertedScore: 'current_converted_risk_score',
      previousPeriodRiskValue: 'mom_risk_value_change_rate_percent',
      previousPeriodScore: 'previous_period_converted_risk_score',
      lastYearSameDateRiskValue: 'yoy_risk_value_change_rate_percent',
      lastYearSameDateScore: 'last_year_same_date_converted_risk_score',
      organAvgRiskValue: 'organ_average_risk_value_change_rate_percent',
      organAvgScore: 'organ_average_converted_risk_score',
      routeAvgRiskValue: 'route_average_risk_value_change_rate_percent',
      routeAvgScore: 'route_average_converted_risk_score',
    });
  }

  if (context.suggestion) {
    Object.assign(aliases, {
      suggestedContent: 'management_suggestion',
      acceptStatu: 'accept_status_code',
      acceptStatu_dictText: 'accept_status_text',
      disposeStatu: 'dispose_status_code',
      disposeStatu_dictText: 'dispose_status_text',
      optimizeStatus: 'optimize_status_code',
      optimizeStatus_dictText: 'optimize_status_text',
    });
  }

  if (context.trend) {
    Object.assign(aliases, {
      'quotaScores[].ppartition': 'trend_period_label',
      'quotaScores[].score': 'trend_source_metric_score',
      'quotaScores[].originalValue': 'trend_final_risk_score / trend_final_risk_contribution',
    });
  }

  if (context.blackspot) {
    Object.assign(aliases, {
      blackType: 'blackspot_type_code',
      blackType_dictText: 'blackspot_type_text',
      eventType: 'event_type_code',
      eventLevel: 'event_level_code',
      eventLevel_dictText: 'event_level_text',
      eventCount: 'blackspot_event_count',
      clusterSize: 'clustered_event_count',
      startDate: 'warning_start_date',
      endDate: 'warning_end_date',
      routeIds: 'related_route_ids',
    });
  }

  if (context.routeList) {
    Object.assign(aliases, {
      busCount: 'registered_vehicle_count_on_route',
      driverCount: 'registered_driver_count_on_route',
    });
  }

  if (context.driverCheck) {
    Object.assign(aliases, {
      allCount: 'planned_pre_trip_check_count',
      actualCount: 'actual_pre_trip_check_count',
      qualifiedCount: 'qualified_pre_trip_check_count',
      unqualifiedCount: 'unqualified_pre_trip_check_count',
      completePer: 'pre_trip_check_completion_rate_percent',
      unqualifiedPer: 'pre_trip_check_unqualified_rate_percent',
    });
  }

  if (context.behaviorStat) {
    Object.assign(aliases, {
      eventType: 'behavior_type_code',
      eventName: 'behavior_type_name',
      eventNum: 'behavior_event_count',
      ranking: 'behavior_count_rank',
    });
  }

  if (context.organAccident) {
    Object.assign(aliases, {
      accidentCount: 'organization_accident_count',
      accidentDescList: 'accident_description_page_items',
    });
  }

  if (context.organAccidentCount) {
    Object.assign(aliases, {
      accidentCount: 'organization_accident_count_in_window',
      trafficCount: 'organization_traffic_violation_count_in_window',
    });
  }

  if (context.driverAccidentCount) {
    Object.assign(aliases, {
      accidentCount: 'driver_accident_count_in_window',
      trafficCount: 'driver_traffic_violation_count_in_window',
      workTime: 'driver_work_hours_in_window',
      workDay: 'driver_work_days_in_window',
      workTimeOver: 'driver_overtime_hours_in_window',
      'behaviorCounts[].eventType': 'behavior_type_name',
      'behaviorCounts[].eventCount': 'behavior_event_count_in_behavior_window',
    });
  }

  if (context.accidentList) {
    Object.assign(aliases, {
      accidentDate: 'accident_time',
      accidentPlace: 'accident_location',
      accidentDesc: 'accident_description',
      lineName: 'route_name',
      busLicenseNum: 'vehicle_plate_no',
      busCode: 'vehicle_self_no',
      accidentLiability: 'liability_code',
      accidentLiability_dictText: 'liability_text',
      opinionStatus: 'handling_opinion_status_code',
      opinionStatus_dictText: 'handling_opinion_status_text',
      isBlackspot: 'is_blackspot_related',
    });
  }

  if (context.accidentBusInfo) {
    Object.assign(aliases, {
      speed: 'accident_moment_speed',
      acceleration: 'accident_moment_acceleration',
      brakePedal: 'accident_moment_brake_pedal_percent',
      acceleratorPedal: 'accident_moment_accelerator_pedal_percent',
      gear: 'accident_moment_gear',
      gearAfter: 'post_accident_gear',
      blackSpotCount: 'related_blackspot_count',
      fault: 'vehicle_fault_info',
      maintainType: 'maintenance_type',
      maintainTime: 'maintenance_time',
      accidentDate: 'accident_time',
    });
  }

  return aliases;
}

function buildTopLevelSemantics(context: ToolSemanticContext): Record<string, string> {
  return {
    patch: `${MCP_FIELD_ALIAS_PATCH_ID}: temporary compatibility aliases added by agent before MCP schema is fixed.`,
    risk_direction: RISK_DIRECTION_SEMANTICS,
    source_metric_score: PROFILE_SOURCE_SCORE_SEMANTICS,
    final_risk_score: PROFILE_RISK_SCORE_SEMANTICS,
    originalValue: PROFILE_WEIGHTED_VALUE_SEMANTICS,
    count_fields: PROFILE_COUNT_SEMANTICS,
    ...(context.riskComparison ? { risk_comparison: COMPARISON_SCORE_SEMANTICS } : {}),
    ...(context.trend
      ? {
          trend_scores:
            '趋势点中 score/trend_source_metric_score 是源指标分；originalValue/trend_final_risk_score 是最终风险分或最终风险贡献。',
        }
      : {}),
    ...(context.suggestion ? { suggestion_score: PROFILE_SUGGESTION_SCORE_SEMANTICS } : {}),
    ...(context.routeList || context.busList || context.busParkList || context.busStationList || context.employeeList
      ? { pagination: CURRENT_PAGE_SEMANTICS }
      : {}),
    ...(context.organAccident ? { accident_description_page_items: CURRENT_PAGE_SEMANTICS } : {}),
    ...(context.driverAccidentCount
      ? { window_fields: 'day 作用于事故/违章统计窗口，behaviorDay 作用于 behaviorCounts 行为统计窗口。' }
      : {}),
  };
}

function buildUsageWarnings(context: ToolSemanticContext): string[] {
  const warnings = [
    '如果同一对象同时有 score 和 originalValue/final_risk_score，解释最终风险分或风险贡献时优先使用 originalValue/final_risk_score；score 只保留为源指标分或中间分。',
    '所有风险值、风险分、风险贡献默认都是数值越高风险越高，不是安全分。',
  ];

  if (context.riskComparison) {
    warnings.push(
      'previousPeriodRiskValue、lastYearSameDateRiskValue、organAvgRiskValue、routeAvgRiskValue 是变化率/差异率，不是上期、去年同期、机构均值或线路均值的绝对分数；对比绝对分数使用 previousPeriodScore、lastYearSameDateScore、organAvgScore、routeAvgScore。'
    );
  }

  if (
    context.routeList ||
    context.busList ||
    context.busParkList ||
    context.busStationList ||
    context.employeeList ||
    context.organAccident
  ) {
    warnings.push(
      'records 或 accidentDescList 只代表当前页明细；回答总数必须使用 total/total_record_count 或专门 count 字段。'
    );
  }

  if (context.driverAccidentCount) {
    warnings.push('day 是事故/违章统计窗口，behaviorDay 是 behaviorCounts 行为统计窗口。');
  }

  return warnings;
}

function attachTopLevelMetadata(value: unknown, context: ToolSemanticContext): unknown {
  const metadata = {
    _mcpFieldAliasPatch: MCP_FIELD_ALIAS_PATCH_ID,
    _mcpFieldAliases: buildTopLevelAliases(context),
    _mcpFieldSemantics: buildTopLevelSemantics(context),
    _mcpUsageWarnings: buildUsageWarnings(context),
  };

  if (Array.isArray(value)) {
    return { result: value, ...metadata };
  }
  if (isRecord(value)) {
    return {
      ...value,
      ...Object.fromEntries(Object.entries(metadata).filter(([key]) => !hasOwn(value, key))),
    };
  }
  return value;
}

export function applyMcpFieldSemanticsPatch(
  toolName: string,
  data: unknown,
  options: McpFieldSemanticsPatchOptions = {}
): unknown {
  const context = buildContext(toolName);
  if (!context) return data;

  // TODO(ai-security-mcp-field-alias-hotfix): Remove this compatibility layer
  // once MCP outputs fieldAliases/fieldSemantics or unambiguous field names.
  return attachTopLevelMetadata(patchValue(data, context, options), context);
}
