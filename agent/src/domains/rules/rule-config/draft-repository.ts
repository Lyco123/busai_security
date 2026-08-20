import { safeJsonParse } from '../../../shared/json';
import type { D1Database } from '../../scenarios/repository';
import { normalizeRuleFieldMetaRecord } from './pure';
import {
  computeRuleConfigMissingFields,
  normalizeRuleConfigState,
  normalizeRuleReworkTicket,
} from './state-machine';
import type {
  LegacyRuleDraftStatus,
  RuleConfigState,
  RuleDraft,
  RuleDraftMode,
  RuleFieldMeta,
  RuleReworkTicket,
} from './types';

function parseUpdatedFields(value?: string[] | string): string[] {
  if (typeof value === 'string') {
    const parsed = safeJsonParse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
  }
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

export function createRuleDraftRepository(createId: (prefix: string) => string) {
  async function getRuleDraft(db: D1Database, sessionId: string): Promise<RuleDraft | null> {
    const row = await db
      .prepare(
        'SELECT session_id, status, mode, rule_id, draft, field_meta, rework_ticket, updated_at FROM rule_drafts WHERE session_id = ?'
      )
      .bind(sessionId)
      .first<{
        session_id: string;
        status: string;
        mode: string;
        rule_id: string | null;
        draft: string;
        field_meta?: string | null;
        rework_ticket?: string | null;
        updated_at: string;
      }>();
    if (!row) return null;
    const parsed = safeJsonParse(row.draft);
    const state = normalizeRuleConfigState(row.status);
    const fieldMeta = normalizeRuleFieldMetaRecord(safeJsonParse(row.field_meta ?? 'null'), createId);
    const draftData = (parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}) as Record<string, unknown>;
    return {
      session_id: row.session_id,
      status: state,
      state,
      mode: row.mode as RuleDraftMode,
      rule_id: row.rule_id,
      draft: draftData,
      field_meta: fieldMeta,
      missing_fields: computeRuleConfigMissingFields(draftData, fieldMeta),
      updated_fields: [],
      rework_ticket: normalizeRuleReworkTicket(safeJsonParse(row.rework_ticket ?? 'null')),
      updated_at: row.updated_at,
    };
  }

  async function upsertRuleDraft(
    db: D1Database,
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
  ): Promise<RuleDraft> {
    const now = new Date().toISOString();
    const sessionId = draft.session_id || draft.sessionId;
    if (!sessionId) {
      throw new Error('session_id is required');
    }
    if (!draft.status && !draft.state) {
      throw new Error('state is required');
    }
    if (!draft.mode) {
      throw new Error('mode is required');
    }

    const ruleId = draft.rule_id ?? draft.ruleId ?? null;
    const state = normalizeRuleConfigState(draft.state ?? draft.status);

    let draftData: Record<string, unknown>;
    if (draft.draft) {
      if (typeof draft.draft === 'string') {
        const parsed = safeJsonParse(draft.draft);
        draftData =
          parsed && typeof parsed === 'object' && !Array.isArray(parsed)
            ? (parsed as Record<string, unknown>)
            : {};
      } else {
        draftData = draft.draft;
      }
    } else {
      draftData = {};
    }

    const fieldMeta =
      typeof draft.field_meta === 'string'
        ? normalizeRuleFieldMetaRecord(safeJsonParse(draft.field_meta), createId)
        : normalizeRuleFieldMetaRecord(draft.field_meta ?? {}, createId);
    const updatedFields = parseUpdatedFields(draft.updated_fields);
    const reworkTicket =
      typeof draft.rework_ticket === 'string'
        ? normalizeRuleReworkTicket(safeJsonParse(draft.rework_ticket))
        : normalizeRuleReworkTicket(draft.rework_ticket ?? null);
    const missingFields = computeRuleConfigMissingFields(draftData, fieldMeta);

    await db
      .prepare(
        'INSERT INTO rule_drafts (session_id, status, mode, rule_id, draft, field_meta, rework_ticket, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET status = excluded.status, mode = excluded.mode, rule_id = excluded.rule_id, draft = excluded.draft, field_meta = excluded.field_meta, rework_ticket = excluded.rework_ticket, updated_at = excluded.updated_at'
      )
      .bind(
        sessionId,
        state,
        draft.mode,
        ruleId,
        JSON.stringify(draftData),
        JSON.stringify(fieldMeta),
        JSON.stringify(reworkTicket),
        now
      )
      .run();

    return {
      session_id: sessionId,
      status: state,
      state,
      mode: draft.mode,
      rule_id: ruleId,
      draft: draftData,
      field_meta: fieldMeta,
      missing_fields: missingFields,
      updated_fields: updatedFields,
      rework_ticket: reworkTicket,
      updated_at: now,
    };
  }

  async function clearRuleDraft(db: D1Database, sessionId: string): Promise<void> {
    const now = new Date().toISOString();
    await db
      .prepare('UPDATE rule_drafts SET status = ?, rework_ticket = ?, updated_at = ? WHERE session_id = ?')
      .bind('cancelled', null, now, sessionId)
      .run();
  }

  return {
    clearRuleDraft,
    getRuleDraft,
    upsertRuleDraft,
  };
}
