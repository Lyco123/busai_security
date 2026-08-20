import { isRecord } from './guards';
import { callMcpToolForAgent } from './mcp';
import {
  PROFILE_RISK_SCORE_SEMANTICS,
  PROFILE_SOURCE_SCORE_SEMANTICS,
  PROFILE_WEIGHTED_VALUE_SEMANTICS,
  resolveProfileFinalRiskScore,
} from './profile-quota-tree';

type EnvLike = {
  MCP_SERVER_URL?: string;
  CF_ACCESS_CLIENT_ID?: string;
  CF_ACCESS_CLIENT_SECRET?: string;
  MCP_ACCESS_TOKEN?: string;
  MCP_REQUEST_TIMEOUT_MS?: string;
};

type ProfileEntityType = 'driver' | 'vehicle' | 'route' | 'unit' | 'station' | 'accident';

type ProfileQuotaLookupConfig = {
  entityType: ProfileEntityType;
  toolName: string;
  entityArg: string;
  aliases: string[];
  displayNamePaths: string[];
  idPaths: string[];
};

type ProfileQuotaLookupArgs = {
  entityType: ProfileEntityType;
  entityName: string;
  quotaName: string;
  ppartition?: string;
  matchMode: 'exact' | 'contains';
};

type ProfileQuotaItem = {
  quotaId: string | null;
  quotaName: string;
  quotaLevel: string | null;
  parentId: string | null;
  firstQuotaName: string | null;
  score: number | null;
  weightRate: number | null;
  originalValue: number | null;
  riskData: string | null;
  ranking: number | null;
};

const LOOKUP_CONFIGS: ProfileQuotaLookupConfig[] = [
  {
    entityType: 'driver',
    toolName: 'get_mcp_base_absDriverProfileMain_queryDriverProfile',
    entityArg: 'driverName',
    aliases: ['driver', 'driver_profile', 'driverName', 'driver_name'],
    displayNamePaths: ['driverName', 'employeeName'],
    idPaths: ['driverId', 'employeeId', 'employeeCode'],
  },
  {
    entityType: 'vehicle',
    toolName: 'get_mcp_base_absBusProfileMain_queryByNumberplate',
    entityArg: 'numberPlate',
    aliases: ['vehicle', 'bus', 'bus_profile', 'numberPlate', 'numberplate', 'plate'],
    displayNamePaths: ['numberPlate', 'busName'],
    idPaths: ['busId', 'busCode'],
  },
  {
    entityType: 'route',
    toolName: 'get_mcp_base_absRouteProfileMain_queryRouteProfile',
    entityArg: 'routeName',
    aliases: ['route', 'route_profile', 'routeName', 'route_name'],
    displayNamePaths: ['routeName'],
    idPaths: ['routeId', 'routeCode'],
  },
  {
    entityType: 'unit',
    toolName: 'get_mcp_base_absCompanyProfileMain_queryCompanyProfile',
    entityArg: 'organName',
    aliases: ['unit', 'company', 'organ', 'company_profile', 'organName', 'organ_name'],
    displayNamePaths: ['organName'],
    idPaths: ['organId'],
  },
  {
    entityType: 'station',
    toolName: 'get_mcp_base_absBusStationProfileMain_queryBusStationProfile',
    entityArg: 'busStationName',
    aliases: ['station', 'bus_station', 'busStationName', 'stationName', 'station_name'],
    displayNamePaths: ['busStationName', 'stationName', 'name'],
    idPaths: ['busStationId', 'stationId'],
  },
  {
    entityType: 'accident',
    toolName: 'get_mcp_base_adsAccidentProfileMain_queryAccidentProfile',
    entityArg: 'organName',
    aliases: ['accident', 'incident', 'accident_profile', 'organName', 'organ_name'],
    displayNamePaths: ['organName'],
    idPaths: ['organId', 'accidentId'],
  },
];

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

function readStringAtPath(record: Record<string, unknown>, path: string): string | null {
  let current: unknown = record;
  for (const part of path.split('.')) {
    if (!isRecord(current)) return null;
    current = current[part];
  }
  return toStringValue(current);
}

function readFirstStringAtPaths(record: Record<string, unknown>, paths: string[]): string | null {
  for (const path of paths) {
    const value = readStringAtPath(record, path);
    if (value) return value;
  }
  return null;
}

function normalizeEntityType(value: unknown): ProfileEntityType | null {
  const raw = toStringValue(value);
  if (!raw) return null;
  const normalized = raw.toLowerCase();
  for (const config of LOOKUP_CONFIGS) {
    if (config.entityType === normalized || config.aliases.some((alias) => alias.toLowerCase() === normalized)) {
      return config.entityType;
    }
  }
  return null;
}

function getConfig(entityType: ProfileEntityType): ProfileQuotaLookupConfig {
  const config = LOOKUP_CONFIGS.find((item) => item.entityType === entityType);
  if (!config) throw new Error(`Unsupported profile entity type: ${entityType}`);
  return config;
}

function resolveEntityName(args: Record<string, unknown>, config: ProfileQuotaLookupConfig): string | null {
  const candidates = [
    args.entityName,
    args.name,
    args[config.entityArg],
    args.driverName,
    args.driver_name,
    args.numberPlate,
    args.numberplate,
    args.routeName,
    args.route_name,
    args.organName,
    args.organ_name,
    args.busStationName,
    args.stationName,
    args.station_name,
  ];
  for (const candidate of candidates) {
    const value = toStringValue(candidate);
    if (value) return value;
  }
  return null;
}

function normalizeArgs(args: Record<string, unknown>): ProfileQuotaLookupArgs | { error: string } {
  const entityType = normalizeEntityType(args.entityType ?? args.profileType ?? args.subjectType);
  if (!entityType) {
    return {
      error:
        'entityType is required and must be one of driver, vehicle, route, unit, station, accident.',
    };
  }

  const config = getConfig(entityType);
  const entityName = resolveEntityName(args, config);
  if (!entityName) {
    return { error: `entityName or ${config.entityArg} is required for ${entityType}.` };
  }

  const quotaName = toStringValue(args.quotaName ?? args.metricName ?? args.indicatorName);
  if (!quotaName) {
    return { error: 'quotaName is required.' };
  }

  const matchModeInput = toStringValue(args.matchMode);
  const matchMode = matchModeInput === 'contains' ? 'contains' : 'exact';
  return {
    entityType,
    entityName,
    quotaName,
    ppartition: toStringValue(args.ppartition ?? args.partition) ?? undefined,
    matchMode,
  };
}

function extractProfilePayload(value: unknown): Record<string, unknown> | null {
  if (!isRecord(value)) return null;
  if (isRecord(value.result)) return value.result;
  return value;
}

function normalizeQuotaItems(value: unknown): ProfileQuotaItem[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((item) => ({
      quotaId: toStringValue(item.quotaId),
      quotaName: toStringValue(item.quotaName) ?? '',
      quotaLevel: toStringValue(item.quotaLevel),
      parentId: toStringValue(item.parentId),
      firstQuotaName: toStringValue(item.firstQuotaName),
      score: toNumber(item.score),
      weightRate: toNumber(item.weightRate),
      originalValue: toNumber(item.originalValue),
      riskData: toStringValue(item.riskData),
      ranking: toNumber(item.ranking),
    }))
    .filter((item) => item.quotaName || item.quotaId);
}

function matchQuotaName(item: ProfileQuotaItem, quotaName: string, matchMode: 'exact' | 'contains'): boolean {
  if (matchMode === 'contains') {
    return item.quotaName.includes(quotaName);
  }
  return item.quotaName === quotaName;
}

function getMcpConfig(env: EnvLike) {
  return {
    serverUrl: env.MCP_SERVER_URL,
    clientId: env.CF_ACCESS_CLIENT_ID,
    clientSecret: env.CF_ACCESS_CLIENT_SECRET,
    accessToken: env.MCP_ACCESS_TOKEN,
    requestTimeoutMs: env.MCP_REQUEST_TIMEOUT_MS,
  };
}

export async function executeProfileQuotaLookup(
  env: EnvLike,
  args: Record<string, unknown>
): Promise<{ success: boolean; data?: unknown; error?: string }> {
  const normalized = normalizeArgs(args);
  if ('error' in normalized) {
    return { success: false, error: normalized.error };
  }

  if (!toStringValue(env.MCP_SERVER_URL)) {
    return { success: false, error: 'MCP_SERVER_URL is not configured.' };
  }

  const config = getConfig(normalized.entityType);
  const toolArgs = {
    [config.entityArg]: normalized.entityName,
    ...(normalized.ppartition ? { ppartition: normalized.ppartition } : {}),
  };
  const profileResult = await callMcpToolForAgent(getMcpConfig(env), config.toolName, toolArgs);
  if (!profileResult.success) {
    return {
      success: false,
      error: profileResult.error ?? `Failed to query profile tool ${config.toolName}.`,
    };
  }

  const payload = extractProfilePayload(profileResult.data);
  if (!payload || !isRecord(payload.main)) {
    return { success: false, error: 'Profile tool did not return a valid profile payload.' };
  }

  const quotaItems = normalizeQuotaItems(payload.quotaScoreSubList);
  const matches = quotaItems.filter((item) =>
    matchQuotaName(item, normalized.quotaName, normalized.matchMode)
  );
  const main = payload.main;

  return {
    success: true,
    data: {
      source_tool: config.toolName,
      source_args: toolArgs,
      entity_type: normalized.entityType,
      entity: {
        name:
          readFirstStringAtPaths(main, config.displayNamePaths) ??
          normalized.entityName,
        id: readFirstStringAtPaths(main, config.idPaths),
        ppartition: readStringAtPath(main, 'ppartition') ?? normalized.ppartition ?? null,
        calculate_date: readStringAtPath(main, 'calculateDate'),
        organ_name: readStringAtPath(main, 'organName'),
        route_name: readStringAtPath(main, 'routeName'),
        score: toNumber(main.score),
        evaluation_type: readStringAtPath(main, 'evalutaionType'),
        ranking: toNumber(main.ranking),
      },
      quota_name: normalized.quotaName,
      match_mode: normalized.matchMode,
      match_count: matches.length,
      matches: matches.map((item) => ({
        quota_id: item.quotaId,
        quota_name: item.quotaName,
        quota_level: item.quotaLevel,
        parent_id: item.parentId,
        first_quota_name: item.firstQuotaName,
        score: item.score,
        source_score: item.score,
        original_value: item.originalValue,
        final_risk_score: resolveProfileFinalRiskScore(item),
        risk_score: resolveProfileFinalRiskScore(item),
        weight_rate: item.weightRate,
        risk_data: item.riskData,
        ranking: item.ranking,
        score_semantics: PROFILE_SOURCE_SCORE_SEMANTICS,
        final_score_semantics: PROFILE_RISK_SCORE_SEMANTICS,
      })),
      quota_value_notes: {
        score: PROFILE_SOURCE_SCORE_SEMANTICS,
        source_score: PROFILE_SOURCE_SCORE_SEMANTICS,
        original_value: PROFILE_WEIGHTED_VALUE_SEMANTICS,
        final_risk_score: PROFILE_RISK_SCORE_SEMANTICS,
        risk_score: PROFILE_RISK_SCORE_SEMANTICS,
      },
      ...(matches.length === 0
        ? {
            available_same_profile_quota_names: Array.from(
              new Set(quotaItems.map((item) => item.quotaName).filter(Boolean))
            ).slice(0, 80),
          }
        : {}),
    },
  };
}
