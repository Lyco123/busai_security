import { jsonResponse } from './http/response';
import { resolveKbTimeoutMs } from './kb-query-tool';

export interface KbProxyEnv {
  KB_API_BASE_URL?: string;
  KB_API_TIMEOUT_MS?: string;
  KB_TENANT_ID?: string;
}

export interface KbProxyAuthContext {
  role: 'anon' | 'user' | 'admin';
  principal_id: string;
  user: {
    id: string;
    kb_level?: 'driver' | 'fleet' | 'company' | 'group';
    company_id?: string;
  } | null;
}

function resolveKbCallerLevel(auth: KbProxyAuthContext): 'driver' | 'fleet' | 'company' | 'group' {
  const userLevel = auth.user?.kb_level;
  if (
    userLevel === 'driver' ||
    userLevel === 'fleet' ||
    userLevel === 'company' ||
    userLevel === 'group'
  ) {
    return userLevel;
  }
  return auth.role === 'admin' ? 'group' : 'driver';
}

function matchKbProxyRoute(
  relativePath: string,
  method: string
): { targetPath: string; write: boolean } | null {
  if (relativePath.startsWith('/kb/documents/') && relativePath.includes('/clauses')) {
    return null;
  }
  if (relativePath === '/kb/retrieve' && method === 'POST') {
    return { targetPath: '/v1/retrieve', write: false };
  }
  if (relativePath === '/kb/reindex' && method === 'POST') {
    return { targetPath: '/v1/reindex', write: true };
  }
  if (relativePath === '/kb/documents/preview' && method === 'POST') {
    return { targetPath: '/v1/documents/preview', write: true };
  }
  if (relativePath === '/kb/documents/commit' && method === 'POST') {
    return { targetPath: '/v1/documents/commit', write: true };
  }
  if (/^\/kb\/documents\/[^/]+\/replace$/.test(relativePath) && method === 'POST') {
    const docId = decodeURIComponent(relativePath.split('/')[3] ?? '');
    return { targetPath: `/v1/documents/${encodeURIComponent(docId)}/replace`, write: true };
  }
  if (relativePath === '/kb/documents' && (method === 'GET' || method === 'POST')) {
    return { targetPath: '/v1/documents', write: method !== 'GET' };
  }
  if (/^\/kb\/documents\/[^/]+\/file$/.test(relativePath) && method === 'GET') {
    const docId = decodeURIComponent(relativePath.split('/')[3] ?? '');
    return { targetPath: `/v1/documents/${encodeURIComponent(docId)}/file`, write: false };
  }
  if (
    /^\/kb\/documents\/[^/]+$/.test(relativePath) &&
    ['GET', 'PATCH', 'DELETE'].includes(method)
  ) {
    const docId = decodeURIComponent(relativePath.split('/')[3] ?? '');
    return {
      targetPath: `/v1/documents/${encodeURIComponent(docId)}`,
      write: method !== 'GET',
    };
  }
  if (/^\/kb\/jobs\/[^/]+$/.test(relativePath) && method === 'GET') {
    const jobId = decodeURIComponent(relativePath.split('/')[3] ?? '');
    return { targetPath: `/v1/jobs/${encodeURIComponent(jobId)}`, write: false };
  }
  return null;
}

export async function handleKbProxyRequest(options: {
  request: Request;
  env: KbProxyEnv;
  relativePath: string;
  auth: KbProxyAuthContext;
  createId: (prefix: string) => string;
}): Promise<Response> {
  const { request, env, relativePath, auth, createId } = options;
  const route = matchKbProxyRoute(relativePath, request.method.toUpperCase());
  if (!route) {
    return jsonResponse({ error: 'not found' }, { status: 404 });
  }

  if (auth.role === 'anon') {
    return jsonResponse({ error: 'forbidden' }, { status: 403 });
  }

  const baseUrl = String(env.KB_API_BASE_URL ?? '').replace(/\/+$/, '');
  if (!baseUrl) {
    return jsonResponse({ error: 'KB_API_BASE_URL is not configured' }, { status: 500 });
  }

  const sourceUrl = new URL(request.url);
  const targetUrl = new URL(`${baseUrl}${route.targetPath}`);
  sourceUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.set(key, value);
  });

  const callerLevel = resolveKbCallerLevel(auth);
  const callerId = auth.user?.id || auth.principal_id;
  const companyId = auth.user?.company_id;

  const headers = new Headers();
  const contentType = request.headers.get('content-type');
  if (contentType) {
    headers.set('Content-Type', contentType);
  }
  headers.set('X-Tenant-Id', String(env.KB_TENANT_ID || 'default'));
  headers.set('X-Caller-Level', callerLevel);
  headers.set('X-Caller-Id', callerId);
  headers.set('X-Request-Id', request.headers.get('x-request-id') || createId('req'));
  if (companyId) {
    headers.set('X-Caller-Company-Id', companyId);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), resolveKbTimeoutMs(env));

  try {
    const upstream = await fetch(targetUrl.toString(), {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
      signal: controller.signal,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: new Headers(upstream.headers),
    });
  } catch (error) {
    return jsonResponse(
      {
        error: error instanceof Error ? error.message : 'kb proxy failed',
      },
      { status: 502 }
    );
  } finally {
    clearTimeout(timer);
  }
}
