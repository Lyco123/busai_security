import { collapseWhitespace } from '../../../shared/text';
import type {
  LegacyRuleDraftStatus,
  RuleConfigIntent,
  RuleConfigState,
  RuleDraft,
  RuleFieldConfidence,
  RuleFieldMeta,
  RuleFieldSource,
  RuleReworkTicket,
  RuleRequiredInfoItem,
  RuleTurnOperation,
  RuleTurnOperationType,
} from './types';

export const RULE_CONFIG_FIELDS = [
  'name',
  'match_text',
  'reply_goal',
  'key_points',
  'required_info',
  'examples',
  'template',
  'safe_defaults',
  'do_not_say',
  'tone',
] as const;

const RULE_CONFIG_TONE_VALUES = new Set(['professional', 'warm', 'brief']);
const RULE_CONFIG_PLACEHOLDER_PATTERN = /(\[[^\]]+\]|\{[^}]+\}|\{\{[^}]+\}\})/;

type CreateId = (prefix: string) => string;

function isRuleConfigField(field: string): field is (typeof RULE_CONFIG_FIELDS)[number] {
  return RULE_CONFIG_FIELDS.includes(field as (typeof RULE_CONFIG_FIELDS)[number]);
}

function buildFallbackRuleFieldMeta(field: string, createId: CreateId): RuleFieldMeta {
  void field;
  return {
    source: 'explicit',
    confidence: 'high',
    turn_id: createId('turn'),
  };
}

export function normalizeRuleConfigState(
  value: unknown,
  fallback: RuleConfigState = 'collecting'
): RuleConfigState {
  const raw = String(value ?? '').trim();
  if (raw === 'ready_for_confirm') return 'awaiting_confirm';
  if (raw === 'blocked') return 'blocked_conflict';
  if (
    raw === 'collecting' ||
    raw === 'awaiting_confirm' ||
    raw === 'compiling' ||
    raw === 'rework' ||
    raw === 'blocked_conflict' ||
    raw === 'saved' ||
    raw === 'cancelled'
  ) {
    return raw;
  }
  return fallback;
}

export function normalizeRuleConfigIntent(value: unknown): RuleConfigIntent {
  const raw = String(value ?? '').trim();
  return raw === 'provide_info' || raw === 'confirm' || raw === 'revise' || raw === 'cancel' ? raw : 'unknown';
}

export function toRuleConfigFieldLabel(field: string): string {
  const labels: Record<string, string> = {
    name: '规则名称',
    match_text: '触发场景',
    reply_goal: '回复目标',
    key_points: '回复要点',
    required_info: '补充信息项',
    examples: '示例问法',
    template: '回复模板',
    safe_defaults: '默认兜底信息',
    do_not_say: '禁说项',
    tone: '语气',
  };
  return labels[field] ?? field;
}

export function normalizeRuleFieldMetaRecord(
  value: unknown,
  createId: CreateId
): Record<string, RuleFieldMeta> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }
  const result: Record<string, RuleFieldMeta> = {};
  for (const [field, rawMeta] of Object.entries(value as Record<string, unknown>)) {
    if (!isRuleConfigField(field)) continue;
    if (!rawMeta || typeof rawMeta !== 'object' || Array.isArray(rawMeta)) continue;
    const metaRecord = rawMeta as Record<string, unknown>;
    const source = String(metaRecord.source ?? '').trim();
    const confidence = String(metaRecord.confidence ?? '').trim();
    const turnId = String(metaRecord.turn_id ?? '').trim();
    result[field] = {
      source:
        source === 'explicit' || source === 'inferred' || source === 'builder_fix'
          ? (source as RuleFieldSource)
          : 'explicit',
      confidence:
        confidence === 'high' || confidence === 'medium' || confidence === 'low'
          ? (confidence as RuleFieldConfidence)
          : 'high',
      turn_id: turnId || createId('turn'),
    };
  }
  return result;
}

export function normalizeRuleFieldMetaInput(
  value: unknown,
  defaultTurnId: string,
  createId: CreateId
): Record<string, RuleFieldMeta> {
  if (Array.isArray(value)) {
    const result: Record<string, RuleFieldMeta> = {};
    for (const item of value) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
      const record = item as Record<string, unknown>;
      const field = String(record.field ?? '').trim();
      if (!isRuleConfigField(field)) continue;
      result[field] = {
        source:
          record.source === 'explicit' || record.source === 'inferred' || record.source === 'builder_fix'
            ? (record.source as RuleFieldSource)
            : 'explicit',
        confidence:
          record.confidence === 'high' || record.confidence === 'medium' || record.confidence === 'low'
            ? (record.confidence as RuleFieldConfidence)
            : 'high',
        turn_id: String(record.turn_id ?? '').trim() || defaultTurnId,
      };
    }
    return result;
  }
  return normalizeRuleFieldMetaRecord(value, createId);
}

export function normalizeRuleConfigStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (typeof value === 'string') {
    return value
      .split(/\r?\n|[;,|、]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

export function normalizeRuleConfigFieldValue(field: string, value: unknown): unknown {
  if (!isRuleConfigField(field)) {
    return undefined;
  }
  if (field === 'tone') {
    const tone = String(value ?? '').trim();
    return RULE_CONFIG_TONE_VALUES.has(tone) ? tone : undefined;
  }
  if (field === 'name' || field === 'match_text' || field === 'reply_goal' || field === 'template') {
    const text = String(value ?? '').trim();
    return text || undefined;
  }
  if (field === 'key_points' || field === 'examples' || field === 'do_not_say') {
    const items = normalizeRuleConfigStringArray(value);
    return items.length ? items : undefined;
  }
  if (field === 'required_info') {
    if (Array.isArray(value)) {
      const normalized = value
        .map((item) => {
          if (typeof item === 'string') {
            const text = item.trim();
            return text ? text : null;
          }
          if (item && typeof item === 'object' && !Array.isArray(item)) {
            const record = item as Record<string, unknown>;
            const key = String(record.key ?? '').trim();
            const ask = String(record.ask ?? '').trim();
            if (!key && !ask) return null;
            return {
              key: key || ask || 'info',
              ask: ask || `请补充${key || '相关信息'}`,
              required: record.required !== false,
            };
          }
          return null;
        })
        .filter(Boolean);
      return normalized.length ? normalized : undefined;
    }
    const items = normalizeRuleConfigStringArray(value);
    return items.length ? items : undefined;
  }
  if (field === 'safe_defaults') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
    const next: Record<string, string> = {};
    for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
      const text = String(raw ?? '').trim();
      if (text) next[key] = text;
    }
    return Object.keys(next).length ? next : undefined;
  }
  return undefined;
}

export function sanitizeRuleConfigPatch(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }
  const result: Record<string, unknown> = {};
  for (const [field, raw] of Object.entries(value as Record<string, unknown>)) {
    const normalized = normalizeRuleConfigFieldValue(field, raw);
    if (normalized !== undefined) {
      result[field] = normalized;
    }
  }
  return result;
}

export function normalizeRuleTurnOperationType(value: unknown): RuleTurnOperationType | null {
  const raw = String(value ?? '').trim().toLowerCase();
  if (raw === 'set' || raw === 'replace') return 'set';
  if (raw === 'append' || raw === 'add' || raw === 'merge') return 'append';
  if (raw === 'remove' || raw === 'delete') return 'remove';
  if (raw === 'clear' || raw === 'unset') return 'clear';
  return null;
}

export function normalizeRuleTurnOperations(
  value: unknown,
  fallbackPatch: Record<string, unknown>
): RuleTurnOperation[] {
  if (!Array.isArray(value)) {
    return Object.entries(fallbackPatch).map(([field, patchValue]) => ({
      field,
      op: 'set',
      value: patchValue,
    }));
  }
  const result: RuleTurnOperation[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const record = item as Record<string, unknown>;
    const field = String(record.field ?? '').trim();
    if (!isRuleConfigField(field)) continue;
    const op = normalizeRuleTurnOperationType(record.op);
    if (!op) continue;
    if (op === 'clear') {
      result.push({ field, op });
      continue;
    }
    const normalizedValue = normalizeRuleConfigFieldValue(field, record.value);
    if (normalizedValue === undefined) continue;
    result.push({ field, op, value: normalizedValue });
  }
  if (result.length > 0) {
    return result;
  }
  return Object.entries(fallbackPatch).map(([field, patchValue]) => ({
    field,
    op: 'set',
    value: patchValue,
  }));
}

export function mergeStringItems(current: string[], incoming: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of [...current, ...incoming]) {
    const key = collapseWhitespace(item).trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push(item.trim());
  }
  return result;
}

export function normalizeRequiredInfoEntries(value: unknown): RuleRequiredInfoItem[] {
  const normalized = normalizeRuleConfigFieldValue('required_info', value);
  return Array.isArray(normalized) ? (normalized as RuleRequiredInfoItem[]) : [];
}

export function getRequiredInfoIdentity(value: RuleRequiredInfoItem): string {
  if (typeof value === 'string') {
    return collapseWhitespace(value).trim();
  }
  return collapseWhitespace(String(value.key || value.ask || '')).trim();
}

export function mergeRequiredInfoItems(
  current: RuleRequiredInfoItem[],
  incoming: RuleRequiredInfoItem[]
): RuleRequiredInfoItem[] {
  const result = [...current];
  const indexById = new Map<string, number>();
  result.forEach((item, index) => indexById.set(getRequiredInfoIdentity(item), index));
  for (const item of incoming) {
    const id = getRequiredInfoIdentity(item);
    if (!id) continue;
    const existingIndex = indexById.get(id);
    if (existingIndex === undefined) {
      indexById.set(id, result.length);
      result.push(item);
      continue;
    }
    result[existingIndex] = item;
  }
  return result;
}

export function removeStringItems(current: string[], removals: string[]): string[] {
  const removalSet = new Set(removals.map((item) => collapseWhitespace(item).trim()).filter(Boolean));
  return current.filter((item) => !removalSet.has(collapseWhitespace(item).trim()));
}

export function removeRequiredInfoItems(
  current: RuleRequiredInfoItem[],
  removals: RuleRequiredInfoItem[]
): RuleRequiredInfoItem[] {
  const removalSet = new Set(removals.map(getRequiredInfoIdentity).filter(Boolean));
  return current.filter((item) => !removalSet.has(getRequiredInfoIdentity(item)));
}

export function applyRuleTurnOperations(
  draft: Record<string, unknown>,
  fieldMeta: Record<string, RuleFieldMeta>,
  operations: RuleTurnOperation[],
  proposalFieldMeta: Record<string, RuleFieldMeta>,
  createId: CreateId
): {
  draft: Record<string, unknown>;
  field_meta: Record<string, RuleFieldMeta>;
  updated_fields: string[];
} {
  const nextDraft = { ...draft };
  const nextFieldMeta = { ...fieldMeta };
  const updatedFields = new Set<string>();

  for (const operation of operations) {
    const field = operation.field;
    if (!isRuleConfigField(field)) continue;
    const meta = proposalFieldMeta[field] ?? buildFallbackRuleFieldMeta(field, createId);

    if (operation.op === 'clear') {
      delete nextDraft[field];
      delete nextFieldMeta[field];
      updatedFields.add(field);
      continue;
    }

    if (operation.op === 'set') {
      const normalizedValue = normalizeRuleConfigFieldValue(field, operation.value);
      if (normalizedValue === undefined) continue;
      nextDraft[field] = normalizedValue;
      nextFieldMeta[field] = meta;
      updatedFields.add(field);
      continue;
    }

    if (operation.op === 'append') {
      if (field === 'key_points' || field === 'examples' || field === 'do_not_say') {
        const current = normalizeRuleConfigStringArray(nextDraft[field]);
        const incoming = normalizeRuleConfigStringArray(operation.value);
        const merged = mergeStringItems(current, incoming);
        if (merged.length > 0) {
          nextDraft[field] = merged;
          nextFieldMeta[field] = meta;
          updatedFields.add(field);
        }
        continue;
      }
      if (field === 'required_info') {
        const current = normalizeRequiredInfoEntries(nextDraft[field]);
        const incoming = normalizeRequiredInfoEntries(operation.value);
        const merged = mergeRequiredInfoItems(current, incoming);
        if (merged.length > 0) {
          nextDraft[field] = merged;
          nextFieldMeta[field] = meta;
          updatedFields.add(field);
        }
        continue;
      }
    }

    if (operation.op === 'remove') {
      if (field === 'key_points' || field === 'examples' || field === 'do_not_say') {
        const current = normalizeRuleConfigStringArray(nextDraft[field]);
        const removals = normalizeRuleConfigStringArray(operation.value);
        const remaining = removeStringItems(current, removals);
        if (remaining.length > 0) {
          nextDraft[field] = remaining;
          nextFieldMeta[field] = meta;
        } else {
          delete nextDraft[field];
          delete nextFieldMeta[field];
        }
        updatedFields.add(field);
        continue;
      }
      if (field === 'required_info') {
        const current = normalizeRequiredInfoEntries(nextDraft[field]);
        const removals = normalizeRequiredInfoEntries(operation.value);
        const remaining = removeRequiredInfoItems(current, removals);
        if (remaining.length > 0) {
          nextDraft[field] = remaining;
          nextFieldMeta[field] = meta;
        } else {
          delete nextDraft[field];
          delete nextFieldMeta[field];
        }
        updatedFields.add(field);
        continue;
      }
    }
  }

  return {
    draft: nextDraft,
    field_meta: nextFieldMeta,
    updated_fields: Array.from(updatedFields),
  };
}

export function hasRuleConfigFieldValue(field: string, value: unknown): boolean {
  void field;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (value && typeof value === 'object') return Object.keys(value as Record<string, unknown>).length > 0;
  return false;
}

export function computeRuleConfigMissingFields(
  draft: Record<string, unknown>,
  fieldMeta: Record<string, RuleFieldMeta>
): string[] {
  const missing: string[] = [];
  for (const field of ['name', 'match_text', 'reply_goal']) {
    if (!hasRuleConfigFieldValue(field, draft[field])) {
      missing.push(field);
      continue;
    }
    const meta = fieldMeta[field];
    if (!meta || meta.source === 'inferred' || meta.confidence === 'low') {
      missing.push(field);
    }
  }
  const hasKeyPoints = hasRuleConfigFieldValue('key_points', draft.key_points);
  const hasRequiredInfo = hasRuleConfigFieldValue('required_info', draft.required_info);
  if (!hasKeyPoints && !hasRequiredInfo) {
    missing.push('key_points');
  }
  return Array.from(new Set(missing));
}

export function computeRuleConfigState(
  draft: Record<string, unknown>,
  fieldMeta: Record<string, RuleFieldMeta>,
  fallback: RuleConfigState = 'collecting'
): RuleConfigState {
  if (fallback === 'cancelled' || fallback === 'saved' || fallback === 'blocked_conflict' || fallback === 'rework') {
    return fallback;
  }
  const missing = computeRuleConfigMissingFields(draft, fieldMeta);
  return missing.length === 0 ? 'awaiting_confirm' : 'collecting';
}

export function normalizeRuleReworkTicket(value: unknown): RuleReworkTicket | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  return {
    missing_fields: normalizeRuleConfigStringArray(record.missing_fields),
    conflicts: normalizeRuleConfigStringArray(record.conflicts),
    hint: typeof record.hint === 'string' ? record.hint.trim() || undefined : undefined,
  };
}

export function hasUnsafeTemplatePlaceholder(value: unknown): boolean {
  return typeof value === 'string' && RULE_CONFIG_PLACEHOLDER_PATTERN.test(value);
}

export function buildFallbackTemplate(rule: Record<string, unknown>): string {
  const replyGoal = typeof rule.reply_goal === 'string' ? rule.reply_goal.trim() : '';
  const keyPoints = normalizeRuleConfigStringArray(rule.key_points).slice(0, 3);
  const parts = [replyGoal, ...keyPoints].filter(Boolean);
  return parts.length ? `${parts.join('；')}。` : '请按既定流程处理，并向用户说明后续步骤。';
}

export function renderRuleConfigQuestionFromField(field?: string): string {
  if (!field) return '请继续补充这条规则最关键的信息。';
  const prompts: Record<string, string> = {
    name: '这条规则的名称想定成什么？',
    match_text: '用户在什么情况下会触发这条规则？',
    reply_goal: '这条规则希望系统最终怎么回复用户？',
    key_points: '回复里最关键的 2 到 3 个要点是什么？',
    required_info: '如果信息不全，最需要补问用户哪一项？',
  };
  return prompts[field] ?? `请补充${toRuleConfigFieldLabel(field)}。`;
}

export function renderRuleConfigAssistantMessage(options: {
  state: RuleConfigState;
  updatedFields?: string[];
  missingFields?: string[];
  nextQuestion?: string;
  reworkTicket?: RuleReworkTicket | null;
  conflictMessage?: string;
  savedMessage?: string;
}): string {
  const updatedFields = (options.updatedFields ?? []).map(toRuleConfigFieldLabel);
  const updatedPrefix = updatedFields.length ? `已记录${updatedFields.join('、')}。` : '';
  if (options.state === 'saved') {
    return options.savedMessage || '规则已保存。';
  }
  if (options.state === 'cancelled') {
    return '已退出规则配置流程。';
  }
  if (options.state === 'blocked_conflict') {
    return options.conflictMessage || '检测到规则冲突，请先处理冲突后再保存。';
  }
  if (options.state === 'rework') {
    const ticket = options.reworkTicket;
    const issueText = [
      ...(ticket?.missing_fields ?? []).map(toRuleConfigFieldLabel),
      ...(ticket?.conflicts ?? []),
    ]
      .filter(Boolean)
      .join('、');
    const hint = ticket?.hint?.trim();
    const question = options.nextQuestion?.trim() || hint || renderRuleConfigQuestionFromField(ticket?.missing_fields?.[0]);
    return `${updatedPrefix}${issueText ? `编译前还需要返工：${issueText}。` : '这条规则还需要返工。'}${question}`.trim();
  }
  if (options.state === 'awaiting_confirm') {
    return `${updatedPrefix}规则已可确认，回复“确认”即可保存。`.trim();
  }
  const question =
    options.nextQuestion?.trim() || renderRuleConfigQuestionFromField((options.missingFields ?? [])[0]);
  return `${updatedPrefix}${question}`.trim();
}

export function buildRuleConfigMetadata(
  draft: RuleDraft,
  extras?: {
    updated_fields?: string[];
    conflict?: Record<string, unknown>;
  }
): Record<string, unknown> {
  return {
    rule_config: {
      state: draft.state,
      status: draft.state,
      mode: draft.mode,
      rule_id: draft.rule_id,
      updated_fields: extras?.updated_fields ?? draft.updated_fields,
      missing_fields: draft.missing_fields,
      rework_ticket: draft.rework_ticket ?? null,
      conflict: extras?.conflict,
      draft,
    },
  };
}

export function buildInitialRuleFieldMeta(
  draft: Record<string, unknown>,
  createId: CreateId
): Record<string, RuleFieldMeta> {
  const result: Record<string, RuleFieldMeta> = {};
  for (const field of RULE_CONFIG_FIELDS) {
    if (hasRuleConfigFieldValue(field, draft[field])) {
      result[field] = {
        source: 'explicit',
        confidence: 'high',
        turn_id: createId('turn'),
      };
    }
  }
  return result;
}

export type { CreateId, LegacyRuleDraftStatus };
