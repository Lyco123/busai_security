import { isRecord } from './guards';
import { callMcpToolForAgent } from './mcp';
import { withMessageSources } from './message-sources';
import { PROFILE_SUGGESTION_SCORE_SEMANTICS } from './profile-quota-tree';

export const ACCIDENT_INVESTIGATION_MCP_TOOL_NAME =
  'get_mcp_ods_odsJituanBsEmployee_getAccidentList';

const ACCIDENT_DRIVER_STAT_TOOL_NAME = 'get_mcp_ods_odsJituanBsEmployee_getDriverAccidentCount';
const ACCIDENT_BEHAVIOR_STAT_TOOL_NAME = 'get_mcp_ods_odsJituanBsEmployee_getBehaviorStat';
const ACCIDENT_UNIT_STAT_TOOL_NAME = 'get_mcp_ods_odsJituanBsEmployee_getOrganAccident';
const DRIVER_SUGGESTION_TOOL_NAME =
  'get_mcp_suggest_absDriverSuggestedSub_queryByDriverNameAndDate';
const ROUTE_SUGGESTION_TOOL_NAME = 'get_mcp_suggest_absRouteSuggestedSub_queryByRouteNameAndDate';
const BUS_SUGGESTION_TOOL_NAME = 'get_mcp_suggest_absBusSuggestedSub_queryByBusNameAndDate';

const SHANGHAI_TIME_ZONE = 'Asia/Shanghai';

type EnvLike = {
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
};

type AccidentInvestigationFetchResult =
  | { success: true; data: Record<string, unknown> }
  | { success: false; error: 'mcp_lookup_failed' | 'incident_not_found'; detail?: string };

type AccidentListToolLookup =
  | { success: true; data: Record<string, unknown> }
  | { success: false; error?: string };

type AccidentSuggestionItem = {
  quotaName: string;
  suggestedContent: string;
  score: number | null;
  firstQuotaName: string | null;
  suggestedDate: string | null;
  acceptStatus: string | null;
  disposeStatus: string | null;
};

function buildAccidentDate(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: SHANGHAI_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const year = parts.find((item) => item.type === 'year')?.value ?? '';
  const month = parts.find((item) => item.type === 'month')?.value ?? '';
  const day = parts.find((item) => item.type === 'day')?.value ?? '';
  const hour = parts.find((item) => item.type === 'hour')?.value ?? '00';
  const minute = parts.find((item) => item.type === 'minute')?.value ?? '00';
  const second = parts.find((item) => item.type === 'second')?.value ?? '00';
  return `${year}${month}${day}${hour}${minute}${second}`;
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

function normalizeAccidentDateToken(value: unknown): string | null {
  const raw = toStringValue(value);
  if (!raw) return null;
  const digits = raw.replace(/\D/g, '');
  return digits.length >= 14 ? digits.slice(0, 14) : digits || null;
}

function formatCompactAccidentDate(value: string): string | null {
  const normalized = normalizeAccidentDateToken(value);
  if (!normalized || normalized.length !== 14) return null;
  return `${normalized.slice(0, 4)}-${normalized.slice(4, 6)}-${normalized.slice(6, 8)} ${normalized.slice(8, 10)}:${normalized.slice(10, 12)}:${normalized.slice(12, 14)}`;
}

function formatPartitionDate(value: string): string | null {
  const normalized = normalizeAccidentDateToken(value);
  if (!normalized || normalized.length < 8) return null;
  return normalized.slice(0, 8);
}

function readAccidentRecordDate(record: Record<string, unknown>): string | null {
  const basic = isRecord(record.basic) ? record.basic : null;
  return normalizeAccidentDateToken(
    record.accidentDate ??
      record.accident_date ??
      record.accidentTime ??
      record.accident_time ??
      record.ppartition ??
      basic?.accident_date ??
      basic?.accidentDate ??
      basic?.accident_time
  );
}

function isSameAccidentDate(left: string | null, right: string | null): boolean {
  if (!left || !right) return false;
  if (left === right) return true;
  const minLength = Math.min(left.length, right.length);
  if (minLength >= 12 && left.slice(0, minLength) === right.slice(0, minLength)) {
    return true;
  }
  return left.length >= 12 && right.length >= 12 && left.slice(0, 12) === right.slice(0, 12);
}

function isAccidentListRecord(value: Record<string, unknown>): boolean {
  const basic = isRecord(value.basic) ? value.basic : null;
  return Boolean(
    value.accidentDesc ??
      value.accidentDate ??
      value.accidentNo ??
      value.driverName ??
      value.busLicenseNum ??
      basic?.accident_date ??
      basic?.driver_name
  );
}

function getFirstRecordFromArray(value: unknown, accidentDate: string): Record<string, unknown> | null {
  if (!Array.isArray(value)) return null;
  const records = value.filter(isRecord);
  const normalizedDate = normalizeAccidentDateToken(accidentDate);
  const matched = normalizedDate
    ? records.find((record) => isSameAccidentDate(readAccidentRecordDate(record), normalizedDate))
    : null;
  if (matched) return matched;
  return records.length === 1 ? records[0] : null;
}

function extractAccidentListRecord(payload: unknown, accidentDate: string): Record<string, unknown> | null {
  if (Array.isArray(payload)) {
    return getFirstRecordFromArray(payload, accidentDate);
  }
  if (!isRecord(payload)) {
    return null;
  }
  if (isAccidentListRecord(payload)) {
    return payload;
  }

  const nestedCandidates = [
    payload.records,
    payload.list,
    payload.rows,
    payload.data,
    payload.items,
    payload.result,
  ];
  for (const candidate of nestedCandidates) {
    const nestedRecord = extractAccidentListRecord(candidate, accidentDate);
    if (nestedRecord) {
      return nestedRecord;
    }
  }

  return null;
}

function normalizeSuggestionItems(value: unknown): AccidentSuggestionItem[] {
  const rawItems =
    isRecord(value) && Array.isArray(value.result)
      ? value.result
      : Array.isArray(value)
        ? value
        : [];
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

function extractOrganNameFromAccidentData(data: Record<string, unknown>): string | null {
  const basic = isRecord(data.basic) ? data.basic : null;
  if (basic) {
    return (
      toStringValue(basic.organization) ??
      toStringValue(basic.organName) ??
      toStringValue(basic.organ_name)
    );
  }
  return (
    toStringValue(data.organization) ??
    toStringValue(data.organName) ??
    toStringValue(data.organ_name)
  );
}

function extractRouteNameFromAccidentData(data: Record<string, unknown>): string | null {
  const basic = isRecord(data.basic) ? data.basic : null;
  if (basic) {
    const fromBasic =
      toStringValue(basic.route_name) ??
      toStringValue(basic.routeName) ??
      toStringValue(basic.line_name) ??
      toStringValue(basic.lineName);
    if (fromBasic) return fromBasic;
  }
  const section2 = isRecord(data.section_2) ? data.section_2 : null;
  const section2Investigation = isRecord(data.section_2_investigation)
    ? data.section_2_investigation
    : null;
  const investigationSource = section2 ?? section2Investigation;
  if (investigationSource) {
    return (
      toStringValue(investigationSource.route_name) ??
      toStringValue(investigationSource.routeName) ??
      toStringValue(investigationSource.line_name) ??
      toStringValue(investigationSource.lineName)
    );
  }
  return (
    toStringValue(data.route_name) ??
    toStringValue(data.routeName) ??
    toStringValue(data.line_name) ??
    toStringValue(data.lineName)
  );
}

function extractBusPlateFromAccidentData(data: Record<string, unknown>): string | null {
  const basic = isRecord(data.basic) ? data.basic : null;
  if (basic) {
    const fromBasic =
      toStringValue(basic.vehicle_plate) ??
      toStringValue(basic.numberPlate) ??
      toStringValue(basic.busLicenseNum);
    if (fromBasic) return fromBasic;
  }
  const section2 = isRecord(data.section_2) ? data.section_2 : null;
  const section2Investigation = isRecord(data.section_2_investigation)
    ? data.section_2_investigation
    : null;
  const investigationSource = section2 ?? section2Investigation;
  if (investigationSource) {
    const vehicleInfo = isRecord(investigationSource.vehicle_info)
      ? investigationSource.vehicle_info
      : null;
    if (vehicleInfo) {
      return (
        toStringValue(vehicleInfo.number_plate) ??
        toStringValue(vehicleInfo.numberPlate) ??
        toStringValue(vehicleInfo.busLicenseNum)
      );
    }
  }
  return (
    toStringValue(data.number_plate) ??
    toStringValue(data.numberPlate) ??
    toStringValue(data.busLicenseNum)
  );
}

function buildAccidentSuggestionPayload(
  driverSuggestions: AccidentSuggestionItem[],
  routeSuggestions: AccidentSuggestionItem[],
  busSuggestions: AccidentSuggestionItem[]
): Record<string, unknown> {
  return {
    driver_suggestions: driverSuggestions.slice(0, 4).map((item) => ({
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
    route_suggestions: routeSuggestions.slice(0, 4).map((item) => ({
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
    bus_suggestions: busSuggestions.slice(0, 4).map((item) => ({
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
  };
}

export function adaptAccidentInvestigationToolResult(
  mainResult: Record<string, unknown>,
  driverStatResult: unknown,
  behaviorStatResult: unknown,
  unitStatResult: unknown,
  driverSuggestionResult?: unknown,
  routeSuggestionResult?: unknown,
  busSuggestionResult?: unknown
): Record<string, unknown> {
  const driverSuggestions = normalizeSuggestionItems(driverSuggestionResult);
  const routeSuggestions = normalizeSuggestionItems(routeSuggestionResult);
  const busSuggestions = normalizeSuggestionItems(busSuggestionResult);

  const suggestionPayload = buildAccidentSuggestionPayload(
    driverSuggestions,
    routeSuggestions,
    busSuggestions
  );

  const merged = {
    ...mainResult,
    driver_stat: driverStatResult ?? null,
    behavior_stat: behaviorStatResult ?? null,
    unit_stat: unitStatResult ?? null,
    suggestions: suggestionPayload,
    appendix: {
      ...(isRecord(mainResult.appendix) ? mainResult.appendix : {}),
      raw_data: {
        ...(isRecord(mainResult.appendix) && isRecord(mainResult.appendix.raw_data)
          ? mainResult.appendix.raw_data
          : {}),
        source: `mcp:${ACCIDENT_INVESTIGATION_MCP_TOOL_NAME}`,
        score_semantics: PROFILE_SUGGESTION_SCORE_SEMANTICS,
        supplementary_sources: {
          driver_stat: driverStatResult ? `mcp:${ACCIDENT_DRIVER_STAT_TOOL_NAME}` : null,
          behavior_stat: behaviorStatResult ? `mcp:${ACCIDENT_BEHAVIOR_STAT_TOOL_NAME}` : null,
          unit_stat: unitStatResult ? `mcp:${ACCIDENT_UNIT_STAT_TOOL_NAME}` : null,
          driver_suggestions:
            driverSuggestions.length > 0 ? `mcp:${DRIVER_SUGGESTION_TOOL_NAME}` : null,
          route_suggestions:
            routeSuggestions.length > 0 ? `mcp:${ROUTE_SUGGESTION_TOOL_NAME}` : null,
          bus_suggestions: busSuggestions.length > 0 ? `mcp:${BUS_SUGGESTION_TOOL_NAME}` : null,
        },
      },
    },
  };

  return merged;
}

async function callAccidentListTool(
  env: EnvLike,
  driverName: string,
  accidentDate: string
): Promise<AccidentListToolLookup> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  const config = {
    serverUrl,
    clientId: env.CF_ACCESS_CLIENT_ID,
    clientSecret: env.CF_ACCESS_CLIENT_SECRET,
    accessToken: env.MCP_ACCESS_TOKEN,
  };
  const formattedAccidentDate = formatCompactAccidentDate(accidentDate);
  const attempts: Record<string, unknown>[] = [
    {
      driverName,
      accidentDate,
      pageNo: '1',
      pageSize: '20',
    },
    {
      driver_name: driverName,
      accident_date: accidentDate,
      pageNo: '1',
      pageSize: '20',
    },
    {
      driverName,
      accidentDate,
    },
    ...(formattedAccidentDate
      ? [
          {
            driverName,
            accidentDate: formattedAccidentDate,
            pageNo: '1',
            pageSize: '20',
          },
          {
            driver_name: driverName,
            accident_date: formattedAccidentDate,
            pageNo: '1',
            pageSize: '20',
          },
        ]
      : []),
    {
      driverName,
      pageNo: '1',
      pageSize: '20',
    },
  ];

  let lastToolError: string | undefined;
  let sawSuccessfulResponse = false;
  for (const args of attempts) {
    const result = await callMcpToolForAgent(config, ACCIDENT_INVESTIGATION_MCP_TOOL_NAME, args);
    if (!result.success) {
      lastToolError = result.error;
      continue;
    }
    sawSuccessfulResponse = true;

    const resultData = isRecord(result.data) ? result.data : null;
    const payload = resultData && 'result' in resultData ? resultData.result : resultData;
    const mainPayload = extractAccidentListRecord(payload, accidentDate);

    if (!mainPayload) {
      continue;
    }

    return {
      success: true,
      data: withMessageSources(mainPayload, [
        {
          type: 'mcp_tool',
          path: '/ods/odsJituanBsEmployee/getAccidentList',
          path_args: args,
          tool_name: ACCIDENT_INVESTIGATION_MCP_TOOL_NAME,
          driver_name: driverName,
          accidentDate,
          provider_mode: 'mcp',
        },
      ]),
    };
  }

  return {
    success: false,
    ...(!sawSuccessfulResponse && lastToolError ? { error: lastToolError } : {}),
  };
}

async function callSupplementaryTool(
  env: EnvLike,
  toolName: string,
  args: Record<string, string>
): Promise<unknown> {
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';

  const result = await callMcpToolForAgent(
    {
      serverUrl,
      clientId: env.CF_ACCESS_CLIENT_ID,
      clientSecret: env.CF_ACCESS_CLIENT_SECRET,
      accessToken: env.MCP_ACCESS_TOKEN,
    },
    toolName,
    args
  );

  return result.success ? result.data : undefined;
}

async function fetchAccidentSupplementaryAndAdapt(
  env: EnvLike,
  mainData: Record<string, unknown>,
  driverName: string,
  accidentDate: string
): Promise<Record<string, unknown>> {
  const routeName = extractRouteNameFromAccidentData(mainData);
  const busPlate = extractBusPlateFromAccidentData(mainData);
  const organName = extractOrganNameFromAccidentData(mainData);
  const ppartition = formatPartitionDate(accidentDate) ?? accidentDate;

  const driverStatResult = await callSupplementaryTool(
    env,
    ACCIDENT_DRIVER_STAT_TOOL_NAME,
    { driverName, ppartition, day: '365', behaviorDay: '30', pageNo: '1', pageSize: '20' }
  );

  const behaviorStatResult = await callSupplementaryTool(
    env,
    ACCIDENT_BEHAVIOR_STAT_TOOL_NAME,
    { driverName, ppartition, day: '30', pageNo: '1', pageSize: '20' }
  );

  const unitStatResult = organName
    ? await callSupplementaryTool(env, ACCIDENT_UNIT_STAT_TOOL_NAME, { organName })
    : undefined;

  const driverSuggestionResult = await callSupplementaryTool(
    env,
    DRIVER_SUGGESTION_TOOL_NAME,
    { driverName, accidentDate, pageNo: '1', pageSize: '20' }
  );

  const routeSuggestionResult = routeName
      ? await callSupplementaryTool(
        env,
        ROUTE_SUGGESTION_TOOL_NAME,
        { routeName, accidentDate, pageNo: '1', pageSize: '20' }
      )
    : undefined;

  const busSuggestionResult = busPlate
      ? await callSupplementaryTool(
        env,
        BUS_SUGGESTION_TOOL_NAME,
        { numberPlate: busPlate, accidentDate, pageNo: '1', pageSize: '20' }
      )
    : undefined;

  return adaptAccidentInvestigationToolResult(
    mainData,
    driverStatResult ?? undefined,
    behaviorStatResult ?? undefined,
    unitStatResult ?? undefined,
    driverSuggestionResult,
    routeSuggestionResult,
    busSuggestionResult
  );
}

export async function fetchAccidentInvestigationByDriverAndDate(
  env: EnvLike,
  driverName: string,
  accidentDate: string
): Promise<Record<string, unknown> | null> {
  const result = await fetchAccidentInvestigationByDriverAndDateResult(
    env,
    driverName,
    accidentDate
  );
  return result.success ? result.data : null;
}

export async function fetchAccidentInvestigationByDriverAndDateResult(
  env: EnvLike,
  driverName: string,
  accidentDate: string
): Promise<AccidentInvestigationFetchResult> {
  const trimmedDriverName = toStringValue(driverName);
  const trimmedAccidentDate = toStringValue(accidentDate) ?? buildAccidentDate();
  const serverUrl = typeof env.MCP_SERVER_URL === 'string' ? env.MCP_SERVER_URL.trim() : '';
  if (!serverUrl || !trimmedDriverName) {
    return {
      success: false,
      error: 'mcp_lookup_failed',
      detail: !serverUrl ? 'MCP_SERVER_URL is not configured' : 'missing driverName',
    };
  }

  const realResult = await callAccidentListTool(env, trimmedDriverName, trimmedAccidentDate);
  if (realResult.success) {
    const data = await fetchAccidentSupplementaryAndAdapt(
      env,
      realResult.data,
      trimmedDriverName,
      trimmedAccidentDate
    );
    return { success: true, data };
  }

  if (!realResult.success && 'error' in realResult && realResult.error) {
    return { success: false, error: 'mcp_lookup_failed', detail: realResult.error };
  }
  return { success: false, error: 'incident_not_found' };
}

export function getDefaultAccidentPartition(): string {
  return buildAccidentDate();
}
