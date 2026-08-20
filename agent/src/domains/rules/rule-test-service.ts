import { callOpenAIEmbedding } from '../../infra/llm/openai-client';
import type { ToolProvider, ToolResult } from '../../tools/provider';
import { buildWorkerPrompt } from '../chat/worker-runner';
import type { D1Database } from '../scenarios/repository';
import { computeRuleMatchScore, generateRuleEmbedding } from './match-service';
import { getRuleById, listRules, type RuleRecord } from './repository';
import type { RuleJson } from './tool-adapter';

type WorkerToolName = 'rule_reply';

interface RuleTestEnvLike {
  DB: D1Database;
  OPENAI_MODEL?: string;
  OPENAI_WORKER_MODEL?: string;
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_EMBEDDING_MODEL?: string;
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

export interface RuleTestDeps {
  createToolProvider(env: RuleTestEnvLike): ToolProvider;
  createScopedToolProvider(
    baseProvider: ToolProvider,
    overrides: Record<string, (args: Record<string, unknown>) => Promise<ToolResult> | ToolResult>,
    allowList?: Set<string>
  ): ToolProvider;
  runWorkerWithTools(
    env: RuleTestEnvLike,
    tool: WorkerToolName,
    prompt: string,
    stream: boolean,
    toolProvider: ToolProvider
  ): Promise<{ content?: string }>;
  ruleMatchThreshold: number;
}

export function normalizeExamples(value: unknown, matchText: string): string[] {
  const raw = Array.isArray(value) ? (value.filter((item) => typeof item === 'string') as string[]) : [];
  const examples = raw.map((item) => item.trim()).filter(Boolean);
  const fallbackBase = matchText || 'related question';
  const fallbackTemplates = [
    `How should ${fallbackBase} be handled?`,
    `What rule applies to ${fallbackBase}?`,
    `What information is needed for ${fallbackBase}?`,
    `What is the process for ${fallbackBase}?`,
    `Please help check how to handle ${fallbackBase}.`,
  ];
  while (examples.length < 5) {
    examples.push(fallbackTemplates[examples.length % fallbackTemplates.length]);
  }
  return examples.slice(0, 5);
}

function buildTopMatches(
  scoredRules: Array<{ rule: RuleRecord; score: number }>,
  ruleId: string,
  minScore: number,
  topK: number
): RuleMatchItem[] {
  return scoredRules
    .filter((item) => item.score >= minScore && item.rule.id !== ruleId)
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
}

export async function executeRuleTest(
  env: RuleTestEnvLike,
  ruleId: string,
  deps: RuleTestDeps,
  payload?: {
    queries?: string[];
    top_k?: number;
    min_score?: number;
    preview_reply?: boolean;
  }
): Promise<ToolResult> {
  const rule = await getRuleById(env.DB, ruleId);
  if (!rule) {
    return { success: false, error: 'rule_not_found' };
  }

  const matchText = rule.match_text.trim();
  if (!matchText) {
    return { success: false, error: 'match_text_required' };
  }

  const examples = normalizeExamples(rule.data?.examples, matchText);
  const suggestedQueries = normalizeExamples(rule.data?.examples, matchText);
  const normalizedQueries = (Array.isArray(payload?.queries) ? payload.queries : [])
    .map((item) => String(item ?? '').trim())
    .filter(Boolean)
    .slice(0, 10);
  const queries = normalizedQueries.length ? normalizedQueries : suggestedQueries;

  let ruleEmbedding = rule.embedding;
  if (!ruleEmbedding) {
    ruleEmbedding = await generateRuleEmbedding(env, matchText, examples);
  }

  const allRules = await listRules(env.DB, { includeDisabled: false, limit: 500 });
  const otherRules = allRules.filter((item) => item.id !== ruleId);
  const topK = Math.min(Math.max(Number(payload?.top_k ?? 5), 1), 20);
  const minScore = Number(payload?.min_score ?? 0.3);
  const previewReply = payload?.preview_reply !== false;

  const baseProvider = deps.createToolProvider(env);
  const ruleJson: RuleJson = {
    id: rule.id,
    name: rule.name,
    match_text: matchText,
    examples,
    ...(rule.data || {}),
  };
  const scopedProvider = deps.createScopedToolProvider(
    baseProvider,
    {
      get_rule: async (args) => {
        const requestedRuleId = String(args?.rule_id ?? '').trim();
        if (!requestedRuleId || requestedRuleId !== ruleId) {
          return { success: false, error: 'rule_id_mismatch' };
        }
        return { success: true, data: ruleJson };
      },
    },
    new Set(['get_rule'])
  );

  const results: RuleDraftTestResultItem[] = [];
  for (const query of queries) {
    try {
      const queryEmbedding = await callOpenAIEmbedding(env, query);
      const scoredOtherRules = otherRules.map((item) => ({
        rule: item,
        score: computeRuleMatchScore(queryEmbedding, item.embedding),
      }));
      const ruleScore = ruleEmbedding ? computeRuleMatchScore(queryEmbedding, ruleEmbedding) : undefined;
      const allScoredRules = [
        ...scoredOtherRules,
        ...(ruleScore !== undefined ? [{ rule, score: ruleScore }] : []),
      ];

      const maxOtherScore = scoredOtherRules.reduce((max, item) => Math.max(max, item.score), 0);
      const ruleRank =
        ruleScore !== undefined ? 1 + allScoredRules.filter((item) => item.score > ruleScore).length : undefined;
      const wouldTrigger =
        ruleScore !== undefined &&
        ruleScore >= deps.ruleMatchThreshold &&
        (scoredOtherRules.length === 0 || ruleScore >= maxOtherScore);

      let replyPreview: string | undefined;
      if (previewReply) {
        const prompt = buildWorkerPrompt({
          tool: 'rule_reply',
          args: { rule_id: ruleId, user_query: query },
        });
        const replyResult = await deps.runWorkerWithTools(env, 'rule_reply', prompt, false, scopedProvider);
        replyPreview = typeof replyResult.content === 'string' ? replyResult.content : undefined;
      }

      results.push({
        query,
        draft_score: ruleScore,
        draft_rank: ruleRank,
        total_rules: allRules.length,
        would_trigger: wouldTrigger,
        top_matches: buildTopMatches(allScoredRules, ruleId, minScore, topK),
        reply_preview: replyPreview,
      });
    } catch (error) {
      results.push({
        query,
        top_matches: [],
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  const response: RuleDraftTestResponse = {
    session_id: '',
    rule_id: ruleId,
    draft_name: rule.name,
    match_text: matchText,
    suggested_queries: suggestedQueries,
    results,
  };

  return { success: true, data: response };
}
