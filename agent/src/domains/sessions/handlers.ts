import { jsonResponse, readJson } from '../../infra/http/response';

interface SessionsHandlersDeps {
  request: Request;
  relativePath: string;
  env: { DB: unknown };
  auth: { principal_id: string };
  defaultSessionTitle: string;
  listAgentSessions: any;
  createAgentSession: any;
  getAgentSession: any;
  getAgentSessionMeta: any;
  sanitizeGeneratedTitle: any;
  updateSessionTitle: any;
  deleteAgentSession: any;
}

export async function handleSessionsApiRequest(deps: SessionsHandlersDeps): Promise<Response | null> {
  const {
    request,
    relativePath,
    env,
    auth,
    defaultSessionTitle,
    listAgentSessions,
    createAgentSession,
    getAgentSession,
    getAgentSessionMeta,
    sanitizeGeneratedTitle,
    updateSessionTitle,
    deleteAgentSession,
  } = deps;

  if (relativePath === '/sessions' && request.method === 'GET') {
    const url = new URL(request.url);
    const includeRuleConfig = url.searchParams.get('include_rule_config') === 'true';
    const sessions = await listAgentSessions(env.DB, auth, { includeRuleConfig });
    return jsonResponse(sessions);
  }

  if (relativePath === '/sessions' && request.method === 'POST') {
    const payload = await readJson<{ title?: string }>(request);
    const title = payload?.title || defaultSessionTitle;
    const session = await createAgentSession(env.DB, title, auth.principal_id);
    return jsonResponse(session);
  }

  if (relativePath.startsWith('/sessions/') && request.method === 'GET') {
    const sessionId = decodeURIComponent(relativePath.replace('/sessions/', ''));
    const session = await getAgentSession(env.DB, sessionId, auth);
    if (!session) {
      return jsonResponse({ error: '找不到颁細璇? '}, { status: 404 });
    }
    return jsonResponse(session);
  }

  if (relativePath.startsWith('/sessions/') && request.method === 'PATCH') {
    const sessionId = decodeURIComponent(relativePath.replace('/sessions/', ''));
    const payload = await readJson<{ title?: string }>(request);
    if (!payload?.title) {
      return jsonResponse({ error: '缺少 title 参数' }, { status: 400 });
    }
    const session = await getAgentSessionMeta(env.DB, sessionId, auth);
    if (!session) {
      return jsonResponse({ error: '找不到颁細璇? '}, { status: 404 });
    }
    const nextTitle = sanitizeGeneratedTitle(payload.title);
    if (!nextTitle) {
      return jsonResponse({ error: '鏍囬涓嶅彲涓虹┖' }, { status: 400 });
    }
    await updateSessionTitle(env.DB, sessionId, nextTitle);
    return jsonResponse({ success: true, title: nextTitle });
  }

  if (relativePath.startsWith('/sessions/') && request.method === 'DELETE') {
    const sessionId = decodeURIComponent(relativePath.replace('/sessions/', ''));
    const session = await getAgentSessionMeta(env.DB, sessionId, auth);
    if (!session) {
      return jsonResponse({ error: 'session not found' }, { status: 404 });
    }
    await deleteAgentSession(env.DB, sessionId);
    return jsonResponse({ success: true });
  }

  return null;
}
