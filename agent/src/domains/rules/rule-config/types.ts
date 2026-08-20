export type RuleConfigState =
  | 'collecting'
  | 'awaiting_confirm'
  | 'compiling'
  | 'rework'
  | 'blocked_conflict'
  | 'saved'
  | 'cancelled';

export type LegacyRuleDraftStatus = 'collecting' | 'ready_for_confirm' | 'blocked' | 'cancelled';
export type RuleDraftStatus = RuleConfigState | LegacyRuleDraftStatus;
export type RuleDraftMode = 'create' | 'edit';
export type RuleConfigIntent = 'provide_info' | 'confirm' | 'revise' | 'cancel' | 'unknown';
export type RuleFieldSource = 'explicit' | 'inferred' | 'builder_fix';
export type RuleFieldConfidence = 'high' | 'medium' | 'low';

export interface RuleFieldMeta {
  source: RuleFieldSource;
  turn_id: string;
  confidence: RuleFieldConfidence;
}

export interface RuleReworkTicket {
  missing_fields: string[];
  conflicts: string[];
  hint?: string;
}

export interface RuleDraft {
  session_id: string;
  status: RuleConfigState;
  state: RuleConfigState;
  mode: RuleDraftMode;
  rule_id?: string | null;
  draft: Record<string, unknown>;
  field_meta: Record<string, RuleFieldMeta>;
  missing_fields: string[];
  updated_fields: string[];
  rework_ticket?: RuleReworkTicket | null;
  updated_at: string;
}

export type RuleTurnOperationType = 'set' | 'append' | 'remove' | 'clear';

export interface RuleTurnOperation {
  field: string;
  op: RuleTurnOperationType;
  value?: unknown;
}

export interface RuleTurnProposal {
  session_id: string;
  patch: Record<string, unknown>;
  operations: RuleTurnOperation[];
  field_meta: Record<string, RuleFieldMeta>;
  intent: RuleConfigIntent;
  next_question?: string;
  missing_fields_guess: string[];
}

export interface BuilderCompileResult {
  status: 'ok' | 'needs_rework' | 'blocked_conflict';
  compiled_rule?: Record<string, unknown>;
  applied_low_risk_patch?: Record<string, unknown>;
  missing_fields: string[];
  conflicts: string[];
  rework_hint?: string;
}

export type RuleRequiredInfoItem = string | { key: string; ask: string; required: boolean };
