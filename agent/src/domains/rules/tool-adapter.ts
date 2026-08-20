import { safeJsonParse } from '../../shared/json';
import type { D1Database } from '../scenarios/repository';
import {
  normalizeRuleConfigIntent,
  normalizeRuleConfigStringArray,
  normalizeRuleFieldMetaInput,
  normalizeRuleTurnOperations,
  sanitizeRuleConfigPatch,
} from './rule-config/pure';
import { normalizeRuleConfigState } from './rule-config/state-machine';
import type {
  LegacyRuleDraftStatus,
  RuleDraft,
  RuleConfigState,
  RuleDraftMode,
  RuleFieldMeta,
  RuleReworkTicket,
  RuleTurnProposal,
} from './rule-config/types';
import { getRuleByIdOrName } from './repository';

type D1DatabaseLike = D1Database;

export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
  error_code?: number | string;
}

export interface RuleJson {
  id?: string;
  name?: string;
  match_text?: string;
  template?: string;
  reply_goal?: string;
  key_points?: string[];
  required_info?: Array<{ key: string; ask: string; required?: boolean }>;
  safe_defaults?: Record<string, string>;
  do_not_say?: string[];
  tone?: string;
  [key: string]: unknown;
}

export function createRuleToolAdapter(deps: {
  createId: (prefix: string) => string;
  getRuleDraft: (db: D1DatabaseLike, sessionId: string) => Promise<RuleDraft | null>;
  upsertRuleDraft: (
    db: D1DatabaseLike,
    draft: {
      session_id?: string;
      sessionId?: string;
      status?: RuleConfigState | LegacyRuleDraftStatus;
      state?: RuleConfigState | LegacyRuleDraftStatus;
      mode?: RuleDraftMode;
      rule_id?: string | null;
      ruleId?: string | null;
      draft?: Record<string, unknown> | string;
      noop?: boolean;
      field_meta?: Record<string, RuleFieldMeta> | string;
      rework_ticket?: RuleReworkTicket | null | string;
      updated_fields?: string[] | string;
    }
  ) => Promise<RuleDraft>;
}) {
  function normalizeRuleFieldMetaInputWithIds(
    value: unknown,
    defaultTurnId: string
  ): Record<string, RuleFieldMeta> {
    return normalizeRuleFieldMetaInput(value, defaultTurnId, deps.createId);
  }

  async function executeGetRule(
    db: D1DatabaseLike,
    args: { rule_id?: string }
  ): Promise<{ success: boolean; data?: RuleJson; error?: string }> {
    const ruleId = String(args.rule_id ?? '').trim();
    if (!ruleId) {
      return { success: false, error: 'rule_id is required' };
    }

    const record = await getRuleByIdOrName(db, ruleId);
    if (!record) {
      return { success: false, error: `rule_not_found: ${ruleId}` };
    }

    return {
      success: true,
      data: {
        id: record.id,
        name: record.name,
        match_text: record.match_text,
        ...record.data,
      },
    };
  }

  async function executeGetRuleDraft(
    db: D1DatabaseLike,
    args: { session_id?: string; sessionId?: string }
  ): Promise<ToolResult> {
    const sessionId = String(args.session_id || args.sessionId || '').trim();
    if (!sessionId) {
      return { success: false, error: 'session_id is required' };
    }
    const draft = await deps.getRuleDraft(db, sessionId);
    if (!draft) {
      return { success: false, error: 'rule_draft_not_found' };
    }
    return {
      success: true,
      data: draft,
    };
  }

  async function executeUpdateRuleDraft(
    db: D1DatabaseLike,
    args: {
      session_id?: string;
      sessionId?: string;
      status?: RuleConfigState | LegacyRuleDraftStatus;
      mode?: RuleDraftMode;
      rule_id?: string | null;
      ruleId?: string | null;
      draft?: Record<string, unknown> | string;
      noop?: boolean;
    }
  ): Promise<ToolResult> {
    const sessionId = String(args.session_id || args.sessionId || '').trim();
    if (!sessionId) {
      return { success: false, error: 'session_id is required' };
    }
    const existing = await deps.getRuleDraft(db, sessionId);
    const noop = args.noop === true;
    const incomingDraftRaw = args.draft;
    let incomingDraft: Record<string, unknown> = {};
    if (!noop) {
      if (incomingDraftRaw && typeof incomingDraftRaw === 'object' && !Array.isArray(incomingDraftRaw)) {
        incomingDraft = incomingDraftRaw;
      } else if (typeof incomingDraftRaw === 'string') {
        const parsed = safeJsonParse(incomingDraftRaw);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          incomingDraft = parsed as Record<string, unknown>;
        }
      }
    }
    const baseDraft = existing?.draft ?? {};
    const mergedDraft = noop ? baseDraft : { ...baseDraft, ...incomingDraft };
    const status = normalizeRuleConfigState(args.status ?? existing?.status ?? 'collecting');
    const mode = args.mode ?? existing?.mode ?? 'create';
    const ruleId = args.rule_id ?? args.ruleId ?? existing?.rule_id ?? null;
    const saved = await deps.upsertRuleDraft(db, {
      session_id: sessionId,
      state: status,
      mode,
      rule_id: ruleId,
      draft: mergedDraft,
      field_meta: existing?.field_meta ?? {},
      updated_fields: noop ? [] : Object.keys(incomingDraft),
      rework_ticket: existing?.rework_ticket ?? null,
    });
    return { success: true, data: saved };
  }

  async function executeSubmitRuleTurn(
    _db: D1DatabaseLike,
    args: Record<string, unknown>
  ): Promise<ToolResult> {
    const sessionId = String(args.session_id ?? args.sessionId ?? '').trim();
    if (!sessionId) {
      return { success: false, error: 'session_id is required' };
    }
    const turnId = deps.createId('turn');
    const patch = sanitizeRuleConfigPatch(args.patch);
    const operations = normalizeRuleTurnOperations(args.operations, patch);
    const fieldMeta = normalizeRuleFieldMetaInputWithIds(args.field_meta, turnId);
    return {
      success: true,
      data: {
        session_id: sessionId,
        patch,
        operations,
        field_meta: fieldMeta,
        intent: normalizeRuleConfigIntent(args.intent),
        next_question: typeof args.next_question === 'string' ? args.next_question.trim() : undefined,
        missing_fields_guess: normalizeRuleConfigStringArray(args.missing_fields_guess),
      } satisfies RuleTurnProposal,
    };
  }

  return {
    executeGetRule,
    executeGetRuleDraft,
    executeUpdateRuleDraft,
    executeSubmitRuleTurn,
  };
}
