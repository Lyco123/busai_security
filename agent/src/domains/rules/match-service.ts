import { callOpenAIEmbedding } from '../../infra/llm/openai-client';
import { cosineSimilarity } from '../../shared/vector';
import type { D1Database } from '../scenarios/repository';
import { listRules, type RuleEmbeddingPayload, type RuleRecord } from './repository';

interface MatchEnvLike {
  DB: D1Database;
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_EMBEDDING_MODEL?: string;
}

interface ToolResultLike {
  success: boolean;
  data?: unknown;
  error?: string;
}

export interface MatchRulesOptions {
  queryEmbedding?: number[];
  onQueryEmbedding?: (embedding: number[]) => void;
}

export async function generateRuleEmbedding(
  env: MatchEnvLike,
  matchText: string,
  examples?: string[]
): Promise<RuleEmbeddingPayload | null> {
  try {
    const anchor = await callOpenAIEmbedding(env, matchText);
    const exampleEmbeddings: number[][] = [];
    if (examples?.length) {
      for (const example of examples) {
        if (!example) continue;
        exampleEmbeddings.push(await callOpenAIEmbedding(env, example));
      }
    }
    return {
      anchor,
      examples: exampleEmbeddings.length ? exampleEmbeddings : undefined,
    };
  } catch (error) {
    console.warn('Rule embedding failed:', error);
    return null;
  }
}

export function computeRuleMatchScore(
  queryEmbedding: number[],
  embedding?: RuleEmbeddingPayload | null
): number {
  if (!embedding) return 0;
  const anchorScore = embedding.anchor ? cosineSimilarity(queryEmbedding, embedding.anchor) : 0;
  const exampleScore = Array.isArray(embedding.examples)
    ? Math.max(
        0,
        ...embedding.examples.map((example) =>
          Array.isArray(example) ? cosineSimilarity(queryEmbedding, example) : 0
        )
      )
    : 0;
  return Math.max(anchorScore, exampleScore);
}

function toRuleMatch(rule: RuleRecord, score: number) {
  return {
    rule_id: rule.id,
    rule_name: rule.name,
    score,
    metadata: {
      match_text: rule.match_text,
      tone: (rule.data?.tone as string | undefined) ?? undefined,
    },
  };
}

export async function executeMatchRules(
  env: MatchEnvLike,
  args: { query: string; top_k?: number; min_score?: number },
  options: MatchRulesOptions = {}
): Promise<ToolResultLike> {
  const query = String(args.query || '').trim();
  if (!query) {
    return { success: false, error: 'query is required' };
  }

  const topK = Math.min(Math.max(Number(args.top_k ?? 5), 1), 20);
  const minScore = Number(args.min_score ?? 0.3);
  const rules = await listRules(env.DB, { includeDisabled: false, limit: 500 });
  if (!rules.length) {
    return {
      success: true,
      data: { query, matches: [], total_matched: 0, top_k: topK },
    };
  }

  const queryEmbedding =
    Array.isArray(options.queryEmbedding) && options.queryEmbedding.length
      ? options.queryEmbedding
      : await callOpenAIEmbedding(env, query);
  options.onQueryEmbedding?.(queryEmbedding);
  const matches = rules
    .map((rule) => toRuleMatch(rule, computeRuleMatchScore(queryEmbedding, rule.embedding)))
    .filter((item) => item.score >= minScore)
    .sort((left, right) => right.score - left.score)
    .slice(0, topK);

  return {
    success: true,
    data: {
      query,
      matches,
      total_matched: matches.length,
      top_k: topK,
    },
  };
}

export async function detectRuleConflict(
  env: MatchEnvLike,
  matchText: string,
  excludeRuleId?: string | null
): Promise<{
  level: 'green' | 'yellow' | 'red';
  match?: { rule_id: string; rule_name: string; score: number };
}> {
  const rules = await listRules(env.DB, { includeDisabled: true, limit: 500 });
  const filtered = rules.filter((rule) => rule.id !== excludeRuleId);
  if (!filtered.length) {
    return { level: 'green' };
  }

  const queryEmbedding = await callOpenAIEmbedding(env, matchText);
  let best: { rule_id: string; rule_name: string; score: number } | null = null;
  for (const rule of filtered) {
    const score = computeRuleMatchScore(queryEmbedding, rule.embedding);
    if (!best || score > best.score) {
      best = { rule_id: rule.id, rule_name: rule.name, score };
    }
  }

  if (!best) return { level: 'green' };
  if (best.score >= 0.92) return { level: 'red', match: best };
  if (best.score >= 0.8) return { level: 'yellow', match: best };
  return { level: 'green', match: best };
}
