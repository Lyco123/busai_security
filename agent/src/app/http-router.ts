import { API_PREFIX } from '../core/constants';
import {
  AUTH_COOKIE_MAX_AGE_SECONDS,
  COOKIE_AUTH_TOKEN,
  buildAuthPayload,
  deleteAuthSession,
  getAuthUserByUsername,
  resolveAuthContext,
  upsertAuthSession,
  type RequestAuthContext,
  type TokenVerifier,
} from '../infra/auth/session-store';
import {
  appendSetCookies,
  buildAnonPrincipalId,
  buildUserPrincipalId,
  serializeCookie,
} from '../infra/auth/cookies';
import { handleChatApiRequest } from '../domains/chat/handlers';
import { getAbTestStats } from '../domains/ab-test/service';
import { handleResearchApiRequest } from '../domains/research/handlers';
import { handleRuleConfigApiRequest } from '../domains/rules/rule-config/http-handlers';
import { handleRulesApiRequest } from '../domains/rules/handlers';
import { handleScenariosApiRequest } from '../domains/scenarios/handlers';
import { handleAliasesApiRequest } from '../domains/aliases/handlers';
import { handleSessionsApiRequest } from '../domains/sessions/handlers';
import { handleKbProxyRequest } from '../infra/kb-proxy';
import { withCors } from '../infra/http/cors';
import { jsonResponse, readJson } from '../infra/http/response';

type D1DatabaseLike = unknown;

type EnvLike = {
  DB: D1DatabaseLike;
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_LOCAL_BASE_URL?: string;
  OPENAI_LOCAL_MODEL?: string;
  OPENAI_LOCAL_REPORT_BASE_URL?: string;
  OPENAI_LOCAL_REPORT_MODEL?: string;
  OPENAI_REPORT_URL?: string;
  OPENAI_REPORT_BASE_URL?: string;
  OPENAI_REPORT_MODEL?: string;
  OPENAI_EMBEDDING_MODEL?: string;
  EMBEDDING_MODEL?: string;
  CORS_ALLOWED_ORIGINS?: string;
  MCP_ACCESS_TOKEN?: string;
};

type WorkerExecutionContext = {
  waitUntil: (promise: Promise<unknown>) => void;
};

export interface HttpRouterDeps {
  createId: (prefix: string) => string;
  defaultSessionTitle: string;
  ruleConfigService: any;
  tokenVerifier?: TokenVerifier;
  normalizeExamples: (examples: unknown, fallback: string) => string[];
  executeRuleTest: (env: any, ruleId: string, payload?: any) => Promise<any>;
  parseResearchFilters: (...args: any[]) => any;
  resolveResearchFilterIssueTypes: (...args: any[]) => any;
  parsePagination: (...args: any[]) => any;
  listIssueTypes: (...args: any[]) => any;
  ensureIssueTypeByName: (...args: any[]) => any;
  updateIssueTypeRecord: (...args: any[]) => any;
  mergeIssueTypes: (...args: any[]) => any;
  getResearchOptions: (...args: any[]) => any;
  getResearchOverview: (...args: any[]) => any;
  listResearchEvals: (...args: any[]) => any;
  createEvalRecord: (...args: any[]) => any;
  getEvalRecordById: (...args: any[]) => any;
  normalizeIssueSeverity: (...args: any[]) => any;
  normalizeIssuePriority: (...args: any[]) => any;
  normalizeIssueStatus: (...args: any[]) => any;
  updateEvalRecord: (...args: any[]) => any;
  listResearchIssues: (...args: any[]) => any;
  createIssueRecord: (...args: any[]) => any;
  getIssueRecordById: (...args: any[]) => any;
  listIssueEventsByIssueId: (...args: any[]) => any;
  updateIssueRecord: (...args: any[]) => any;
  listAgentSessions: (...args: any[]) => any;
  createAgentSession: (...args: any[]) => any;
  getAgentSession: (...args: any[]) => any;
  getAgentSessionMeta: (...args: any[]) => any;
  sanitizeGeneratedTitle: (...args: any[]) => any;
  updateSessionTitle: (...args: any[]) => any;
  deleteAgentSession: (...args: any[]) => any;
  handleChatStream: (...args: any[]) => Promise<Response>;
  handleDirectStreamProbe: (...args: any[]) => Promise<Response>;
  handlePipelineStreamProbe: (...args: any[]) => Promise<Response>;
  handleChat: (...args: any[]) => any;
  handleReportSummary: (...args: any[]) => any;
}

export function createHttpRequestHandler(deps: HttpRouterDeps) {
  async function handleRequest(
    request: Request,
    env: EnvLike,
    ctx?: WorkerExecutionContext
  ): Promise<Response> {
    try {
      return await handleRequestUnchecked(request, env, ctx);
    } catch (error) {
      console.error('Server error:', error);
      return withCors(jsonResponse({ error: '服务器内部错误' }, { status: 500 }), request, env);
    }
  }

  async function handleRequestUnchecked(
    request: Request,
    env: EnvLike,
    ctx?: WorkerExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url);
    const pathname = url.pathname.replace(/\/+$/, '');

    if (request.method === 'OPTIONS') {
      return withCors(new Response(null, { status: 204 }), request, env);
    }

    if (pathname.startsWith(API_PREFIX)) {
      const relativePath = pathname.slice(API_PREFIX.length) || '/';
      const auth = await resolveAuthContext(request, env.DB as any, deps.tokenVerifier);
      const response = await handleAPIRequest(request, env, relativePath, auth, ctx);
      return withCors(appendSetCookies(response, auth.pending_set_cookies), request, env);
    }

    return withCors(new Response('Not Found', { status: 404 }), request, env);
  }

  async function handleAPIRequest(
    request: Request,
    env: EnvLike,
    relativePath: string,
    auth: RequestAuthContext,
    ctx?: WorkerExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url);

    if (relativePath === '/health' && request.method === 'GET') {
      return jsonResponse({ status: 'ok', timestamp: new Date().toISOString() });
    }

    if (relativePath === '/auth/me' && request.method === 'GET') {
      return jsonResponse({ data: buildAuthPayload(auth) });
    }

    if (relativePath === '/auth/login' && request.method === 'POST') {
      const payload = await readJson<{ username?: string; password?: string }>(request);
      const username = payload?.username?.trim() || '';
      const password = payload?.password || '';
      if (!username || !password) {
        return jsonResponse({ error: 'missing username or password' }, { status: 400 });
      }

      const user = await getAuthUserByUsername(env.DB as any, username);
      if (!user || !user.enabled || user.password !== password) {
        return jsonResponse({ error: 'invalid username or password' }, { status: 401 });
      }

      if (auth.auth_token) {
        await deleteAuthSession(env.DB as any, auth.auth_token);
      }
      const authSession = await upsertAuthSession(env.DB as any, user);
      auth.pending_set_cookies.push(
        serializeCookie(COOKIE_AUTH_TOKEN, authSession.token, {
          maxAge: AUTH_COOKIE_MAX_AGE_SECONDS,
        })
      );

      return jsonResponse({
        data: {
          role: user.role,
          is_authenticated: true,
          principal_id: buildUserPrincipalId(user.id),
          anon_id: auth.anon_id,
          user: {
            id: user.id,
            username: user.username,
            display_name: user.display_name,
            role: user.role,
          },
        },
      });
    }

    if (relativePath === '/auth/logout' && request.method === 'POST') {
      if (auth.auth_token) {
        await deleteAuthSession(env.DB as any, auth.auth_token);
      }
      auth.pending_set_cookies.push(serializeCookie(COOKIE_AUTH_TOKEN, '', { maxAge: 0 }));
      return jsonResponse({
        data: {
          role: 'anon',
          is_authenticated: false,
          principal_id: buildAnonPrincipalId(auth.anon_id),
          anon_id: auth.anon_id,
          user: null,
        },
      });
    }

    env = withRequestAccessTokenEnv(request, withRequestLocalLlmEnv(request, env));

    if (relativePath === '/kb' || relativePath.startsWith('/kb/')) {
      return handleKbProxyRequest({
        request,
        env: env as any,
        relativePath,
        auth,
        createId: deps.createId,
      });
    }

    if (isResearcherFeaturePath(relativePath) && auth.role !== 'admin') {
      return jsonResponse({ error: 'forbidden' }, { status: 403 });
    }
    const ownerScope = resolveOwnerScope(auth);

    if (relativePath === '/ab-test/stats' && request.method === 'GET') {
      const stats = await getAbTestStats(env.DB as any);
      return jsonResponse({ data: stats });
    }

    const researchResponse = await handleResearchApiRequest({
      request,
      relativePath,
      url,
      env: env as any,
      ownerScope,
      parseResearchFilters: deps.parseResearchFilters,
      resolveResearchFilterIssueTypes: deps.resolveResearchFilterIssueTypes,
      parsePagination: deps.parsePagination,
      listIssueTypes: deps.listIssueTypes,
      ensureIssueTypeByName: deps.ensureIssueTypeByName,
      updateIssueTypeRecord: deps.updateIssueTypeRecord,
      mergeIssueTypes: deps.mergeIssueTypes,
      getResearchOptions: deps.getResearchOptions,
      getResearchOverview: deps.getResearchOverview,
      listResearchEvals: deps.listResearchEvals,
      createEvalRecord: deps.createEvalRecord,
      getAgentSessionMeta: deps.getAgentSessionMeta,
      getEvalRecordById: deps.getEvalRecordById,
      normalizeIssueSeverity: deps.normalizeIssueSeverity,
      normalizeIssuePriority: deps.normalizeIssuePriority,
      normalizeIssueStatus: deps.normalizeIssueStatus,
      updateEvalRecord: deps.updateEvalRecord,
      listResearchIssues: deps.listResearchIssues,
      createIssueRecord: deps.createIssueRecord,
      getIssueRecordById: deps.getIssueRecordById,
      listIssueEventsByIssueId: deps.listIssueEventsByIssueId,
      updateIssueRecord: deps.updateIssueRecord,
    });
    if (researchResponse) {
      return researchResponse;
    }

    const ruleConfigResponse = await handleRuleConfigApiRequest({
      request,
      relativePath,
      env: env as any,
      auth,
      ruleConfigService: deps.ruleConfigService,
    });
    if (ruleConfigResponse) {
      return ruleConfigResponse;
    }

    const rulesResponse = await handleRulesApiRequest({
      request,
      relativePath,
      url,
      env: env as any,
      normalizeExamples: deps.normalizeExamples,
      createId: deps.createId,
      executeRuleTest: deps.executeRuleTest,
    });
    if (rulesResponse) {
      return rulesResponse;
    }

    const scenariosResponse = await handleScenariosApiRequest({
      request,
      relativePath,
      url,
      env: env as any,
      createId: deps.createId,
    });
    if (scenariosResponse) {
      return scenariosResponse;
    }

    const aliasesResponse = await handleAliasesApiRequest({
      request,
      relativePath,
      url,
      env: env as any,
      auth,
      createId: deps.createId,
    });
    if (aliasesResponse) {
      return aliasesResponse;
    }

    const sessionsResponse = await handleSessionsApiRequest({
      request,
      relativePath,
      env,
      auth,
      defaultSessionTitle: deps.defaultSessionTitle,
      listAgentSessions: deps.listAgentSessions,
      createAgentSession: deps.createAgentSession,
      getAgentSession: deps.getAgentSession,
      getAgentSessionMeta: deps.getAgentSessionMeta,
      sanitizeGeneratedTitle: deps.sanitizeGeneratedTitle,
      updateSessionTitle: deps.updateSessionTitle,
      deleteAgentSession: deps.deleteAgentSession,
    });
    if (sessionsResponse) {
      return sessionsResponse;
    }

    const chatResponse = await handleChatApiRequest({
      request,
      relativePath,
      env,
      auth,
      ctx,
      getAgentSession: deps.getAgentSession,
      getAgentSessionMeta: deps.getAgentSessionMeta,
      handleChatStream: deps.handleChatStream,
      handleDirectStreamProbe: deps.handleDirectStreamProbe,
      handlePipelineStreamProbe: deps.handlePipelineStreamProbe,
      handleChat: deps.handleChat,
      handleReportSummary: deps.handleReportSummary,
    });
    if (chatResponse) {
      return chatResponse;
    }

    return new Response('找不到接口', { status: 404 });
  }

  return { handleRequest };
}

function isResearcherFeaturePath(relativePath: string): boolean {
  return relativePath.startsWith('/research');
}

function resolveOwnerScope(auth: RequestAuthContext): string | undefined {
  if (auth.role === 'admin') return undefined;
  return auth.principal_id;
}

function withRequestLocalLlmEnv(request: Request, env: EnvLike): EnvLike {
  const baseUrl = sanitizeSelfHostedLlmBaseUrl(
    request.headers.get('x-self-hosted-llm-base-url') ?? request.headers.get('x-local-llm-base-url')
  );
  const model = sanitizeSelfHostedLlmModel(
    request.headers.get('x-self-hosted-llm-model') ?? request.headers.get('x-local-llm-model')
  );
  const reportBaseUrl = sanitizeSelfHostedLlmBaseUrl(
    request.headers.get('x-self-hosted-report-base-url')
  );
  const reportModel = sanitizeSelfHostedLlmModel(request.headers.get('x-self-hosted-report-model'));
  if ((!baseUrl || !model) && (!reportBaseUrl || !reportModel)) {
    return env;
  }
  const next = {
    ...env,
  };
  if (baseUrl && model) {
    next.OPENAI_LOCAL_BASE_URL = baseUrl;
    next.OPENAI_LOCAL_MODEL = model;
  }
  if (reportBaseUrl && reportModel) {
    next.OPENAI_LOCAL_REPORT_BASE_URL = reportBaseUrl;
    next.OPENAI_LOCAL_REPORT_MODEL = reportModel;
  }
  return next;
}

function withRequestAccessTokenEnv(request: Request, env: EnvLike): EnvLike {
  const accessToken = request.headers.get('X-Access-Token')?.trim();
  if (!accessToken) {
    return env;
  }
  return {
    ...env,
    MCP_ACCESS_TOKEN: accessToken,
  };
}

function sanitizeSelfHostedLlmModel(value: string | null): string | null {
  const trimmed = value?.trim() ?? '';
  if (!trimmed || trimmed.length > 128) {
    return null;
  }
  return trimmed;
}

function sanitizeSelfHostedLlmBaseUrl(value: string | null): string | null {
  const trimmed = value?.trim() ?? '';
  if (!trimmed || trimmed.length > 512) {
    return null;
  }
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return null;
  }
  return trimmed;
}
