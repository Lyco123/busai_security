import {
  isMissingGuangdongVehiclePlateSeries,
  normalizeGuangdongVehiclePlate,
} from '../../shared/vehicle-plate-normalizer';

type WorkerToolNameForValidation =
  | 'generate_driver_report'
  | 'generate_vehicle_report'
  | 'generate_unit_report'
  | 'generate_route_report'
  | 'generate_station_report'
  | 'generate_accident_investigation_report'
  | 'consult_omni'
  | 'consult_driver_expert'
  | 'consult_vehicle_expert'
  | 'consult_unit_expert'
  | 'consult_route_expert'
  | 'consult_station_expert'
  | 'consult_incident_expert'
  | 'rule_reply'
  | 'rule_asker'
  | 'rule_builder';

export interface WorkerToolCallForValidation {
  tool: WorkerToolNameForValidation;
  args: Record<string, unknown>;
}

const GENERIC_PLACEHOLDER_ARGS = new Set([
  '参数',
  '缺少参数',
  '待补充',
  'unknown',
  'none',
  'null',
  'n/a',
  'na',
  'xxx',
  'xxxx',
]);

const DRIVER_PLACEHOLDER_ARGS = new Set([
  'driver_name',
  'drivername',
  '驾驶员',
  '驾驶员姓名',
  '驾驶员名称',
  '司机姓名',
  '安全',
  '风险',
  '报告',
  '画像',
  '模板',
  '管理人员版',
]);

const VEHICLE_PLACEHOLDER_ARGS = new Set([
  'vehicle_id',
  'vehicleid',
  '车辆',
  '车辆id',
  '车牌',
  '车牌号',
  '车牌号或车辆id',
  '车辆id或车牌号',
]);

const ROUTE_PLACEHOLDER_ARGS = new Set([
  'route_name',
  'routename',
  '线路',
  '线路名',
  '线路名称',
  '线路名称或线路编号',
]);

const STATION_PLACEHOLDER_ARGS = new Set([
  'station',
  'busstation',
  'station_name',
  'stationname',
  '站场',
  '站场名称',
]);

const UNIT_PLACEHOLDER_ARGS = new Set([
  'unit',
  'organ',
  'organization',
  'company',
  'organ_name',
  'organname',
  '单位',
  '单位名称',
  '机构',
  '机构名称',
  '公司',
  '分公司',
  '集团',
]);

function normalizeArgToken(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[“”"'`]/g, '')
    .replace(/[（）()【】\[\]<>《》]/g, '')
    .replace(/\s+/g, '');
}

function looksLikeIntentPhrase(value: string): boolean {
  return /^(请|帮我|给我|麻烦|查询|查下|查看|获取|生成|做|出|提供)/.test(value.trim());
}

function isGenericPlaceholderArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) {
    return true;
  }
  const normalized = normalizeArgToken(trimmed);
  if (!normalized) {
    return true;
  }
  if (GENERIC_PLACEHOLDER_ARGS.has(normalized)) {
    return true;
  }
  if (/^x{2,}$/i.test(normalized)) {
    return true;
  }
  if (/^\{.+\}$/.test(trimmed) || /^<.+>$/.test(trimmed) || /^\[.+\]$/.test(trimmed)) {
    return true;
  }
  return false;
}

function isInvalidDriverNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) {
    return true;
  }
  if (DRIVER_PLACEHOLDER_ARGS.has(normalized)) {
    return true;
  }
  if (looksLikeIntentPhrase(trimmed)) {
    return true;
  }
  if (/(安全报告|驾驶员报告|报告|画像|分析|评估)/.test(trimmed)) {
    return true;
  }
  return false;
}

function isInvalidVehicleIdArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) {
    return true;
  }
  if (VEHICLE_PLACEHOLDER_ARGS.has(normalized)) {
    return true;
  }
  if (
    /(\u96c6\u56e2|\u516c\u53f8|\u603b\u516c\u53f8|\u5206\u516c\u53f8|\u8f66\u961f|\u8f66\u961f\u96c6\u56e2)/.test(
      trimmed
    ) ||
    normalized.includes('group') ||
    normalized.includes('company') ||
    normalized.includes('fleet')
  ) {
    return true;
  }
  if (normalized.includes('车牌号') && normalized.includes('车辆id')) {
    return true;
  }
  if (looksLikeIntentPhrase(trimmed)) {
    return true;
  }
  if (/(车辆安全报告|车辆报告|报告|画像|分析|评估)/.test(trimmed)) {
    return true;
  }
  return false;
}

function isLikelyIncompleteVehicleArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  if (/^[\u4e00-\u9fa5A-Za-z]$/.test(trimmed)) {
    return true;
  }
  const normalized = normalizeArgToken(trimmed);
  if (isMissingGuangdongVehiclePlateSeries(trimmed)) {
    return true;
  }
  if (/^\d{1,3}$/.test(normalized)) {
    return true;
  }
  if (/^[a-z]{1,2}\d{0,2}$/i.test(normalized)) {
    return true;
  }
  if (/^[a-z]{1,3}-?\d{0,2}$/i.test(normalized)) {
    return true;
  }
  return false;
}

function isLikelyIncompleteDriverArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  if (/^[\u4e00-\u9fa5A-Za-z]$/.test(trimmed)) {
    return true;
  }
  const normalized = normalizeArgToken(trimmed);
  if (/^\d{1,3}$/.test(normalized)) {
    return true;
  }
  if (/^[a-z]\d{0,2}$/i.test(normalized)) {
    return true;
  }
  return false;
}

function isInvalidUnitNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) {
    return true;
  }
  if (UNIT_PLACEHOLDER_ARGS.has(normalized)) {
    return true;
  }
  if (looksLikeIntentPhrase(trimmed)) {
    return true;
  }
  if (/(单位报告|安全报告|报告|画像|分析|评估)/.test(trimmed)) {
    return true;
  }
  return false;
}

function isStandaloneFleetNameArg(value: string): boolean {
  return /^(?:第)?(?:\d+|[一二三四五六七八九十]+)车队$/u.test(
    value.normalize('NFKC').replace(/\s+/g, '').trim()
  );
}

function isLikelyIncompleteUnitArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  if (/^[\u4e00-\u9fa5A-Za-z]$/.test(trimmed)) {
    return true;
  }
  if (isStandaloneFleetNameArg(trimmed)) {
    return true;
  }
  return UNIT_PLACEHOLDER_ARGS.has(normalizeArgToken(trimmed));
}

function isInvalidRouteNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) {
    return true;
  }
  if (ROUTE_PLACEHOLDER_ARGS.has(normalized)) {
    return true;
  }
  if (looksLikeIntentPhrase(trimmed)) {
    return true;
  }
  if (/(线路报告|报告|画像|分析|评估)/.test(trimmed)) {
    return true;
  }
  return false;
}

function isInvalidStationNameArg(value: string): boolean {
  const trimmed = value.trim();
  const normalized = normalizeArgToken(trimmed);
  if (isGenericPlaceholderArg(trimmed)) {
    return true;
  }
  if (STATION_PLACEHOLDER_ARGS.has(normalized)) {
    return true;
  }
  if (looksLikeIntentPhrase(trimmed)) {
    return true;
  }
  if (/(站场报告|报告|画像|分析|评估)/.test(trimmed)) {
    return true;
  }
  return false;
}

function isLikelyIncompleteStationArg(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  if (/^[\u4e00-\u9fa5A-Za-z]$/.test(trimmed)) {
    return true;
  }
  return STATION_PLACEHOLDER_ARGS.has(normalizeArgToken(trimmed));
}

export function validateToolCall(
  toolCall: WorkerToolCallForValidation,
  extractRuleIdFromRuleReplyArgs: (args: Record<string, unknown>) => string
): { ok: true } | { ok: false; prompt: string; handling?: 'ask_user' | 'retry_router' } {
  if (
    toolCall.tool === 'consult_omni' ||
    toolCall.tool === 'consult_driver_expert' ||
    toolCall.tool === 'consult_vehicle_expert' ||
    toolCall.tool === 'consult_unit_expert' ||
    toolCall.tool === 'consult_route_expert' ||
    toolCall.tool === 'consult_station_expert' ||
    toolCall.tool === 'consult_incident_expert'
  ) {
    const query = String(toolCall.args.query ?? '').trim();
    if (!query) {
      return { ok: false, prompt: '请提供你想咨询的问题或背景信息。' };
    }
    return { ok: true };
  }

  if (toolCall.tool === 'generate_driver_report') {
    const name = String(toolCall.args.driver_name ?? '').trim();
    if (!name || isInvalidDriverNameArg(name) || isLikelyIncompleteDriverArg(name)) {
      return { ok: false, prompt: '请提供驾驶员姓名（例如“张三”），我再为你生成驾驶员安全报告。' };
    }
    return { ok: true };
  }

  if (toolCall.tool === 'generate_vehicle_report') {
    const id = normalizeGuangdongVehiclePlate(toolCall.args.numberPlate);
    if (!id || isInvalidVehicleIdArg(id) || isLikelyIncompleteVehicleArg(id)) {
      return {
        ok: false,
        prompt:
          '请提供完整车牌号或车辆ID（例如“粤A12345”“粤A12345D”“BUS-102”或“vehicle-001”），我再为你生成车辆安全报告。',
      };
    }
    return { ok: true };
  }

  if (toolCall.tool === 'generate_unit_report') {
    const name = String(toolCall.args.organ_name ?? '').trim();
    if (!name || isInvalidUnitNameArg(name) || isLikelyIncompleteUnitArg(name)) {
      return {
        ok: false,
        prompt: isStandaloneFleetNameArg(name)
          ? '请补充分公司名称后再生成车队安全报告，例如“二分公司-二车队”或“巴集二分第二车队”。'
          : '请提供完整单位名称（例如“二巴公司”），我再为你生成单位安全报告。',
      };
    }
    return { ok: true };
  }

  if (toolCall.tool === 'generate_route_report') {
    const name = String(toolCall.args.route_name ?? '').trim();
    if (!name || isInvalidRouteNameArg(name)) {
      return {
        ok: false,
        prompt: '请提供线路名称或线路编号（例如“1路”），我再为你生成线路安全报告。',
      };
    }
    return { ok: true };
  }

  if (toolCall.tool === 'generate_station_report') {
    const name = String(toolCall.args.station_name ?? '').trim();
    if (!name || isInvalidStationNameArg(name) || isLikelyIncompleteStationArg(name)) {
      return {
        ok: false,
        prompt: '请提供完整站场名称（例如“体育中心站场”），我再为你生成站场安全报告。',
      };
    }
    return { ok: true };
  }

  if (toolCall.tool === 'generate_accident_investigation_report') {
    const driverName = String(toolCall.args.driver_name ?? '').trim();
    const accidentDate = String(toolCall.args.accident_date ?? '').trim();
    if (!driverName) {
      return {
        ok: false,
        prompt: '请提供肇事驾驶员姓名和事故发生时间（格式 yyyyMMddHHmmss），便于生成调查及整改报告。',
      };
    }
    if (!accidentDate) {
      return { ok: false, prompt: '请补充事故发生时间（格式 yyyyMMddHHmmss），便于生成调查及整改报告。' };
    }
    if (!/^\d{14}$/.test(accidentDate)) {
      return { ok: false, prompt: '事故发生时间格式应为 yyyyMMddHHmmss，例如 20251231050505。' };
    }
    return { ok: true };
  }

  if (toolCall.tool === 'rule_reply') {
    const userQuery = String(toolCall.args.user_query ?? '').trim();
    if (!userQuery) {
      return {
        ok: false,
        prompt: 'rule_reply requires user_query; ask the router to choose another tool.',
        handling: 'retry_router',
      };
    }
    const ruleId = extractRuleIdFromRuleReplyArgs(toolCall.args);
    if (!ruleId) {
      return {
        ok: false,
        prompt:
          'rule_reply requires an explicit matched rule_id from this turn. No concrete rule was selected, so choose another tool instead of calling rule_reply.',
        handling: 'retry_router',
      };
    }
    return { ok: true };
  }

  return { ok: true };
}
