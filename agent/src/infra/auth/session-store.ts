import type { D1Database } from '../../domains/scenarios/repository';
import {
  buildAnonPrincipalId,
  buildUserPrincipalId,
  createAnonId,
  isValidAnonId,
  parseCookieHeader,
  serializeCookie,
} from './cookies';

export type AuthRole = 'anon' | 'user' | 'admin';

export interface AuthUserRecord {
  id: string;
  username: string;
  password: string;
  role: 'user' | 'admin';
  display_name: string;
  enabled: boolean;
  kb_level?: 'driver' | 'fleet' | 'company' | 'group';
  company_id?: string;
}

export interface RequestAuthContext {
  role: AuthRole;
  is_authenticated: boolean;
  principal_id: string;
  anon_id: string;
  user: Omit<AuthUserRecord, 'password' | 'enabled'> | null;
  auth_token: string | null;
  pending_set_cookies: string[];
}

export type AuthUserInfo = Omit<AuthUserRecord, 'password' | 'enabled'>;

export interface TokenVerifier {
  verify(input: { credential: string; db: D1Database }): Promise<AuthUserInfo | null>;
}

export const COOKIE_ANON_ID = 'bus_anon_id';
export const COOKIE_AUTH_TOKEN = 'bus_auth_token';
export const AUTH_COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;
export const ANON_COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60;

function createAuthId(prefix: string): string {
  return `${prefix}_${crypto.randomUUID()}`;
}

export async function getAuthUserByUsername(
  db: D1Database,
  username: string
): Promise<AuthUserRecord | null> {
  const row = await selectAuthUser(db, 'username = ?', username);
  if (!row) return null;
  return normalizeAuthUser(row);
}

export async function getAuthUserById(db: D1Database, id: string): Promise<AuthUserRecord | null> {
  const row = await selectAuthUser(db, 'id = ?', id);
  if (!row) return null;
  return normalizeAuthUser(row);
}

async function selectAuthUser(
  db: D1Database,
  whereClause: string,
  value: string
): Promise<AuthUserRow | null> {
  try {
    return await db
      .prepare(
        `SELECT id, username, password, role, display_name, enabled, kb_level, company_id FROM agent_users WHERE ${whereClause} LIMIT 1`
      )
      .bind(value)
      .first<AuthUserRow>();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (
      !message.includes('kb_level') &&
      !message.includes('company_id') &&
      !message.includes('no such column')
    ) {
      throw error;
    }
    return db
      .prepare(
        `SELECT id, username, password, role, display_name, enabled FROM agent_users WHERE ${whereClause} LIMIT 1`
      )
      .bind(value)
      .first<AuthUserRow>();
  }
}

function normalizeAuthUser(row: AuthUserRow): AuthUserRecord | null {
  const role = row.role === 'admin' ? 'admin' : row.role === 'user' ? 'user' : null;
  if (!role) return null;
  return {
    id: row.id,
    username: row.username,
    password: row.password,
    role,
    display_name: row.display_name,
    enabled: Number(row.enabled ?? 1) === 1,
    kb_level:
      row.kb_level === 'driver' ||
      row.kb_level === 'fleet' ||
      row.kb_level === 'company' ||
      row.kb_level === 'group'
        ? row.kb_level
        : undefined,
    company_id: row.company_id ? String(row.company_id) : undefined,
  };
}

interface AuthUserRow {
  id: string;
  username: string;
  password: string;
  role: string;
  display_name: string;
  enabled: number | string;
  kb_level?: string | null;
  company_id?: string | null;
}

export async function getAuthSessionByToken(
  db: D1Database,
  token: string
): Promise<{ token: string; user_id: string; role: string; expires_at: string } | null> {
  return db
    .prepare(
      'SELECT token, user_id, role, expires_at FROM agent_auth_sessions WHERE token = ? LIMIT 1'
    )
    .bind(token)
    .first<{ token: string; user_id: string; role: string; expires_at: string }>();
}

export async function upsertAuthSession(
  db: D1Database,
  user: AuthUserRecord
): Promise<{ token: string; expires_at: string }> {
  const now = new Date();
  const expiresAt = new Date(now.getTime() + AUTH_COOKIE_MAX_AGE_SECONDS * 1000);
  const token = createAuthId('auth');
  await db
    .prepare(
      'INSERT INTO agent_auth_sessions (token, user_id, role, created_at, expires_at) VALUES (?, ?, ?, ?, ?)'
    )
    .bind(token, user.id, user.role, now.toISOString(), expiresAt.toISOString())
    .run();
  return {
    token,
    expires_at: expiresAt.toISOString(),
  };
}

export async function deleteAuthSession(db: D1Database, token: string): Promise<void> {
  await db.prepare('DELETE FROM agent_auth_sessions WHERE token = ?').bind(token).run();
}

export const demoTokenVerifier: TokenVerifier = {
  async verify({ credential, db }): Promise<AuthUserInfo | null> {
    const authSession = await getAuthSessionByToken(db, credential);
    const isExpired = !authSession || Date.parse(authSession.expires_at) <= Date.now();
    if (isExpired) {
      if (authSession) {
        await deleteAuthSession(db, credential);
      }
      return null;
    }
    const authUser = await getAuthUserById(db, authSession.user_id);
    if (!authUser || !authUser.enabled) {
      await deleteAuthSession(db, credential);
      return null;
    }
    return {
      id: authUser.id,
      username: authUser.username,
      role: authUser.role,
      display_name: authUser.display_name,
      kb_level: authUser.kb_level,
      company_id: authUser.company_id,
    };
  },
};

export async function resolveAuthContext(
  request: Request,
  db: D1Database,
  verifier: TokenVerifier = demoTokenVerifier
): Promise<RequestAuthContext> {
  const cookies = parseCookieHeader(request.headers.get('Cookie'));
  const pendingSetCookies: string[] = [];

  let anonId = cookies[COOKIE_ANON_ID];
  if (!isValidAnonId(anonId)) {
    anonId = createAnonId();
    pendingSetCookies.push(
      serializeCookie(COOKIE_ANON_ID, anonId, {
        maxAge: ANON_COOKIE_MAX_AGE_SECONDS,
      })
    );
  }

  let authToken = cookies[COOKIE_AUTH_TOKEN] || null;
  let role: AuthRole = 'anon';
  let user: Omit<AuthUserRecord, 'password' | 'enabled'> | null = null;
  let isAuthenticated = false;

  if (authToken) {
    const verified = await verifier.verify({ credential: authToken, db });
    if (!verified) {
      authToken = null;
      pendingSetCookies.push(serializeCookie(COOKIE_AUTH_TOKEN, '', { maxAge: 0 }));
    } else {
      role = verified.role;
      isAuthenticated = true;
      user = verified;
    }
  }

  return {
    role,
    is_authenticated: isAuthenticated,
    principal_id:
      isAuthenticated && user ? buildUserPrincipalId(user.id) : buildAnonPrincipalId(anonId),
    anon_id: anonId,
    user,
    auth_token: authToken,
    pending_set_cookies: pendingSetCookies,
  };
}

export function buildAuthPayload(auth: RequestAuthContext): Record<string, unknown> {
  return {
    role: auth.role,
    is_authenticated: auth.is_authenticated,
    principal_id: auth.principal_id,
    anon_id: auth.anon_id,
    user: auth.user,
  };
}
