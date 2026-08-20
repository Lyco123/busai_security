import { config } from '../config';
import { callLlmJson } from './llm';

export interface QueryRewriteResult {
  intent: string;
  original_query: string;
  dense_query: string;
  lexical_queries: string[];
  must_terms: string[];
  negative_terms: string[];
}

function uniqueStrings(values: string[], limit: number): string[] {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    items.push(trimmed);
    if (items.length >= limit) break;
  }
  return items;
}

export function splitKeywordQuery(value: string): string[] {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return [];
  return uniqueStrings(
    normalized
      .split(/[\s,，。；;、/]+/g)
      .map((word) => word.trim())
      .filter((word) => word.length >= 2),
    8
  );
}

export function buildRewriteFallback(query: string): QueryRewriteResult {
  const original = query.trim();
  return {
    intent: 'regulation_lookup',
    original_query: original,
    dense_query: original,
    lexical_queries: splitKeywordQuery(original).slice(0, 3),
    must_terms: [],
    negative_terms: [],
  };
}

function normalizeRewriteResult(query: string, payload: Partial<QueryRewriteResult> | null | undefined): QueryRewriteResult {
  const fallback = buildRewriteFallback(query);
  if (!payload) return fallback;
  return {
    intent: typeof payload.intent === 'string' && payload.intent.trim() ? payload.intent.trim() : fallback.intent,
    original_query: fallback.original_query,
    dense_query:
      typeof payload.dense_query === 'string' && payload.dense_query.trim()
        ? payload.dense_query.trim()
        : fallback.dense_query,
    lexical_queries: uniqueStrings(
      Array.isArray(payload.lexical_queries)
        ? payload.lexical_queries.map((item) => String(item))
        : fallback.lexical_queries,
      3
    ),
    must_terms: uniqueStrings(
      Array.isArray(payload.must_terms) ? payload.must_terms.map((item) => String(item)) : [],
      6
    ),
    negative_terms: uniqueStrings(
      Array.isArray(payload.negative_terms) ? payload.negative_terms.map((item) => String(item)) : [],
      6
    ),
  };
}

export async function rewriteRetrieveQuery(query: string): Promise<QueryRewriteResult> {
  const fallback = buildRewriteFallback(query);
  if (!config.retrieveRewriteEnabled) {
    return fallback;
  }

  const payload = await callLlmJson<Partial<QueryRewriteResult> | null>(
    config.queryRewriteModel,
    [
      {
        role: 'system',
        content: [
          '你是知识库检索改写器，只负责把用户问题改写成更适合制度/条款检索的查询，不要回答问题。',
          '输出必须是 JSON 对象，字段固定为 intent、dense_query、lexical_queries、must_terms、negative_terms。',
          'dense_query 只保留 1 条，适合语义检索。',
          'lexical_queries 最多 3 条，适合关键词召回，可提取制度名、主题词、动作词、对象词。',
          'must_terms 只保留必须命中的核心词，negative_terms 只保留明确应排斥的词。',
          '禁止编造不存在的制度名称；如果无法确定，就只抽取问题中的真实词语。',
        ].join('\n'),
      },
      {
        role: 'user',
        content: `用户问题：${query.trim()}`,
      },
    ],
    fallback
  );

  return normalizeRewriteResult(query, payload);
}
