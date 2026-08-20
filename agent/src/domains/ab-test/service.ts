import {
  ACTIVE_AB_TEST_EXPERIMENT,
  createAbTestStatsBucket,
  getAbTestGroupDisplayLabel,
  getActiveAbTestDisplayGroups,
  type AbTestGroup,
  type AbTestStatsResponse,
} from './config';
import { extractAbTestGroupFromMetadata, normalizeAbTestGroup, normalizeAbTestVariant } from './metadata';
import type { AbTestResolution } from './types';
import { safeJsonParse } from '../../shared/json';
import { DEFAULT_RULE_ROUTING_MODE } from '../chat/turn-context';

interface D1PreparedStatementLike {
  bind: (...values: unknown[]) => D1PreparedStatementLike;
  first: <T = Record<string, unknown>>() => Promise<T | null>;
  all: <T = Record<string, unknown>>() => Promise<{ results: T[] }>;
}

interface D1DatabaseLike {
  prepare: (query: string) => D1PreparedStatementLike;
}

const DEFAULT_AB_TEST_GROUP: AbTestGroup = ACTIVE_AB_TEST_EXPERIMENT.defaultGroup;

export function assignAbTestGroup(sessionId: string): AbTestGroup {
  const groups = ACTIVE_AB_TEST_EXPERIMENT.groups;
  if (!groups.length) return DEFAULT_AB_TEST_GROUP;

  let hash = 0;
  for (let index = 0; index < sessionId.length; index += 1) {
    hash = (hash * 31 + sessionId.charCodeAt(index)) >>> 0;
  }
  return groups[hash % groups.length] ?? DEFAULT_AB_TEST_GROUP;
}

export async function resolveSessionAbTestResolution(
  db: D1DatabaseLike,
  sessionId: string
): Promise<AbTestResolution> {
  const firstAssistant = await db
    .prepare(
      'SELECT metadata FROM agent_messages WHERE session_id = ? AND role = ? ORDER BY created_at ASC, id ASC LIMIT 1'
    )
    .bind(sessionId, 'assistant')
    .first<{ metadata: string | null }>();

  if (firstAssistant) {
    const parsed = firstAssistant.metadata ? safeJsonParse(firstAssistant.metadata) : null;
    const existingGroup = extractAbTestGroupFromMetadata(parsed);
    if (existingGroup) {
      return {
        experiment: ACTIVE_AB_TEST_EXPERIMENT.id,
        group: existingGroup,
        locked: true,
        source: 'session_bound',
        routingMode: DEFAULT_RULE_ROUTING_MODE,
      };
    }
    return {
      experiment: ACTIVE_AB_TEST_EXPERIMENT.id,
      group: null,
      locked: true,
      source: 'legacy',
      routingMode: DEFAULT_RULE_ROUTING_MODE,
    };
  }

  const countRow = await db
    .prepare("SELECT COUNT(*) as count FROM agent_messages WHERE session_id = ? AND role IN ('user','assistant')")
    .bind(sessionId)
    .first<{ count: number | string }>();
  const count = Number(countRow?.count ?? 0);
  if (Number.isFinite(count) && count > 1) {
    return {
      experiment: ACTIVE_AB_TEST_EXPERIMENT.id,
      group: null,
      locked: true,
      source: 'legacy',
      routingMode: DEFAULT_RULE_ROUTING_MODE,
    };
  }

  return {
    experiment: ACTIVE_AB_TEST_EXPERIMENT.id,
    group: assignAbTestGroup(sessionId),
    locked: false,
    source: 'assigned',
    routingMode: DEFAULT_RULE_ROUTING_MODE,
  };
}

export async function getAbTestStats(db: D1DatabaseLike): Promise<AbTestStatsResponse> {
  const result = await db
    .prepare('SELECT session_id, metadata FROM agent_messages WHERE role = ? AND metadata IS NOT NULL')
    .bind('assistant')
    .all<{ session_id: string; metadata: string | null }>();

  const displayGroups = getActiveAbTestDisplayGroups();
  const metricBuckets = new Map(
    ACTIVE_AB_TEST_EXPERIMENT.statsMetrics.map((metric) => [metric.key, createAbTestStatsBucket(displayGroups)])
  );
  const sessions = new Set<string>();
  let sampleTurns = 0;

  for (const row of result.results) {
    if (!row.metadata) continue;
    const parsed = safeJsonParse(row.metadata);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) continue;
    const metadata = parsed as Record<string, unknown>;
    const abTestRaw = metadata.ab_test;
    if (!abTestRaw || typeof abTestRaw !== 'object' || Array.isArray(abTestRaw)) continue;
    const abTest = abTestRaw as Record<string, unknown>;
    const experiment = typeof abTest.experiment === 'string' ? abTest.experiment : '';
    if (experiment !== ACTIVE_AB_TEST_EXPERIMENT.id) continue;
    if (abTest.source === 'legacy') continue;
    const group = normalizeAbTestGroup(abTest.group) ?? normalizeAbTestVariant(abTest.variant);
    const bucketKey =
      (typeof abTest.variant === 'string' && abTest.variant.trim()) ||
      (group ? getAbTestGroupDisplayLabel(group) : '');
    if (!bucketKey) continue;

    sampleTurns += 1;
    sessions.add(row.session_id);

    const selectedTool = typeof abTest.selected_tool === 'string' ? abTest.selected_tool.trim() : '';
    for (const metric of ACTIVE_AB_TEST_EXPERIMENT.statsMetrics) {
      if (!metric.test({ selectedTool })) continue;
      const bucket = metricBuckets.get(metric.key);
      if (bucket && Object.prototype.hasOwnProperty.call(bucket, bucketKey)) {
        bucket[bucketKey] += 1;
      }
    }
  }

  return {
    experiment: ACTIVE_AB_TEST_EXPERIMENT.id,
    title: ACTIVE_AB_TEST_EXPERIMENT.title,
    groups: displayGroups,
    sample_turns: sampleTurns,
    sample_sessions: sessions.size,
    metrics: ACTIVE_AB_TEST_EXPERIMENT.statsMetrics.map((metric) => ({
      key: metric.key,
      label: metric.label,
      values: metricBuckets.get(metric.key) ?? createAbTestStatsBucket(displayGroups),
    })),
    updated_at: new Date().toISOString(),
  };
}

export function shouldEnableVehicleExpertDeepCot(
  resolution: AbTestResolution | null | undefined,
  cotMode: string | null | undefined
): boolean {
  return resolution?.group === 'Y' && cotMode === 'deep';
}
