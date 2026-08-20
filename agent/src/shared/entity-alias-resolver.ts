import {
  listApprovedEntityAliases,
  listEntityStandardNames,
  type D1Database,
  type EntityAliasType,
} from '../domains/aliases/repository';

export type EntityAliasResolution = {
  entityType: EntityAliasType;
  mention: string;
  standardName: string;
  hint: string;
};

type AliasPair = {
  alias: string;
  standardName: string;
  normalizedAlias: string;
};

type AliasSpan = {
  mention: string;
  standardName: string;
  start: number;
  end: number;
};

function normalizeEntityToken(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/[\s"'`.,，。；;：:！？?、/\\|()[\]{}<>《》【】「」『』“”‘’]+/g, '');
}

function normalizeLooseUnitToken(value: string): string {
  return normalizeEntityToken(value)
    .replace(/\u6709\u9650\u516c\u53f8/g, '')
    .replace(/\u7b2c\u4e00(?=\u5206)/g, '\u4e00')
    .replace(/\u7b2c\u4e8c(?=\u5206|\u5df4)/g, '\u4e8c')
    .replace(/\u7b2c\u4e09(?=\u5206)/g, '\u4e09')
    .replace(/\u7b2c\u56db(?=\u5206)/g, '\u56db')
    .replace(/^[8八][级集]/, '巴集')
    .replace(/^巴级/, '巴集')
    .replace(/1(?=分)/g, '一')
    .replace(/2(?=分|巴)/g, '二')
    .replace(/3(?=分)/g, '三')
    .replace(/4(?=分)/g, '四');
}

function normalizeFleetNumber(value: string): string {
  const normalized = value.normalize('NFKC').trim().replace(/^第/u, '');
  const digitMap: Record<string, string> = {
    '1': '一',
    '2': '二',
    '3': '三',
    '4': '四',
    '5': '五',
    '6': '六',
    '7': '七',
    '8': '八',
    '9': '九',
    '10': '十',
  };
  return digitMap[normalized] ?? normalized;
}

function normalizeLooseFleetToken(value: string): string {
  const token = normalizeEntityToken(value)
    .replace(/^第/u, '')
    .replace(/^车([0-9一二三四五六七八九十]+)队$/u, '$1队');
  const numericFleet = token.match(/^([0-9]+)(?:车队|队)$/u);
  if (numericFleet?.[1]) {
    return `${normalizeFleetNumber(numericFleet[1])}车队`;
  }
  const chineseFleet = token.match(/^([一二三四五六七八九十]+)(?:车队|队)$/u);
  if (chineseFleet?.[1]) {
    return `${chineseFleet[1]}车队`;
  }
  return token;
}

function normalizeAliasByType(entityType: EntityAliasType, value: string): string {
  if (entityType === 'unit') return normalizeLooseUnitToken(value);
  if (entityType === 'fleet') return normalizeLooseFleetToken(value);
  return normalizeEntityToken(value);
}

function buildAliasHint(entityType: EntityAliasType, mention: string, standardName: string): string {
  const label = entityType === 'unit' ? '单位' : entityType === 'fleet' ? '车队' : '线路';
  return [
    '实体别名提示：',
    `- 用户提到的“${mention}”可能是“${standardName}”。`,
    `- “${standardName}”是数据库标准${label}名称。`,
    `- 当涉及查询调用时必须使用标准名“${standardName}”。`,
  ].join('\n');
}

function createResolution(
  entityType: EntityAliasType,
  mention: string,
  standardName: string,
  options?: { allowIdentity?: boolean }
): EntityAliasResolution | null {
  const trimmedMention = mention.trim();
  const trimmedStandardName = standardName.trim();
  if (
    !trimmedMention ||
    !trimmedStandardName ||
    (!options?.allowIdentity && trimmedMention === trimmedStandardName)
  ) {
    return null;
  }
  return {
    entityType,
    mention: trimmedMention,
    standardName: trimmedStandardName,
    hint: buildAliasHint(entityType, trimmedMention, trimmedStandardName),
  };
}

async function getApprovedAliasPairs(db: D1Database | undefined, entityType: EntityAliasType) {
  if (!db) return [];
  const aliases = await listApprovedEntityAliases(db, entityType);
  return aliases.map((row) => ({
    alias: row.alias,
    standardName: row.standard_name,
    normalizedAlias: normalizeAliasByType(entityType, row.alias),
  }));
}

function dedupeAliasPairs(pairs: AliasPair[]): AliasPair[] {
  const seen = new Set<string>();
  const result: AliasPair[] = [];
  for (const pair of pairs) {
    const key = `${pair.normalizedAlias}\u0000${pair.standardName}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(pair);
  }
  return result;
}

function inferComposableUnitName(standardName: string): boolean {
  const normalized = standardName.normalize('NFKC').trim();
  if (!normalized || normalized.includes('-') || normalized.includes('车队')) return false;
  return /(?:分公司|片区|公司)$/u.test(normalized);
}

async function getComposableUnitAliasPairs(db: D1Database | undefined): Promise<AliasPair[]> {
  if (!db) return [];
  const [aliases, standards] = await Promise.all([
    listApprovedEntityAliases(db, 'unit'),
    listEntityStandardNames(db, { entityType: 'unit' }),
  ]);
  const composableStandards = new Set(
    standards
      .filter((row) => row.can_compose_with_fleet || inferComposableUnitName(row.standard_name))
      .map((row) => row.standard_name)
  );
  const standardPairs = standards
    .filter((row) => composableStandards.has(row.standard_name))
    .map((row) => ({
      alias: row.standard_name,
      standardName: row.standard_name,
      normalizedAlias: normalizeLooseUnitToken(row.standard_name),
    }));
  const aliasPairs = aliases
    .filter((row) => composableStandards.has(row.standard_name))
    .map((row) => ({
      alias: row.alias,
      standardName: row.standard_name,
      normalizedAlias: normalizeLooseUnitToken(row.alias),
    }));
  return dedupeAliasPairs([...aliasPairs, ...standardPairs]);
}

async function getFleetAliasPairs(db: D1Database | undefined): Promise<AliasPair[]> {
  if (!db) return [];
  const [aliases, standards] = await Promise.all([
    listApprovedEntityAliases(db, 'fleet'),
    listEntityStandardNames(db, { entityType: 'fleet' }),
  ]);
  const standardPairs = standards.map((row) => ({
    alias: row.standard_name,
    standardName: row.standard_name,
    normalizedAlias: normalizeLooseFleetToken(row.standard_name),
  }));
  const aliasPairs = aliases.map((row) => ({
    alias: row.alias,
    standardName: row.standard_name,
    normalizedAlias: normalizeLooseFleetToken(row.alias),
  }));
  return dedupeAliasPairs([...aliasPairs, ...standardPairs]);
}

function findAliasSpans(
  value: string,
  pairs: AliasPair[],
  normalizer: (input: string) => string
): AliasSpan[] {
  if (pairs.length === 0) return [];
  const normalized = value.normalize('NFKC').trim();
  const chars = Array.from(normalized);
  const maxAliasLength = Math.max(...pairs.map((item) => Array.from(item.alias).length));
  const spans: AliasSpan[] = [];

  for (let start = 0; start < chars.length; start += 1) {
    const maxEnd = Math.min(chars.length, start + maxAliasLength + 4);
    for (let end = start + 1; end <= maxEnd; end += 1) {
      const candidate = chars.slice(start, end).join('').trim();
      const normalizedCandidate = normalizer(candidate);
      if (!normalizedCandidate) continue;
      const matched = pairs.find((pair) => pair.normalizedAlias === normalizedCandidate);
      if (!matched) continue;
      spans.push({
        mention: candidate,
        standardName: matched.standardName,
        start,
        end,
      });
    }
  }

  return spans;
}

function normalizeUnitFleetGap(value: string): string {
  return normalizeEntityToken(value)
    .replace(/[-－—_]+/g, '')
    .replace(/^(?:的|下属|所属|所辖|旗下)/u, '');
}

async function resolveConfiguredAlias(
  db: D1Database | undefined,
  entityType: EntityAliasType,
  value: string
): Promise<EntityAliasResolution | null> {
  const mention = value.trim();
  if (!mention) return null;
  const normalizedMention = normalizeAliasByType(entityType, mention);
  const pairs = await getApprovedAliasPairs(db, entityType);
  const matched = pairs.find((pair) => pair.normalizedAlias === normalizedMention);
  return matched ? createResolution(entityType, mention, matched.standardName) : null;
}

async function resolveConfiguredAliasInText(
  db: D1Database | undefined,
  entityType: EntityAliasType,
  value: string
): Promise<EntityAliasResolution | null> {
  const direct = await resolveConfiguredAlias(db, entityType, value);
  if (direct) return direct;

  const pairs = await getApprovedAliasPairs(db, entityType);
  if (pairs.length === 0) return null;

  const normalizer = (input: string) => normalizeAliasByType(entityType, input);
  const maxAliasLength = Math.max(...pairs.map((item) => Array.from(item.alias).length));
  const chars = Array.from(value.trim());
  let best: EntityAliasResolution | null = null;

  for (let start = 0; start < chars.length; start += 1) {
    const maxEnd = Math.min(chars.length, start + maxAliasLength + 2);
    for (let end = start + 2; end <= maxEnd; end += 1) {
      const candidate = chars.slice(start, end).join('').trim();
      const normalizedCandidate = normalizer(candidate);
      const matched = pairs.find((pair) => pair.normalizedAlias === normalizedCandidate);
      if (!matched) continue;
      const resolved = createResolution(entityType, candidate, matched.standardName);
      if (resolved && (!best || resolved.mention.length > best.mention.length)) {
        best = resolved;
      }
    }
  }

  return best;
}

function resolveRouteRuleAlias(value: string): EntityAliasResolution | null {
  const mention = value.trim();
  if (!mention) return null;
  const compact = mention.normalize('NFKC').replace(/\s+/g, '').trim();
  const routeMatch =
    compact.match(
      /^(?:线路)?([0-9A-Za-z]+)(?:[（(](?:上行|下行)[）)]路?|路(?:上行|下行)?|(?:上行|下行)路?)$/i
    );
  if (!routeMatch?.[1]) return null;
  return createResolution('route', mention, routeMatch[1]);
}

function resolveRouteRuleAliasInText(value: string): EntityAliasResolution | null {
  const direct = resolveRouteRuleAlias(value);
  if (direct) return direct;
  const match =
    value
      .normalize('NFKC')
      .match(
        /(?:线路)?[0-9A-Za-z]+(?:[（(](?:上行|下行)[）)]路?|路(?:上行|下行)?|(?:上行|下行)路?)/u
      ) ??
    value.normalize('NFKC').match(/(?:线路)?([0-9A-Za-z]+)路/u);
  return match?.[0] ? resolveRouteRuleAlias(match[0]) : null;
}

export async function resolveUnitAlias(
  db: D1Database | undefined,
  value: string
): Promise<EntityAliasResolution | null> {
  return resolveConfiguredAlias(db, 'unit', value);
}

export async function resolveUnitAliasInText(
  db: D1Database | undefined,
  value: string
): Promise<EntityAliasResolution | null> {
  return resolveConfiguredAliasInText(db, 'unit', value);
}

export async function resolveFleetAlias(
  db: D1Database | undefined,
  value: string
): Promise<EntityAliasResolution | null> {
  return resolveConfiguredAlias(db, 'fleet', value);
}

export async function resolveFleetAliasInText(
  db: D1Database | undefined,
  value: string
): Promise<EntityAliasResolution | null> {
  return resolveConfiguredAliasInText(db, 'fleet', value);
}

export async function resolveFleetUnitAliasInText(
  db: D1Database | undefined,
  value: string
): Promise<EntityAliasResolution | null> {
  const normalized = value.normalize('NFKC').trim();
  if (!normalized) return null;

  const [unitPairs, fleetPairs] = await Promise.all([
    getComposableUnitAliasPairs(db),
    getFleetAliasPairs(db),
  ]);
  const unitSpans = findAliasSpans(normalized, unitPairs, normalizeLooseUnitToken);
  const fleetSpans = findAliasSpans(normalized, fleetPairs, normalizeLooseFleetToken);
  let best:
    | {
        mention: string;
        standardName: string;
        gapLength: number;
        spanLength: number;
      }
    | null = null;

  for (const unitSpan of unitSpans) {
    for (const fleetSpan of fleetSpans) {
      if (unitSpan.end > fleetSpan.start) continue;
      const gap = Array.from(normalized).slice(unitSpan.end, fleetSpan.start).join('');
      const normalizedGap = normalizeUnitFleetGap(gap);
      if (normalizedGap) continue;
      const standardName = `${unitSpan.standardName}-${fleetSpan.standardName}`;
      const mention = Array.from(normalized).slice(unitSpan.start, fleetSpan.end).join('').trim();
      const candidate = {
        mention,
        standardName,
        gapLength: Array.from(gap).length,
        spanLength: Array.from(mention).length,
      };
      if (
        !best ||
        candidate.gapLength < best.gapLength ||
        (candidate.gapLength === best.gapLength && candidate.spanLength > best.spanLength)
      ) {
        best = candidate;
      }
    }
  }

  return best
    ? createResolution('unit', best.mention, best.standardName, { allowIdentity: true })
    : null;
}

export async function resolveRouteAlias(
  db: D1Database | undefined,
  value: string
): Promise<EntityAliasResolution | null> {
  return (await resolveConfiguredAlias(db, 'route', value)) ?? resolveRouteRuleAlias(value);
}

export async function resolveRouteAliasInText(
  db: D1Database | undefined,
  value: string
): Promise<EntityAliasResolution | null> {
  return (await resolveConfiguredAliasInText(db, 'route', value)) ?? resolveRouteRuleAliasInText(value);
}

export function applyEntityAliasHintToPrompt(prompt: string, resolution: EntityAliasResolution | null): string {
  return resolution ? `${resolution.hint}\n\n${prompt}` : prompt;
}

export async function getStandardUnitName(db: D1Database | undefined, value: string): Promise<string> {
  return (
    (await resolveUnitAlias(db, value))?.standardName ??
    (await resolveFleetUnitAliasInText(db, value))?.standardName ??
    value.trim()
  );
}

export async function getStandardRouteName(db: D1Database | undefined, value: string): Promise<string> {
  return (await resolveRouteAlias(db, value))?.standardName ?? value.trim();
}
