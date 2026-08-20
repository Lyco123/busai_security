import { jsonResponse, readJson } from '../../infra/http/response';
import { isStringArray } from '../../shared/guards';
import type { D1Database } from './repository';
import {
  deleteWorkScenario,
  getWorkScenario,
  insertWorkScenario,
  listWorkScenarios,
  updateWorkScenario,
} from './repository';
import { tryGenerateScenarioEmbedding } from './match-service';

interface ScenariosHandlersDeps {
  request: Request;
  relativePath: string;
  url: URL;
  env: {
    DB: D1Database;
    OPENAI_API_KEY?: string;
    OPENAI_BASE_URL?: string;
    OPENAI_EMBEDDING_MODEL?: string;
  };
  createId: (prefix: string) => string;
}

export async function handleScenariosApiRequest(deps: ScenariosHandlersDeps): Promise<Response | null> {
  const { request, relativePath, url, env, createId } = deps;

if (relativePath === '/scenarios' && request.method === 'GET') {
    const includeDisabled = url.searchParams.get('include_disabled') === 'true';
    const scenarios = await listWorkScenarios(env.DB, { includeDisabled });
    const data = scenarios.map((scenario) => ({
      ...scenario,
      embedding: undefined,
    }));
    return jsonResponse({ data });
  }

  if (relativePath === '/scenarios' && request.method === 'POST') {
    const payload = await readJson<{
      id?: string;
      name?: string;
      description?: string;
      keywords?: string[];
      enabled?: boolean;
    }>(request);

    if (!payload?.name || !payload.description) {
      return jsonResponse({ error: '缺少 name/description 参数' }, { status: 400 });
    }
    if (payload.keywords && !isStringArray(payload.keywords)) {
      return jsonResponse({ error: 'keywords 蹇呴』涓哄瓧绗︿覆鏁扮粍' }, { status: 400 });
    }

    const scenarioId = payload.id || createId('scenario');
    const embedding = await tryGenerateScenarioEmbedding(env, {
      name: payload.name,
      description: payload.description,
      keywords: payload.keywords,
    });

    const scenario = await insertWorkScenario(env.DB, {
      id: scenarioId,
      name: payload.name,
      description: payload.description,
      keywords: payload.keywords,
      embedding,
      enabled: payload.enabled,
    });

    return jsonResponse({
      data: { ...scenario, embedding: undefined },
      embedding_status: embedding ? 'ok' : 'skipped',
    });
  }

  if (relativePath.startsWith('/scenarios/') && request.method === 'GET') {
    const id = decodeURIComponent(relativePath.replace('/scenarios/', ''));
    const scenario = await getWorkScenario(env.DB, id);
    if (!scenario) {
      return jsonResponse({ error: '找不到板満鏅? '}, { status: 404 });
    }
    return jsonResponse({ data: { ...scenario, embedding: undefined } });
  }

  if (relativePath.startsWith('/scenarios/') && request.method === 'PUT') {
    const id = decodeURIComponent(relativePath.replace('/scenarios/', ''));
    const payload = await readJson<{
      name?: string;
      description?: string;
      keywords?: string[];
      enabled?: boolean;
      refresh_embedding?: boolean;
    }>(request);

    if (!payload) {
      return jsonResponse({ error: '缺少更新参数' }, { status: 400 });
    }
    if (payload.keywords && !isStringArray(payload.keywords)) {
      return jsonResponse({ error: 'keywords 蹇呴』涓哄瓧绗︿覆鏁扮粍' }, { status: 400 });
    }

    const existing = await getWorkScenario(env.DB, id);
    if (!existing) {
      return jsonResponse({ error: '找不到板満鏅? '}, { status: 404 });
    }

    const updates: Partial<{
      name: string;
      description: string;
      keywords: string[];
      enabled: boolean;
      embedding: number[] | null;
    }> = {};

    if (payload.name !== undefined) updates.name = payload.name;
    if (payload.description !== undefined) updates.description = payload.description;
    if (payload.keywords !== undefined) updates.keywords = payload.keywords;
    if (payload.enabled !== undefined) updates.enabled = payload.enabled;

    let embeddingStatus: 'ok' | 'skipped' = 'skipped';
    const shouldEmbed =
      payload.refresh_embedding ||
      payload.name !== undefined ||
      payload.description !== undefined ||
      payload.keywords !== undefined;

    if (shouldEmbed) {
      const embedding = await tryGenerateScenarioEmbedding(env, {
        name: payload.name ?? existing.name,
        description: payload.description ?? existing.description,
        keywords: payload.keywords ?? existing.keywords,
      });
      if (embedding) {
        updates.embedding = embedding;
        embeddingStatus = 'ok';
      }
    }

    const scenario = await updateWorkScenario(env.DB, id, updates);
    if (!scenario) {
      return jsonResponse({ error: '找不到板満鏅? '}, { status: 404 });
    }

    return jsonResponse({
      data: { ...scenario, embedding: undefined },
      embedding_status: embeddingStatus,
    });
  }

  if (relativePath.startsWith('/scenarios/') && request.method === 'DELETE') {
    const id = decodeURIComponent(relativePath.replace('/scenarios/', ''));
    await deleteWorkScenario(env.DB, id);
    return jsonResponse({ success: true });
  }

  return null;
}
