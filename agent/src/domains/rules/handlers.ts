import { jsonResponse, readJson } from '../../infra/http/response';
import type { D1Database } from '../scenarios/repository';
import {
  deleteRule,
  getRuleById,
  insertRule,
  listRules,
  updateRule,
  type RuleEmbeddingPayload,
} from './repository';
import { executeMatchRules, generateRuleEmbedding } from './match-service';

interface RulesHandlersDeps {
  request: Request;
  relativePath: string;
  url: URL;
  env: {
    DB: D1Database;
    OPENAI_API_KEY?: string;
    OPENAI_BASE_URL?: string;
    OPENAI_EMBEDDING_MODEL?: string;
  };
  normalizeExamples: (value: unknown, matchText: string) => string[];
  createId: (prefix: string) => string;
  executeRuleTest: (
    env: any,
    ruleId: string,
    payload?: {
      queries?: string[];
      top_k?: number;
      min_score?: number;
      preview_reply?: boolean;
    }
  ) => Promise<{ success: boolean; data?: unknown; error?: string }>;
}

export async function handleRulesApiRequest(deps: RulesHandlersDeps): Promise<Response | null> {
  const { request, relativePath, url, env, normalizeExamples, createId, executeRuleTest } = deps;

  if (relativePath === '/rules' && request.method === 'GET') {
    const includeDisabled = url.searchParams.get('include_disabled') === 'true';
    const rules = await listRules(env.DB, { includeDisabled });
    const data = rules.map((rule) => ({
      ...rule,
      embedding: undefined,
    }));
    return jsonResponse({ data });
  }

  if (relativePath === '/rules/match' && request.method === 'POST') {
    const payload = await readJson<{ query?: string; top_k?: number; min_score?: number }>(request);
    const result = await executeMatchRules(env, {
      query: String(payload?.query ?? ''),
      top_k: payload?.top_k,
      min_score: payload?.min_score,
    });
    return jsonResponse(result);
  }

  if (relativePath === '/rules' && request.method === 'POST') {
    const payload = await readJson<{
      id?: string;
      name?: string;
      match_text?: string;
      enabled?: boolean;
      priority?: number;
      version?: number;
      data?: Record<string, unknown>;
    }>(request);

    if (!payload?.name || !payload.match_text || !payload.data) {
      return jsonResponse({ error: 'missing name/match_text/data' }, { status: 400 });
    }

    const examples = normalizeExamples(payload.data.examples, payload.match_text);
    payload.data.examples = examples;

    const embedding = await generateRuleEmbedding(env, payload.match_text, examples);
    const ruleId = payload.id || createId('rule');
    const rule = await insertRule(env.DB, {
      id: ruleId,
      name: payload.name,
      match_text: payload.match_text,
      enabled: payload.enabled,
      priority: payload.priority,
      version: payload.version,
      embedding,
      data: payload.data,
    });

    return jsonResponse({
      data: { ...rule, embedding: undefined },
      embedding_status: embedding ? 'ok' : 'skipped',
    });
  }

  if (relativePath.startsWith('/rules/') && request.method === 'GET') {
    const id = decodeURIComponent(relativePath.replace('/rules/', ''));
    const rule = await getRuleById(env.DB, id);
    if (!rule) {
      return jsonResponse({ error: 'rule_not_found' }, { status: 404 });
    }
    return jsonResponse({ data: { ...rule, embedding: undefined } });
  }

  if (relativePath.startsWith('/rules/') && request.method === 'PUT') {
    const id = decodeURIComponent(relativePath.replace('/rules/', ''));
    const payload = await readJson<{
      name?: string;
      match_text?: string;
      enabled?: boolean;
      priority?: number;
      version?: number;
      data?: Record<string, unknown>;
      refresh_embedding?: boolean;
    }>(request);

    const existing = await getRuleById(env.DB, id);
    if (!existing) {
      return jsonResponse({ error: 'rule_not_found' }, { status: 404 });
    }

    let embedding: RuleEmbeddingPayload | null | undefined;
    let embeddingStatus: 'ok' | 'skipped' = 'skipped';
    const shouldEmbed = payload?.refresh_embedding || payload?.match_text || payload?.data;
    let nextData = payload?.data ?? existing.data;
    if (nextData && payload?.match_text) {
      const nextExamples = normalizeExamples(nextData.examples, payload.match_text);
      nextData = { ...nextData, examples: nextExamples };
    }
    if (shouldEmbed) {
      const matchText = payload?.match_text ?? existing.match_text;
      const examples = normalizeExamples(nextData?.examples, matchText);
      embedding = await generateRuleEmbedding(env, matchText, examples);
      embeddingStatus = embedding ? 'ok' : 'skipped';
      nextData = { ...nextData, examples };
    }

    const rule = await updateRule(env.DB, id, {
      name: payload?.name,
      match_text: payload?.match_text,
      enabled: payload?.enabled,
      priority: payload?.priority,
      version: payload?.version,
      embedding: embedding ?? undefined,
      data: nextData,
    });

    if (!rule) {
      return jsonResponse({ error: 'rule_not_found' }, { status: 404 });
    }

    return jsonResponse({
      data: { ...rule, embedding: undefined },
      embedding_status: embeddingStatus,
    });
  }

  if (relativePath.startsWith('/rules/') && relativePath.endsWith('/test') && request.method === 'POST') {
    const ruleId = decodeURIComponent(relativePath.replace('/rules/', '').replace('/test', ''));
    const payload = await readJson<{
      queries?: string[];
      top_k?: number;
      min_score?: number;
      preview_reply?: boolean;
    }>(request);
    const result = await executeRuleTest(env, ruleId, payload ?? undefined);
    return jsonResponse(result);
  }

  if (
    relativePath.startsWith('/rules/') &&
    relativePath.endsWith('/refresh_embedding') &&
    request.method === 'POST'
  ) {
    const id = decodeURIComponent(relativePath.replace('/rules/', '').replace('/refresh_embedding', ''));
    const existing = await getRuleById(env.DB, id);
    if (!existing) {
      return jsonResponse({ error: 'rule_not_found' }, { status: 404 });
    }
    const examples = normalizeExamples(existing.data?.examples, existing.match_text);
    const embedding = await generateRuleEmbedding(env, existing.match_text, examples);
    await updateRule(env.DB, id, {
      embedding: embedding ?? existing.embedding ?? null,
      data: { ...existing.data, examples },
    });
    return jsonResponse({ embedding_status: embedding ? 'ok' : 'skipped' });
  }

  if (relativePath.startsWith('/rules/') && request.method === 'DELETE') {
    const id = decodeURIComponent(relativePath.replace('/rules/', ''));
    await deleteRule(env.DB, id);
    return jsonResponse({ success: true });
  }

  return null;
}
