export interface CorsEnv {
  CORS_ALLOWED_ORIGINS?: string;
}

export function parseCorsAllowedOrigins(env: CorsEnv): string[] {
  return (env.CORS_ALLOWED_ORIGINS || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function isCorsOriginAllowed(requestOrigin: string, requestUrl: URL, env: CorsEnv): boolean {
  if (requestOrigin === requestUrl.origin) {
    return true;
  }
  const configuredOrigins = parseCorsAllowedOrigins(env);
  if (configuredOrigins.length > 0) {
    return configuredOrigins.includes('*') || configuredOrigins.includes(requestOrigin);
  }
  return (
    /^https:\/\/([a-z0-9-]+\.)*canocache\.com$/i.test(requestOrigin) ||
    /^https?:\/\/localhost(?::\d+)?$/i.test(requestOrigin) ||
    /^https?:\/\/127\.0\.0\.1(?::\d+)?$/i.test(requestOrigin)
  );
}

export function withCors(response: Response, request: Request, env: CorsEnv): Response {
  const headers = new Headers(response.headers);
  const requestOrigin = request.headers.get('Origin');
  const requestUrl = new URL(request.url);
  if (requestOrigin && isCorsOriginAllowed(requestOrigin, requestUrl, env)) {
    headers.set('Access-Control-Allow-Origin', requestOrigin);
    headers.set('Access-Control-Allow-Credentials', 'true');
    headers.set('Vary', 'Origin');
  }
  headers.set('Access-Control-Allow-Methods', 'GET,POST,PATCH,DELETE,OPTIONS');
  headers.set(
    'Access-Control-Allow-Headers',
    request.headers.get('Access-Control-Request-Headers') || 'Content-Type, Authorization'
  );
  headers.set('Access-Control-Max-Age', '86400');
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
