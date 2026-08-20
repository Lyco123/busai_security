import ruleAskerSkill from '../../../../skills/conversational/rule_asker/SKILL.md';
import ruleBuilderSkill from '../../../../skills/structured/rule_builder/SKILL.md';
import { callOpenAI, callOpenAIWithTools } from '../../../infra/llm/chat-completions';
import { callOpenAIEmbedding } from '../../../infra/llm/openai-client';
import { safeJsonParse } from '../../../shared/json';
import { collapseWhitespace } from '../../../shared/text';
import { buildWorkerPrompt, type ToolDefinition, type ToolProvider, type ToolResult } from '../../chat/worker-runner';
import { buildContextFromHistory, type HistoryMessage } from '../../chat/context';
import {
  computeRuleMatchScore,
  detectRuleConflict as detectRuleConflictService,
  generateRuleEmbedding as generateRuleEmbeddingService,
} from '../match-service';
import { getRuleById, insertRule, listRules, updateRule, type RuleRecord } from '../repository';
import {
  applyRuleTurnOperations,
  buildInitialRuleFieldMeta,
  buildFallbackTemplate,
  hasUnsafeTemplatePlaceholder,
  normalizeRequiredInfoEntries,
  normalizeRuleConfigFieldValue,
  normalizeRuleConfigIntent,
  normalizeRuleConfigStringArray,
  normalizeRuleFieldMetaInput,
  normalizeRuleTurnOperations,
  sanitizeRuleConfigPatch,
} from './pure';
import {
  buildRuleConfigMetadata,
  computeRuleConfigState,
  computeRuleConfigMissingFields,
  normalizeRuleConfigState,
  renderRuleConfigAssistantMessage,
} from './state-machine';
import type {
  BuilderCompileResult,
  RuleConfigState,
  RuleDraft,
  RuleDraftMode,
  RuleTurnOperation,
  RuleTurnProposal,
  RuleReworkTicket,
} from './types';

interface RuleConfigEnv {
  DB: any;
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_EMBEDDING_MODEL?: string;
  OPENAI_MODEL?: string;
  OPENAI_WORKER_MODEL?: string;
  RULE_CONFIG_STATE_MACHINE_V2?: string;
}

interface AgentSessionMessage {
  role: string;
  content: string;
}

interface RuleMatchItem {
  rule_id?: string;
  rule_name?: string;
  score?: number;
  metadata?: { match_text?: string; tone?: string };
}

interface RuleDraftTestResultItem {
  query: string;
  draft_score?: number;
  draft_rank?: number;
  total_rules?: number;
  would_trigger?: boolean;
  top_matches: RuleMatchItem[];
  reply_preview?: string;
  error?: string;
}

interface RuleDraftTestResponse {
  session_id: string;
  rule_id?: string | null;
  draft_name?: string;
  match_text?: string;
  suggested_queries: string[];
  results: RuleDraftTestResultItem[];
}

type RefreshPlan = { examples: boolean; template: boolean; safe_defaults: boolean };

interface RuleConfigServiceDeps {
  DEFAULT_MODEL: string;
  LOW_RISK_BUILDER_FIELDS: readonly string[];
  RULE_MATCH_THRESHOLD: number;
  MAX_TOOL_ITERATIONS: number;
  createId: (prefix: string) => string;
  normalizeExamples: (value: unknown, matchText: string) => string[];
  createAgentSession: (
    db: any,
    title: string,
    ownerId?: any
  ) => Promise<{ id: string }>;
  getAgentSession: (
    db: any,
    sessionId: string
  ) => Promise<{ messages?: AgentSessionMessage[] } | null>;
  getRuleDraft: (db: any, sessionId: string) => Promise<RuleDraft | null>;
  upsertRuleDraft: (db: any, draft: any) => Promise<RuleDraft>;
  clearRuleDraft: (db: any, sessionId: string) => Promise<void>;
  isRuleConfigStateMachineV2Enabled: (env: any) => boolean;
  createToolProvider: (env: any) => ToolProvider;
  createScopedToolProvider: (
    baseProvider: ToolProvider,
    tools: Record<string, (args: Record<string, unknown>) => Promise<ToolResult>>,
    allowList: Set<string>
  ) => ToolProvider;
  toOpenAIToolSchema: (tool: ToolDefinition) => { type: 'function'; function: ToolDefinition };
  runWorkerWithTools: (
    env: any,
    workerTool: 'rule_reply' | 'rule_asker',
    userQuery: string,
    isStream?: boolean,
    toolProvider?: ToolProvider,
    historyMessages?: HistoryMessage[]
  ) => Promise<{ content: string | ReadableStream; metadata?: Record<string, unknown> }>;
}

export interface SaveRuleConfigSessionResult {
  state: RuleConfigState;
  message: string;
  rule_id?: string;
  conflict?: { level: string; match?: { rule_id: string; rule_name: string; score: number } };
  draft: RuleDraft;
}

export interface StartRuleConfigSessionResult {
  session_id: string;
  draft: RuleDraft;
}

export interface ConfirmRuleConfigSessionResult {
  status: RuleConfigState | 'ready_for_confirm' | 'blocked' | 'cancelled';
  state: RuleConfigState;
  rule_id?: string;
  conflict?: { level: string; match?: { rule_id: string; rule_name: string; score: number } };
  message: string;
  draft: RuleDraft;
  missing_fields: string[];
  updated_fields: string[];
  rework_ticket?: RuleReworkTicket | null;
}

export function createRuleConfigService(deps: RuleConfigServiceDeps) {
  async function extractRuleConfigConversationContext(
    db: any,
    sessionId: string
  ): Promise<{ transcript: string; latestUserMessage: string }> {
    const session = await deps.getAgentSession(db, sessionId);
    if (!session?.messages?.length) {
      return { transcript: '', latestUserMessage: '' };
    }
    const relevantMessages = session.messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .slice(-20);
    let latestUserMessage = '';
    for (let index = relevantMessages.length - 1; index >= 0; index -= 1) {
      if (relevantMessages[index].role === 'user') {
        latestUserMessage = relevantMessages[index].content || '';
        break;
      }
    }
    return {
      transcript: relevantMessages
        .map((message) => `${message.role === 'user' ? '用户' : '助手'}: ${message.content}`)
        .join('\n\n'),
      latestUserMessage,
    };
  }

  function normalizeBuilderCompileResult(value: unknown): BuilderCompileResult {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new Error('rule_builder_output_invalid');
    }
    const record = value as Record<string, unknown>;
    const status = String(record.status ?? '').trim();
    if (status === 'ok' || status === 'needs_rework' || status === 'blocked_conflict') {
      return {
        status,
        compiled_rule:
          record.compiled_rule && typeof record.compiled_rule === 'object' && !Array.isArray(record.compiled_rule)
            ? (record.compiled_rule as Record<string, unknown>)
            : undefined,
        applied_low_risk_patch: sanitizeRuleConfigPatch(record.applied_low_risk_patch),
        missing_fields: normalizeRuleConfigStringArray(record.missing_fields),
        conflicts: normalizeRuleConfigStringArray(record.conflicts),
        rework_hint: typeof record.rework_hint === 'string' ? record.rework_hint.trim() : undefined,
      };
    }
    return {
      status: 'ok',
      compiled_rule: record,
      applied_low_risk_patch: {},
      missing_fields: [],
      conflicts: [],
    };
  }

  function detectRuleDraftRefreshPlan(
    draft: RuleDraft,
    existingRule?: RuleRecord | null
  ): RefreshPlan {
    if (draft.mode !== 'edit' || !existingRule) {
      return { examples: false, template: false, safe_defaults: false };
    }
    const existingData = existingRule.data || {};
    const nextDraft = draft.draft || {};
    const matchTextChanged =
      String(nextDraft.match_text ?? '').trim() !== String(existingRule.match_text ?? '').trim();
    const replyGoalChanged =
      String(nextDraft.reply_goal ?? '').trim() !== String(existingData.reply_goal ?? '').trim();
    const keyPointsChanged =
      JSON.stringify(normalizeRuleConfigStringArray(nextDraft.key_points)) !==
      JSON.stringify(normalizeRuleConfigStringArray(existingData.key_points));
    const requiredInfoChanged =
      JSON.stringify(normalizeRequiredInfoEntries(nextDraft.required_info)) !==
      JSON.stringify(normalizeRequiredInfoEntries(existingData.required_info));
    return {
      examples: matchTextChanged,
      template: matchTextChanged || replyGoalChanged || keyPointsChanged || requiredInfoChanged,
      safe_defaults: matchTextChanged || replyGoalChanged || keyPointsChanged || requiredInfoChanged,
    };
  }

  function prepareRuleDraftForCompilation(
    draft: RuleDraft,
    refreshPlan: RefreshPlan
  ): Record<string, unknown> {
    const nextDraft = { ...draft.draft };
    if (refreshPlan.examples) {
      delete nextDraft.examples;
    }
    if (refreshPlan.template) {
      delete nextDraft.template;
    }
    if (refreshPlan.safe_defaults) {
      delete nextDraft.safe_defaults;
    }
    return nextDraft;
  }

  async function compileRuleConfigSession(
    env: RuleConfigEnv,
    sessionId: string,
    mode: RuleDraftMode,
    draft: Record<string, unknown>,
    refreshPlan?: RefreshPlan
  ): Promise<BuilderCompileResult> {
    const context = await extractRuleConfigConversationContext(env.DB, sessionId);
    const compileInput = refreshPlan
      ? prepareRuleDraftForCompilation(
          {
            session_id: sessionId,
            status: 'collecting',
            state: 'collecting',
            mode,
            rule_id: null,
            draft,
            field_meta: {},
            missing_fields: [],
            updated_fields: [],
            rework_ticket: null,
            updated_at: new Date().toISOString(),
          },
          refreshPlan
        )
      : draft;
    const prompt = `请将 rule_draft 编译并校验为结构化结果，只返回严格 JSON：{
  "draft_mode": ${JSON.stringify(mode)},
  "latest_user_request": ${JSON.stringify(context.latestUserMessage)},
  "refresh_hints": ${JSON.stringify(refreshPlan ?? { examples: false, template: false, safe_defaults: false })},
  "rule_draft": ${JSON.stringify(compileInput, null, 2)},
  "conversation_context": ${JSON.stringify(context.transcript)}
}`;
    const response = await callOpenAI(env, {
      model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
      temperature: 0.2,
      messages: [
        { role: 'system', content: ruleBuilderSkill },
        { role: 'user', content: prompt },
      ],
      responseFormat: 'json_object',
    });
    return normalizeBuilderCompileResult(safeJsonParse(response));
  }

  async function compileRuleDraft(
    env: RuleConfigEnv,
    draft: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const prompt = `请将 rule_draft 编译成 rule_json，只返回严格 JSON：${JSON.stringify(draft, null, 2)}`;
    const response = await callOpenAI(env, {
      model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
      temperature: 0.2,
      messages: [
        { role: 'system', content: ruleBuilderSkill },
        { role: 'user', content: prompt },
      ],
      responseFormat: 'json_object',
    });
    const parsed = safeJsonParse(response);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('rule_builder_output_invalid');
    }
    return parsed as Record<string, unknown>;
  }

  function applyLowRiskBuilderPatch(
    draft: RuleDraft,
    patch: Record<string, unknown> | undefined
  ): RuleDraft {
    const sanitizedPatch: Record<string, unknown> = {};
    for (const field of deps.LOW_RISK_BUILDER_FIELDS) {
      if (patch && field in patch) {
        const value = normalizeRuleConfigFieldValue(field, patch[field]);
        if (value !== undefined) {
          sanitizedPatch[field] = value;
        }
      }
    }
    if (!Object.keys(sanitizedPatch).length) {
      return draft;
    }
    const nextDraftData = { ...draft.draft, ...sanitizedPatch };
    const nextFieldMeta = { ...draft.field_meta };
    for (const field of Object.keys(sanitizedPatch)) {
      nextFieldMeta[field] = {
        source: 'builder_fix',
        confidence: 'medium',
        turn_id: deps.createId('turn'),
      };
    }
    return {
      ...draft,
      draft: nextDraftData,
      field_meta: nextFieldMeta,
      updated_fields: Object.keys(sanitizedPatch),
      missing_fields: computeRuleConfigMissingFields(nextDraftData, nextFieldMeta),
    };
  }

  function normalizeRuleConflictText(value: string): string {
    return collapseWhitespace(value).replace(/[，。！？；：,.!?:;\s]/g, '').trim();
  }

  function stripNegativeRuleConstraint(value: string): string {
    const normalized = normalizeRuleConflictText(value);
    const prefixes = ['不要建议', '不要继续', '不要直接', '不要', '别再', '别', '不得', '严禁', '禁止'];
    for (const prefix of prefixes) {
      const normalizedPrefix = normalizeRuleConflictText(prefix);
      if (normalized.startsWith(normalizedPrefix)) {
        return normalized.slice(normalizedPrefix.length).trim();
      }
    }
    return normalized;
  }

  function detectRuleDraftInternalConflicts(rule: Record<string, unknown>): string[] {
    const doNotSay = normalizeRuleConfigStringArray(rule.do_not_say);
    if (!doNotSay.length) return [];
    const positiveTexts = [
      String(rule.reply_goal ?? ''),
      String(rule.template ?? ''),
      ...normalizeRuleConfigStringArray(rule.key_points),
    ]
      .map(normalizeRuleConflictText)
      .filter((item) => item.length >= 4);
    if (!positiveTexts.length) return [];
    const conflicts = new Set<string>();
    for (const raw of doNotSay) {
      const normalizedRaw = raw.trim();
      const constrained = stripNegativeRuleConstraint(normalizedRaw);
      if (constrained.length < 4) continue;
      const hasConflict = positiveTexts.some(
        (item) => item.includes(constrained) || constrained.includes(item)
      );
      if (hasConflict) {
        conflicts.add(`"${normalizedRaw}" 与回复目标/要点/模板存在冲突`);
      }
    }
    return Array.from(conflicts);
  }

  function buildRuleConfirmBlockedMessage(draft: RuleDraft): string {
    if (draft.state === 'blocked_conflict') {
      return draft.rework_ticket?.hint?.trim() || '当前规则存在冲突，暂时不能直接确认保存。';
    }
    if (draft.state === 'rework') {
      return draft.rework_ticket?.hint?.trim() || '当前规则仍需返工，补充或修正后再确认保存。';
    }
    if (draft.state === 'saved') {
      return '当前规则已经保存。';
    }
    if (draft.state === 'cancelled') {
      return '当前规则配置已取消，不能继续保存。';
    }
    return '当前编辑仍需澄清，暂时不能确认保存。';
  }

  async function executeRuleDraftTest(
    env: RuleConfigEnv,
    sessionId: string,
    payload?: {
      queries?: string[];
      top_k?: number;
      min_score?: number;
      preview_reply?: boolean;
    }
  ): Promise<ToolResult> {
    const draft = await deps.getRuleDraft(env.DB, sessionId);
    if (!draft) {
      return { success: false, error: 'rule_draft_not_found' };
    }

    let compiled: Record<string, unknown>;
    try {
      if (deps.isRuleConfigStateMachineV2Enabled(env)) {
        const existingRule =
          draft.mode === 'edit' && draft.rule_id ? await getRuleById(env.DB, draft.rule_id) : null;
        const result = await compileRuleConfigSession(
          env,
          sessionId,
          draft.mode,
          draft.draft,
          detectRuleDraftRefreshPlan(draft, existingRule)
        );
        if (result.status !== 'ok' || !result.compiled_rule) {
          return { success: false, error: 'rule_builder_rework_required' };
        }
        compiled = result.compiled_rule;
      } else {
        compiled = await compileRuleDraft(env, draft.draft);
      }
    } catch {
      return { success: false, error: 'rule_builder_failed' };
    }

    const draftName = String(
      (compiled as Record<string, unknown>).name ??
        (draft.draft as Record<string, unknown>)?.name ??
        'rule_draft'
    );
    const matchText = String(
      (compiled as Record<string, unknown>).match_text ??
        (draft.draft as Record<string, unknown>)?.match_text ??
        ''
    ).trim();

    if (!matchText) {
      return { success: false, error: 'match_text_required' };
    }

    const suggestedQueries = deps.normalizeExamples(
      (compiled as Record<string, unknown>).examples ??
        (draft.draft as Record<string, unknown>)?.examples,
      matchText
    );

    const rawQueries = Array.isArray(payload?.queries) ? payload.queries : [];
    const normalizedQueries = rawQueries
      .map((item) => String(item ?? '').trim())
      .filter(Boolean)
      .slice(0, 10);
    const queries = normalizedQueries.length ? normalizedQueries : suggestedQueries;

    const examples = deps.normalizeExamples(
      (compiled as Record<string, unknown>).examples ??
        (draft.draft as Record<string, unknown>)?.examples,
      matchText
    );
    const draftEmbedding = await generateRuleEmbeddingService(env, matchText, examples);

    const rules = await listRules(env.DB, { includeDisabled: false, limit: 500 });
    const topK = Math.min(Math.max(Number(payload?.top_k ?? 5), 1), 20);
    const minScore = Number(payload?.min_score ?? 0.3);
    const previewReply = payload?.preview_reply !== false;

    const baseProvider = deps.createToolProvider(env);
    const draftRuleId = `draft_${sessionId}`;
    const compiledRule = {
      ...compiled,
      id: draftRuleId,
      name: draftName,
      match_text: matchText,
      examples,
    };
    const scopedProvider = deps.createScopedToolProvider(
      baseProvider,
      {
        get_rule: async (args) => {
          const ruleId = String(args?.rule_id ?? '').trim();
          if (!ruleId || ruleId !== draftRuleId) {
            return { success: false, error: 'rule_id_mismatch' };
          }
          return { success: true, data: compiledRule };
        },
      },
      new Set(['get_rule'])
    );

    const results: RuleDraftTestResultItem[] = [];

    for (const query of queries) {
      try {
        const queryEmbedding = await callOpenAIEmbedding(env, query);
        const scoredRules = rules.map((rule) => ({
          rule,
          score: computeRuleMatchScore(queryEmbedding, rule.embedding),
        }));
        const topMatches = scoredRules
          .filter((item) => item.score >= minScore)
          .sort((a, b) => b.score - a.score)
          .slice(0, topK)
          .map((item) => ({
            rule_id: item.rule.id,
            rule_name: item.rule.name,
            score: item.score,
            metadata: {
              match_text: item.rule.match_text,
              tone: (item.rule.data?.tone as string | undefined) ?? undefined,
            },
          }));

        const draftScore =
          draftEmbedding !== null && draftEmbedding !== undefined
            ? computeRuleMatchScore(queryEmbedding, draftEmbedding)
            : undefined;
        const maxScore = scoredRules.reduce((max, item) => Math.max(max, item.score), 0);
        const draftRank =
          draftScore !== undefined
            ? 1 + scoredRules.filter((item) => item.score > draftScore).length
            : undefined;
        const wouldTrigger =
          draftScore !== undefined &&
          draftScore >= deps.RULE_MATCH_THRESHOLD &&
          (scoredRules.length === 0 || draftScore >= maxScore);

        let replyPreview: string | undefined;
        if (previewReply) {
          const prompt = buildWorkerPrompt({
            tool: 'rule_reply',
            args: { rule_id: draftRuleId, user_query: query },
          });
          const replyResult = await deps.runWorkerWithTools(
            env,
            'rule_reply',
            prompt,
            false,
            scopedProvider
          );
          replyPreview = typeof replyResult.content === 'string' ? replyResult.content : undefined;
        }

        results.push({
          query,
          draft_score: draftScore,
          draft_rank: draftRank,
          total_rules: rules.length + 1,
          would_trigger: wouldTrigger,
          top_matches: topMatches,
          reply_preview: replyPreview,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        results.push({
          query,
          top_matches: [],
          error: message,
        });
      }
    }

    const response: RuleDraftTestResponse = {
      session_id: sessionId,
      rule_id: draft.rule_id ?? null,
      draft_name: draftName,
      match_text: matchText,
      suggested_queries: suggestedQueries,
      results,
    };

    return { success: true, data: response };
  }

  async function saveRuleConfigSessionV2(
    env: RuleConfigEnv,
    draft: RuleDraft,
    options?: { forceSave?: boolean }
  ): Promise<SaveRuleConfigSessionResult> {
    const currentState = normalizeRuleConfigState(draft.state ?? draft.status ?? 'collecting');
    const canAttemptSave =
      currentState === 'awaiting_confirm' ||
      (currentState === 'blocked_conflict' && Boolean(options?.forceSave));
    if (!canAttemptSave) {
      return {
        state: currentState,
        message: buildRuleConfirmBlockedMessage(draft),
        draft,
      };
    }

    const current = await deps.upsertRuleDraft(env.DB, {
      session_id: draft.session_id,
      state: 'compiling',
      mode: draft.mode,
      rule_id: draft.rule_id ?? null,
      draft: draft.draft,
      field_meta: draft.field_meta,
      updated_fields: [],
      rework_ticket: null,
    });

    const existingRule =
      current.mode === 'edit' && current.rule_id ? await getRuleById(env.DB, current.rule_id) : null;
    const refreshPlan = detectRuleDraftRefreshPlan(current, existingRule);
    let builderResult: BuilderCompileResult;
    try {
      builderResult = await compileRuleConfigSession(
        env,
        draft.session_id,
        current.mode,
        current.draft,
        refreshPlan
      );
    } catch {
      const reworkTicket: RuleReworkTicket = {
        missing_fields: current.missing_fields,
        conflicts: [],
        hint: '编译失败，请补充或改写关键信息后重试。',
      };
      const reworkDraft = await deps.upsertRuleDraft(env.DB, {
        session_id: current.session_id,
        state: 'rework',
        mode: current.mode,
        rule_id: current.rule_id ?? null,
        draft: current.draft,
        field_meta: current.field_meta,
        updated_fields: [],
        rework_ticket: reworkTicket,
      });
      return {
        state: 'rework',
        message: renderRuleConfigAssistantMessage({ state: 'rework', reworkTicket }),
        draft: reworkDraft,
      };
    }

    if (builderResult.status === 'needs_rework' || builderResult.status === 'blocked_conflict') {
      const reworkTicket: RuleReworkTicket = {
        missing_fields: builderResult.missing_fields,
        conflicts: builderResult.conflicts,
        hint: builderResult.rework_hint,
      };
      const nextState =
        builderResult.status === 'blocked_conflict' ? 'blocked_conflict' : 'rework';
      const nextDraft = await deps.upsertRuleDraft(env.DB, {
        session_id: current.session_id,
        state: nextState,
        mode: current.mode,
        rule_id: current.rule_id ?? null,
        draft: current.draft,
        field_meta: current.field_meta,
        updated_fields: [],
        rework_ticket: reworkTicket,
      });
      return {
        state: nextState,
        message: renderRuleConfigAssistantMessage({
          state: nextState,
          reworkTicket,
          conflictMessage: builderResult.rework_hint,
        }),
        draft: nextDraft,
      };
    }

    if (!builderResult.compiled_rule) {
      throw new Error('rule_builder_missing_compiled_rule');
    }

    const effectiveDraft = applyLowRiskBuilderPatch(current, builderResult.applied_low_risk_patch);
    const compiled = { ...builderResult.compiled_rule };
    const name = String((effectiveDraft.draft?.name as string) || '').trim();
    const matchText = String((effectiveDraft.draft?.match_text as string) || '').trim();
    if (!name || !matchText) {
      const reworkTicket: RuleReworkTicket = {
        missing_fields: computeRuleConfigMissingFields(effectiveDraft.draft, effectiveDraft.field_meta),
        conflicts: [],
        hint: '名称或触发场景仍不完整，请补充后再确认。',
      };
      const reworkDraft = await deps.upsertRuleDraft(env.DB, {
        session_id: effectiveDraft.session_id,
        state: 'rework',
        mode: effectiveDraft.mode,
        rule_id: effectiveDraft.rule_id ?? null,
        draft: effectiveDraft.draft,
        field_meta: effectiveDraft.field_meta,
        updated_fields: effectiveDraft.updated_fields,
        rework_ticket: reworkTicket,
      });
      return {
        state: 'rework',
        message: renderRuleConfigAssistantMessage({ state: 'rework', reworkTicket }),
        draft: reworkDraft,
      };
    }

    const existingTemplate = String(existingRule?.data?.template ?? '').trim();
    const existingSafeDefaults = normalizeRuleConfigFieldValue(
      'safe_defaults',
      existingRule?.data?.safe_defaults
    );
    const exampleSeed = refreshPlan.examples ? undefined : effectiveDraft.draft.examples;
    const examples = deps.normalizeExamples(
      (compiled as Record<string, unknown>).examples ?? exampleSeed,
      matchText
    );
    (compiled as Record<string, unknown>).examples = examples;
    if (
      !String((compiled as Record<string, unknown>).template ?? '').trim() ||
      hasUnsafeTemplatePlaceholder((compiled as Record<string, unknown>).template) ||
      (refreshPlan.template &&
        existingTemplate.length > 0 &&
        String((compiled as Record<string, unknown>).template ?? '').trim() === existingTemplate)
    ) {
      (compiled as Record<string, unknown>).template = buildFallbackTemplate(
        compiled as Record<string, unknown>
      );
    }
    if (refreshPlan.safe_defaults) {
      const compiledSafeDefaults = normalizeRuleConfigFieldValue(
        'safe_defaults',
        (compiled as Record<string, unknown>).safe_defaults
      );
      if (JSON.stringify(compiledSafeDefaults ?? {}) === JSON.stringify(existingSafeDefaults ?? {})) {
        delete (compiled as Record<string, unknown>).safe_defaults;
      }
    }
    const internalConflicts = detectRuleDraftInternalConflicts(compiled as Record<string, unknown>);
    if (internalConflicts.length > 0) {
      const reworkTicket: RuleReworkTicket = {
        missing_fields: [],
        conflicts: internalConflicts,
        hint: '当前规则内存在互相冲突的要求，请先明确允许什么、禁止什么。',
      };
      const reworkDraft = await deps.upsertRuleDraft(env.DB, {
        session_id: effectiveDraft.session_id,
        state: 'rework',
        mode: effectiveDraft.mode,
        rule_id: effectiveDraft.rule_id ?? null,
        draft: effectiveDraft.draft,
        field_meta: effectiveDraft.field_meta,
        updated_fields: effectiveDraft.updated_fields,
        rework_ticket: reworkTicket,
      });
      return {
        state: 'rework',
        message: renderRuleConfigAssistantMessage({ state: 'rework', reworkTicket }),
        draft: reworkDraft,
      };
    }

    const conflict = await detectRuleConflictService(env, matchText, effectiveDraft.rule_id ?? undefined);
    if (conflict.level === 'red' || (conflict.level === 'yellow' && !options?.forceSave)) {
      const blockedDraft = await deps.upsertRuleDraft(env.DB, {
        session_id: effectiveDraft.session_id,
        state: 'blocked_conflict',
        mode: effectiveDraft.mode,
        rule_id: effectiveDraft.rule_id ?? null,
        draft: effectiveDraft.draft,
        field_meta: effectiveDraft.field_meta,
        updated_fields: effectiveDraft.updated_fields,
        rework_ticket: {
          missing_fields: [],
          conflicts: [
            conflict.match?.rule_name ? `疑似与规则“${conflict.match.rule_name}”冲突` : '检测到规则冲突',
          ],
          hint:
            conflict.level === 'red'
              ? '请直接修改现有规则，或调整当前触发场景。'
              : '如需继续保存，请使用强制保存后再次确认。',
        },
      });
      return {
        state: 'blocked_conflict',
        message: renderRuleConfigAssistantMessage({
          state: 'blocked_conflict',
          conflictMessage:
            conflict.level === 'red'
              ? `检测到与现有规则“${conflict.match?.rule_name ?? ''}”高度重复，请先修改原规则或调整触发场景。`
              : `检测到与现有规则“${conflict.match?.rule_name ?? ''}”相似，如需继续保存，请使用强制保存。`,
        }),
        draft: blockedDraft,
        conflict,
      };
    }

    const embedding = await generateRuleEmbeddingService(env, matchText, examples);
    if (effectiveDraft.mode === 'edit' && effectiveDraft.rule_id) {
      const existing = await getRuleById(env.DB, effectiveDraft.rule_id);
      if (!existing) {
        const blockedDraft = await deps.upsertRuleDraft(env.DB, {
          session_id: effectiveDraft.session_id,
          state: 'blocked_conflict',
          mode: effectiveDraft.mode,
          rule_id: effectiveDraft.rule_id ?? null,
          draft: effectiveDraft.draft,
          field_meta: effectiveDraft.field_meta,
          updated_fields: effectiveDraft.updated_fields,
          rework_ticket: {
            missing_fields: [],
            conflicts: ['待编辑的规则不存在'],
            hint: '请重新进入编辑流程。',
          },
        });
        return {
          state: 'blocked_conflict',
          message: renderRuleConfigAssistantMessage({
            state: 'blocked_conflict',
            conflictMessage: '找不到要编辑的规则。',
          }),
          draft: blockedDraft,
        };
      }
      await updateRule(env.DB, existing.id, {
        name,
        match_text: matchText,
        embedding: embedding ?? existing.embedding ?? null,
        data: compiled,
        version: existing.version + 1,
      });
      const savedDraft = await deps.upsertRuleDraft(env.DB, {
        session_id: effectiveDraft.session_id,
        state: 'saved',
        mode: effectiveDraft.mode,
        rule_id: existing.id,
        draft: effectiveDraft.draft,
        field_meta: effectiveDraft.field_meta,
        updated_fields: [],
        rework_ticket: null,
      });
      return {
        state: 'saved',
        message: '规则已保存。',
        rule_id: existing.id,
        draft: savedDraft,
      };
    }

    const newId = deps.createId('rule');
    await insertRule(env.DB, {
      id: newId,
      name,
      match_text: matchText,
      embedding,
      data: compiled,
    });
    const savedDraft = await deps.upsertRuleDraft(env.DB, {
      session_id: effectiveDraft.session_id,
      state: 'saved',
      mode: effectiveDraft.mode,
      rule_id: newId,
      draft: effectiveDraft.draft,
      field_meta: effectiveDraft.field_meta,
      updated_fields: [],
      rework_ticket: null,
    });
    return {
      state: 'saved',
      message: '规则已保存。',
      rule_id: newId,
      draft: savedDraft,
    };
  }

  async function saveRuleFromDraft(
    env: RuleConfigEnv,
    draft: RuleDraft,
    options?: { forceSave?: boolean }
  ): Promise<{
    status: RuleConfigState | 'ready_for_confirm' | 'blocked' | 'cancelled';
    message: string;
    rule_id?: string;
    conflict?: { level: string; match?: { rule_id: string; rule_name: string; score: number } };
  }> {
    const name = String((draft.draft?.name as string) || '').trim();
    const matchText = String((draft.draft?.match_text as string) || '').trim();
    if (!name || !matchText) {
      return { status: 'collecting', message: '规则名称和触发场景都需要先补充完整。' };
    }

    const compiled = await compileRuleDraft(env, draft.draft);
    const examples = deps.normalizeExamples((compiled as Record<string, unknown>).examples, matchText);
    (compiled as Record<string, unknown>).examples = examples;

    const conflict = await detectRuleConflictService(env, matchText, draft.rule_id ?? undefined);
    if (conflict.level === 'red') {
      await deps.upsertRuleDraft(env.DB, {
        session_id: draft.session_id,
        status: 'blocked',
        mode: draft.mode,
        rule_id: draft.rule_id ?? null,
        draft: draft.draft,
      });
      return {
        status: 'blocked',
        message: `检测到与规则“${conflict.match?.rule_name ?? ''}”高度重复，请直接修改旧规则。`,
        conflict,
      };
    }
    if (conflict.level === 'yellow' && !options?.forceSave) {
      await deps.upsertRuleDraft(env.DB, {
        session_id: draft.session_id,
        status: 'blocked',
        mode: draft.mode,
        rule_id: draft.rule_id ?? null,
        draft: draft.draft,
      });
      return {
        status: 'blocked',
        message: `检测到与规则“${conflict.match?.rule_name ?? ''}”相似，如需继续保存请使用强制保存。`,
        conflict,
      };
    }

    const embedding = await generateRuleEmbeddingService(env, matchText, examples);
    if (draft.mode === 'edit' && draft.rule_id) {
      const existing = await getRuleById(env.DB, draft.rule_id);
      if (!existing) {
        return { status: 'blocked', message: '找不到要编辑的规则。' };
      }
      await updateRule(env.DB, existing.id, {
        name,
        match_text: matchText,
        embedding: embedding ?? existing.embedding ?? null,
        data: compiled,
        version: existing.version + 1,
      });
      await deps.clearRuleDraft(env.DB, draft.session_id);
      return { status: 'ready_for_confirm', message: '规则已保存。', rule_id: existing.id };
    }

    const newId = deps.createId('rule');
    await insertRule(env.DB, {
      id: newId,
      name,
      match_text: matchText,
      embedding,
      data: compiled,
    });
    await deps.clearRuleDraft(env.DB, draft.session_id);
    return { status: 'ready_for_confirm', message: '规则已保存。', rule_id: newId };
  }

  async function buildRuleAskerPrompt(
    db: any,
    sessionId: string,
    mode: RuleDraftMode,
    userInput: string
  ): Promise<string> {
    const draft = await deps.getRuleDraft(db, sessionId);
    const draftInfo = draft?.draft
      ? `\n\n当前草稿内容:\n${JSON.stringify(draft.draft, null, 2)}`
      : '\n\n当前草稿为空。';

    return `SESSION_ID: ${sessionId}
MODE: ${mode}
USER_INPUT: ${userInput}${draftInfo}

重要：在回复用户前，必须先调用 get_rule_draft(session_id: "${sessionId}") 获取草稿，
然后调用 update_rule_draft 更新草稿（即使没有变化，也要调用 update_rule_draft with noop: true）。`;
  }

  async function buildRuleAskerProposalPrompt(
    db: any,
    sessionId: string,
    mode: RuleDraftMode,
    userInput: string
  ): Promise<string> {
    const draft = await deps.getRuleDraft(db, sessionId);
    const draftInfo = JSON.stringify(draft?.draft ?? {}, null, 2);
    const fieldMetaInfo = JSON.stringify(draft?.field_meta ?? {}, null, 2);
    const state = draft?.state ?? 'collecting';
    const missingFields = JSON.stringify(draft?.missing_fields ?? []);
    const reworkTicket = JSON.stringify(draft?.rework_ticket ?? null);
    return `SESSION_ID: ${sessionId}
MODE: ${mode}
USER_INPUT: ${userInput}
CURRENT_DRAFT: ${draftInfo}
FIELD_META: ${fieldMetaInfo}
SESSION_STATE: ${state}
MISSING_FIELDS: ${missingFields}
REWORK_TICKET: ${reworkTicket}

重要：
- 你只能调用 get_rule_draft(session_id: "${sessionId}") 和 submit_rule_turn(...)
- 你是提案器，不直接回复用户
- edit 模式优先通过 operations 表达 set / append / remove / clear
- 不能直接写数据库`;
  }

  async function runRuleAskerProposal(
    env: RuleConfigEnv,
    userQuery: string,
    historyMessages?: HistoryMessage[]
  ): Promise<{ proposal: RuleTurnProposal; metadata?: Record<string, unknown> }> {
    const baseProvider = deps.createToolProvider(env);
    const scopedProvider = deps.createScopedToolProvider(
      baseProvider,
      {},
      new Set(['get_rule_draft', 'submit_rule_turn'])
    );
    const openAITools = (await scopedProvider.listTools()).map(deps.toOpenAIToolSchema);
    const skill = `${ruleAskerSkill}

CRITICAL:
- Ignore any older instruction that tells you to call update_rule_draft or to produce a final user-facing reply.
- You are a proposal worker, not a user-facing assistant.
- You MUST call get_rule_draft first.
- You MUST then call submit_rule_turn exactly once.
- If the current edit still needs clarification, leave unresolved fields out of patch, provide one next_question, and fill missing_fields_guess.
- Do NOT generate any final reply for the user.`;

    const messages = [{ role: 'system', content: skill }] as Array<{ role: 'user' | 'assistant' | 'system' | 'tool'; content: string; tool_calls?: any; tool_call_id?: string; name?: string }>;
    if (historyMessages?.length) {
      messages.push(...buildContextFromHistory(historyMessages));
    }
    messages.push({ role: 'user', content: userQuery });

    let didGetDraft = false;
    let proposal: RuleTurnProposal | null = null;

    for (let iteration = 1; iteration <= deps.MAX_TOOL_ITERATIONS; iteration += 1) {
      const response = await callOpenAIWithTools(env, {
        model: env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || deps.DEFAULT_MODEL,
        temperature: 0.2,
        messages,
        tools: openAITools,
      });

      if (response.toolCalls?.length) {
        messages.push({
          role: 'assistant',
          content: response.content || '',
          tool_calls: response.toolCalls,
        });

        for (const toolCall of response.toolCalls) {
          const result = await scopedProvider.callTool(toolCall.tool, toolCall.args);
          if (toolCall.tool === 'get_rule_draft' && result.success) {
            didGetDraft = true;
          }
          if (toolCall.tool === 'submit_rule_turn' && result.success) {
            proposal = result.data as RuleTurnProposal;
          }
          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            name: toolCall.tool,
            content: JSON.stringify(result, null, 2),
          });
        }

        if (didGetDraft && proposal) {
          return {
            proposal,
            metadata: { tool: 'rule_asker', iterations: iteration, proposal_only: true },
          };
        }
        continue;
      }

      messages.push({
        role: 'user',
        content:
          'You must call get_rule_draft first and then submit_rule_turn exactly once. Do not answer the user directly.',
      });
    }

    throw new Error('rule_asker_proposal_failed');
  }

  function hasAppendEditCue(text: string): boolean {
    return /补上|增加|追加|再加|还要补充|另外补充|也覆盖|保留原来的/.test(text);
  }

  function buildRequiredInfoEntryFromUserInput(
    userInput: string
  ): { key: string; ask: string; required: boolean } | null {
    if (!/(必填信息|补充信息|信息项|required_info)/.test(userInput)) return null;
    const match = userInput.match(
      /(?:补上|补充|增加|追加|再加|还要补充|另外补充)(.+?)(?:这个|这一项|该项)?(?:必填信息|补充信息|信息项|required_info)/
    );
    const label = String(match?.[1] ?? '')
      .replace(/[？?，。；;]/g, '')
      .trim();
    if (!label) return null;
    return {
      key: label,
      ask: `请提供${label}`,
      required: true,
    };
  }

  function shouldCoerceAppendEditOperation(
    session: RuleDraft,
    userInput: string,
    operation: RuleTurnOperation
  ): boolean {
    return (
      session.mode === 'edit' &&
      operation.op === 'set' &&
      hasAppendEditCue(userInput) &&
      (operation.field === 'key_points' ||
        operation.field === 'required_info' ||
        operation.field === 'examples' ||
        operation.field === 'do_not_say')
    );
  }

  function isAbstractEditRequest(
    session: RuleDraft,
    userInput: string,
    operations: RuleTurnOperation[]
  ): boolean {
    if (session.mode !== 'edit') return false;
    if (!/适合|口径|严谨|客服|晨会|统一|再细|更细|更像/.test(userInput)) return false;
    if (/语气|触发条件|触发场景|目标|关键点|要点|补充信息|required_info|tone|professional|warm|brief|简洁|温和|专业/.test(userInput)) {
      return false;
    }
    return operations.every((operation) => operation.field === 'tone' || operation.field === 'reply_goal');
  }

  function isConflictingEditRequest(
    session: RuleDraft,
    userInput: string,
    operations: RuleTurnOperation[]
  ): boolean {
    if (session.mode !== 'edit') return false;
    if (!/但不要|但是不要|不过不要|但别|但是别|不过别/.test(userInput)) return false;
    const styleOnlyEdit =
      /语气|口吻|措辞|专业|温和|简洁|礼貌|生硬|严谨|口径|客服|晨会/.test(userInput) &&
      operations.every((operation) => operation.field === 'tone' || operation.field === 'reply_goal');
    if (styleOnlyEdit) return false;
    return true;
  }

  function buildRuleEditClarification(
    session: RuleDraft,
    userInput: string,
    operations: RuleTurnOperation[],
    proposal: RuleTurnProposal
  ): { nextQuestion: string; missingFieldsGuess: string[] } | null {
    if (isConflictingEditRequest(session, userInput, operations)) {
      return {
        nextQuestion:
          '你这次修改里同时出现了互相冲突的要求。请明确一下：这条规则到底是允许这样处理，还是明确禁止这样处理？',
        missingFieldsGuess: ['reply_goal', 'key_points', 'do_not_say'],
      };
    }
    if (isAbstractEditRequest(session, userInput, operations)) {
      return {
        nextQuestion:
          '你希望具体调整哪一项：触发场景、回复目标，还是回复要点？如果只是想改语气，也可以直接说专业、温和或简洁。',
        missingFieldsGuess:
          proposal.missing_fields_guess.length > 0
            ? proposal.missing_fields_guess
            : ['reply_goal', 'key_points', 'tone'],
      };
    }
    return null;
  }

  function buildRuleTurnOperationsForSession(
    session: RuleDraft,
    proposal: RuleTurnProposal,
    userInput: string
  ): RuleTurnOperation[] {
    if (proposal.operations.length > 0) {
      return proposal.operations.map((operation) =>
        shouldCoerceAppendEditOperation(session, userInput, operation)
          ? { ...operation, op: 'append' }
          : operation
      );
    }
    const operationsFromPatch = Object.entries(proposal.patch).map(([field, value]) => {
      const baseOperation = {
        field,
        op: 'set' as const,
        value,
      };
      return shouldCoerceAppendEditOperation(session, userInput, baseOperation)
        ? {
            ...baseOperation,
            op: 'append' as const,
          }
        : baseOperation;
    });
    if (operationsFromPatch.length > 0) {
      return operationsFromPatch;
    }
    const inferredRequiredInfo =
      session.mode === 'edit' && hasAppendEditCue(userInput)
        ? buildRequiredInfoEntryFromUserInput(userInput)
        : null;
    if (inferredRequiredInfo) {
      return [{ field: 'required_info', op: 'append', value: [inferredRequiredInfo] }];
    }
    return [];
  }

  async function applyRuleTurnProposal(
    db: any,
    session: RuleDraft,
    proposal: RuleTurnProposal,
    userInput: string
  ): Promise<{ draft: RuleDraft; next_question?: string; missing_fields_guess: string[] }> {
    const requestedOperations = buildRuleTurnOperationsForSession(session, proposal, userInput);
    const clarification = buildRuleEditClarification(session, userInput, requestedOperations, proposal);
    const effectiveOperations = clarification ? [] : requestedOperations;
    const operationResult = applyRuleTurnOperations(
      session.draft,
      session.field_meta,
      effectiveOperations,
      proposal.field_meta,
      deps.createId
    );
    const updatedFields = operationResult.updated_fields;
    const mergedDraft = operationResult.draft;
    const mergedFieldMeta = operationResult.field_meta;
    const nextQuestion = clarification?.nextQuestion ?? proposal.next_question;
    const missingFieldsGuess =
      clarification?.missingFieldsGuess.length
        ? clarification.missingFieldsGuess
        : proposal.missing_fields_guess;
    const requiresClarification =
      proposal.intent !== 'confirm' &&
      proposal.intent !== 'cancel' &&
      missingFieldsGuess.length > 0 &&
      typeof nextQuestion === 'string' &&
      nextQuestion.trim().length > 0;
    const nextState =
      proposal.intent === 'cancel'
        ? 'cancelled'
        : requiresClarification
          ? 'collecting'
          : computeRuleConfigState(
              mergedDraft,
              mergedFieldMeta,
              session.state === 'rework' ? 'collecting' : session.state
            );
    const reworkTicket = nextState === 'rework' ? session.rework_ticket ?? null : null;
    const nextDraft = await deps.upsertRuleDraft(db, {
      session_id: session.session_id,
      state: nextState,
      mode: session.mode,
      rule_id: session.rule_id ?? null,
      draft: mergedDraft,
      field_meta: mergedFieldMeta,
      updated_fields: updatedFields,
      rework_ticket: reworkTicket,
    });
    return {
      draft: nextDraft,
      next_question: nextQuestion,
      missing_fields_guess: missingFieldsGuess,
    };
  }

  async function tryHandleRuleConfigV2(
    env: RuleConfigEnv,
    sessionId: string,
    content: string,
    historyMessages: HistoryMessage[] = []
  ): Promise<{ content: string; metadata?: Record<string, unknown> } | null> {
    const draft = await deps.getRuleDraft(env.DB, sessionId);
    if (!draft || draft.state === 'cancelled' || draft.state === 'saved') {
      return null;
    }

    if (/^(取消|退出|退出配置|放弃|不保存)$/.test(content.trim())) {
      await deps.clearRuleDraft(env.DB, sessionId);
      const cancelledDraft = await deps.getRuleDraft(env.DB, sessionId);
      return {
        content: renderRuleConfigAssistantMessage({ state: 'cancelled' }),
        metadata: cancelledDraft
          ? buildRuleConfigMetadata(cancelledDraft)
          : { rule_config: { state: 'cancelled', status: 'cancelled' } },
      };
    }

    const forceSave = /^(强制保存|覆盖保存|确认并强制保存)$/.test(content.trim());
    if (
      /^(确认保存|确认|保存)$/.test(content.trim()) &&
      (draft.state === 'awaiting_confirm' || forceSave || draft.state === 'rework' || draft.state === 'blocked_conflict')
    ) {
      const result = await saveRuleConfigSessionV2(env, draft, { forceSave });
      return {
        content: result.message,
        metadata: buildRuleConfigMetadata(result.draft, { conflict: result.conflict }),
      };
    }

    const askerPrompt = await buildRuleAskerProposalPrompt(env.DB, sessionId, draft.mode, content);
    const proposalResult = await runRuleAskerProposal(env, askerPrompt, historyMessages);
    const appliedTurn = await applyRuleTurnProposal(env.DB, draft, proposalResult.proposal, content);
    const nextDraft = appliedTurn.draft;
    return {
      content: renderRuleConfigAssistantMessage({
        state: nextDraft.state,
        updatedFields: nextDraft.updated_fields,
        missingFields: nextDraft.missing_fields,
        nextQuestion: appliedTurn.next_question,
        reworkTicket: nextDraft.rework_ticket,
      }),
      metadata: {
        ...proposalResult.metadata,
        ...buildRuleConfigMetadata(nextDraft, { updated_fields: nextDraft.updated_fields }),
      },
    };
  }

  async function tryHandleRuleConfig(
    env: RuleConfigEnv,
    sessionId: string,
    content: string,
    isStream: boolean,
    historyMessages: HistoryMessage[] = []
  ): Promise<{ content: string | ReadableStream; metadata?: Record<string, unknown> } | null> {
    if (deps.isRuleConfigStateMachineV2Enabled(env)) {
      const result = await tryHandleRuleConfigV2(env, sessionId, content, historyMessages);
      return result ? { ...result, content: result.content } : null;
    }

    const draft = await deps.getRuleDraft(env.DB, sessionId);
    if (!draft || draft.status === 'cancelled') {
      return null;
    }

    if (/^(取消|退出|退出配置|放弃|不保存)$/.test(content.trim())) {
      await deps.clearRuleDraft(env.DB, sessionId);
      return {
        content: '规则配置已取消。',
        metadata: { rule_config: { status: 'cancelled' } },
      };
    }

    const forceSave = /^(强制保存|覆盖保存|确认并强制保存)$/.test(content.trim());
    if (/^(确认保存|确认|保存)$/.test(content.trim()) && (draft.status === 'awaiting_confirm' || forceSave)) {
      const result = await saveRuleFromDraft(env, draft, { forceSave });
      return {
        content: result.message,
        metadata: {
          rule_config: {
            status: result.status,
            rule_id: result.rule_id,
            conflict: result.conflict,
          },
        },
      };
    }

    const askerPrompt = await buildRuleAskerPrompt(env.DB, sessionId, draft.mode, content);
    const output = await deps.runWorkerWithTools(
      env,
      'rule_asker',
      askerPrompt,
      isStream,
      undefined,
      historyMessages
    );
    const latestDraft = await deps.getRuleDraft(env.DB, sessionId);
    return {
      ...output,
      metadata: {
        ...output.metadata,
        rule_config: {
          status: latestDraft?.status,
          mode: latestDraft?.mode,
          rule_id: latestDraft?.rule_id,
          draft: latestDraft ?? undefined,
        },
      },
    };
  }

  async function startSession(
    env: RuleConfigEnv,
    principalId: string,
    payload?: { sessionId?: string; rule_id?: string }
  ): Promise<StartRuleConfigSessionResult> {
    let sessionId = payload?.sessionId;
    if (!sessionId) {
      const session = await deps.createAgentSession(env.DB, '规则配置', principalId);
      sessionId = session.id;
    }

    let draftPayload: Record<string, unknown> = {};
    let mode: RuleDraftMode = 'create';
    let ruleId: string | null = null;

    if (payload?.rule_id) {
      const existing = await getRuleById(env.DB, payload.rule_id);
      if (!existing) {
        throw new Error('rule_not_found');
      }
      ruleId = existing.id;
      mode = 'edit';
      draftPayload = {
        name: existing.name,
        match_text: existing.match_text,
        examples: existing.data?.examples ?? [],
        reply_goal: existing.data?.reply_goal,
        key_points: existing.data?.key_points,
        required_info: existing.data?.required_info,
        template: existing.data?.template,
        safe_defaults: existing.data?.safe_defaults,
        do_not_say: existing.data?.do_not_say,
        tone: existing.data?.tone,
      };
    }

    const initialFieldMeta = buildInitialRuleFieldMeta(draftPayload, deps.createId);
    const initialState = computeRuleConfigState(draftPayload, initialFieldMeta);
    const draft = await deps.upsertRuleDraft(env.DB, {
      session_id: sessionId,
      state: initialState,
      mode,
      rule_id: ruleId,
      draft: draftPayload,
      field_meta: initialFieldMeta,
      updated_fields: [],
      rework_ticket: null,
    });

    return { session_id: sessionId, draft };
  }

  async function confirmSession(
    env: RuleConfigEnv,
    sessionId: string,
    options?: { forceSave?: boolean }
  ): Promise<ConfirmRuleConfigSessionResult> {
    const draft = await deps.getRuleDraft(env.DB, sessionId);
    if (!draft) {
      throw new Error('rule_draft_not_found');
    }
    const result = deps.isRuleConfigStateMachineV2Enabled(env)
      ? await saveRuleConfigSessionV2(env, draft, options)
      : await saveRuleFromDraft(env, draft, options);
    const resultDraft = 'draft' in result ? result.draft : draft;
    const state = normalizeRuleConfigState(('state' in result ? result.state : result.status) ?? draft.state);
    return {
      status: 'state' in result ? result.state : result.status,
      state,
      rule_id: result.rule_id,
      conflict: result.conflict,
      message: result.message,
      draft: resultDraft,
      missing_fields: resultDraft?.missing_fields ?? [],
      updated_fields: resultDraft?.updated_fields ?? [],
      rework_ticket: resultDraft?.rework_ticket ?? null,
    };
  }

  async function cancelSession(env: RuleConfigEnv, sessionId: string): Promise<{ success: true }> {
    await deps.clearRuleDraft(env.DB, sessionId);
    return { success: true };
  }

  return {
    compileRuleConfigSession,
    confirmSession,
    cancelSession,
    executeRuleDraftTest,
    saveRuleFromDraft,
    saveRuleConfigSessionV2,
    startSession,
    tryHandleRuleConfig,
  };
}
