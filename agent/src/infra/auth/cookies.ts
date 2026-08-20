export function parseCookieHeader(value: string | null): Record<string, string> {
  if (!value) return {};
  return value
    .split(';')
    .map((part) => part.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((acc, chunk) => {
      const [name, ...rest] = chunk.split('=');
      if (!name || rest.length === 0) return acc;
      const rawValue = rest.join('=');
      try {
        acc[name] = decodeURIComponent(rawValue);
      } catch {
        acc[name] = rawValue;
      }
      return acc;
    }, {});
}

export function serializeCookie(
  name: string,
  value: string,
  options?: {
    maxAge?: number;
    httpOnly?: boolean;
    sameSite?: 'Lax' | 'Strict' | 'None';
    path?: string;
  }
): string {
  const parts = [`${name}=${encodeURIComponent(value)}`];
  parts.push(`Path=${options?.path ?? '/'}`);
  if (typeof options?.maxAge === 'number') {
    parts.push(`Max-Age=${Math.max(0, Math.floor(options.maxAge))}`);
  }
  if (options?.httpOnly !== false) {
    parts.push('HttpOnly');
  }
  parts.push(`SameSite=${options?.sameSite ?? 'Lax'}`);
  return parts.join('; ');
}

export function createAnonId(): string {
  return `anon_${crypto.randomUUID()}`;
}

export function buildUserPrincipalId(userId: string): string {
  return `user:${userId}`;
}

export function buildAnonPrincipalId(anonId: string): string {
  return `anon:${anonId}`;
}

export function isValidAnonId(value: string | undefined): boolean {
  return Boolean(value && /^[a-zA-Z0-9:_-]{8,120}$/.test(value));
}

export function appendSetCookies(response: Response, cookies: string[]): Response {
  if (!cookies.length) return response;
  const headers = new Headers(response.headers);
  for (const cookie of cookies) {
    headers.append('Set-Cookie', cookie);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
