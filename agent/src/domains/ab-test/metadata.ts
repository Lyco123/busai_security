import {
  ACTIVE_AB_TEST_EXPERIMENT,
  getAbTestGroupDisplayLabel,
  isAbTestGroup,
  type AbTestGroup,
} from './config';
import type { AbTestMetadataDetails, AbTestResolution } from './types';

const DEFAULT_HIGH_SCORE_THRESHOLD = 0.7;

export function normalizeAbTestGroup(value: unknown): AbTestGroup | null {
  return isAbTestGroup(value) ? value : null;
}

export function normalizeAbTestVariant(value: unknown): AbTestGroup | null {
  if (typeof value !== 'string') return null;
  const variant = value.trim();
  if (!variant) return null;
  for (const group of ACTIVE_AB_TEST_EXPERIMENT.groups) {
    if (getAbTestGroupDisplayLabel(group) === variant) {
      return group;
    }
  }
  return null;
}

export function extractAbTestGroupFromMetadata(value: unknown): AbTestGroup | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const metadata = value as Record<string, unknown>;
  if (!metadata.ab_test || typeof metadata.ab_test !== 'object' || Array.isArray(metadata.ab_test)) {
    return null;
  }
  const abTest = metadata.ab_test as Record<string, unknown>;
  return normalizeAbTestGroup(abTest.group) ?? normalizeAbTestVariant(abTest.variant);
}

export function hasAbTestMetadata(value: unknown): boolean {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const metadata = value as Record<string, unknown>;
  return Boolean(metadata.ab_test && typeof metadata.ab_test === 'object' && !Array.isArray(metadata.ab_test));
}

export function readAbTestGroupFromMessageMetadata(metadata: unknown): AbTestGroup | null {
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) return null;
  const abTest = (metadata as Record<string, unknown>).ab_test;
  if (!abTest || typeof abTest !== 'object' || Array.isArray(abTest)) return null;
  const record = abTest as Record<string, unknown>;
  return normalizeAbTestGroup(record.group) ?? normalizeAbTestVariant(record.variant);
}

export function buildAbTestMetadata(
  resolution: AbTestResolution,
  details?: AbTestMetadataDetails,
  options?: { highScoreThreshold?: number }
): Record<string, unknown> {
  const topScore = Number.isFinite(details?.topScore ?? Number.NaN)
    ? Number((details?.topScore as number).toFixed(3))
    : null;
  const highScoreThreshold = options?.highScoreThreshold ?? DEFAULT_HIGH_SCORE_THRESHOLD;
  return {
    experiment: resolution.experiment,
    group: resolution.group ?? null,
    variant: resolution.group ? getAbTestGroupDisplayLabel(resolution.group) : null,
    locked: resolution.locked,
    source: resolution.source,
    routing_mode: resolution.routingMode,
    top_score: topScore,
    high_score_hit: typeof topScore === 'number' ? topScore >= highScoreThreshold : false,
    selected_tool: details?.selectedTool ?? null,
    selected_rule_id: details?.selectedRuleId ?? null,
    rule_exit_fallback: Boolean(details?.ruleExitFallback),
    skip_rule_id: details?.skipRuleId || null,
  };
}

export function withAbTestMetadata(
  metadata: Record<string, unknown> | undefined,
  abTestMetadata: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...(metadata ?? {}),
    ab_test: abTestMetadata,
  };
}
