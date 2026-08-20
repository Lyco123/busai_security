import type { RequestAuthContext } from '../../infra/auth/session-store';
import { jsonResponse, readJson } from '../../infra/http/response';
import {
  deleteEntityAlias,
  insertEntityAlias,
  listEntityAliases,
  listEntityStandardNames,
  updateEntityAliasStatus,
  upsertEntityStandardName,
  type D1Database,
  type EntityAliasStatus,
  type EntityAliasType,
} from './repository';

interface AliasHandlersDeps {
  request: Request;
  relativePath: string;
  url: URL;
  env: {
    DB: D1Database;
  };
  auth: RequestAuthContext;
  createId: (prefix: string) => string;
}

function parseEntityType(value: string | null | undefined): EntityAliasType | null {
  if (value === 'unit' || value === 'route' || value === 'fleet') return value;
  return null;
}

function parseStatus(value: string | null | undefined): EntityAliasStatus | null {
  if (value === 'pending' || value === 'approved' || value === 'rejected') return value;
  return null;
}

function normalizeText(value: unknown): string {
  return typeof value === 'string' ? value.normalize('NFKC').trim() : '';
}

function requireAuthenticated(auth: RequestAuthContext): Response | null {
  if (auth.role === 'anon' || !auth.is_authenticated) {
    return jsonResponse({ error: 'authentication required' }, { status: 401 });
  }
  return null;
}

function requireAdmin(auth: RequestAuthContext): Response | null {
  if (auth.role !== 'admin') {
    return jsonResponse({ error: 'forbidden' }, { status: 403 });
  }
  return null;
}

export async function handleAliasesApiRequest(deps: AliasHandlersDeps): Promise<Response | null> {
  const { request, relativePath, url, env, auth, createId } = deps;

  if (relativePath === '/aliases/standards' && request.method === 'GET') {
    const entityType = parseEntityType(url.searchParams.get('entity_type') || undefined);
    const standards = await listEntityStandardNames(env.DB, { entityType: entityType ?? undefined });
    return jsonResponse({ data: standards });
  }

  if (relativePath === '/aliases' && request.method === 'GET') {
    const entityType = parseEntityType(url.searchParams.get('entity_type') || undefined);
    const status = parseStatus(url.searchParams.get('status') || undefined);
    const aliases = await listEntityAliases(env.DB, {
      entityType: entityType ?? undefined,
      status: status ?? undefined,
    });
    return jsonResponse({ data: aliases });
  }

  if (relativePath === '/aliases' && request.method === 'POST') {
    const authError = requireAuthenticated(auth);
    if (authError) return authError;

    const payload = await readJson<{
      entity_type?: string;
      standard_name?: string;
      alias?: string;
    }>(request);
    const entityType = parseEntityType(payload?.entity_type);
    const standardName = normalizeText(payload?.standard_name);
    const alias = normalizeText(payload?.alias);

    if (!entityType || !standardName || !alias) {
      return jsonResponse({ error: 'entity_type, standard_name and alias are required' }, { status: 400 });
    }
    if (standardName === alias) {
      return jsonResponse({ error: 'alias must be different from standard_name' }, { status: 400 });
    }

    await upsertEntityStandardName(env.DB, {
      id: createId('entity_standard'),
      entityType,
      standardName,
    });

    const status: EntityAliasStatus = auth.role === 'admin' ? 'approved' : 'pending';
    const aliasRecord = await insertEntityAlias(env.DB, {
      id: createId('entity_alias'),
      entityType,
      standardName,
      alias,
      status,
      submittedBy: auth.principal_id,
      submittedByRole: auth.role,
      reviewedBy: auth.role === 'admin' ? auth.principal_id : null,
    });
    return jsonResponse({ data: aliasRecord });
  }

  const approveMatch = relativePath.match(/^\/aliases\/([^/]+)\/approve$/);
  if (approveMatch && request.method === 'POST') {
    const adminError = requireAdmin(auth);
    if (adminError) return adminError;
    const aliasRecord = await updateEntityAliasStatus(
      env.DB,
      decodeURIComponent(approveMatch[1]),
      'approved',
      auth.principal_id
    );
    if (!aliasRecord) {
      return jsonResponse({ error: 'alias not found' }, { status: 404 });
    }
    await upsertEntityStandardName(env.DB, {
      id: createId('entity_standard'),
      entityType: aliasRecord.entity_type,
      standardName: aliasRecord.standard_name,
    });
    return jsonResponse({ data: aliasRecord });
  }

  const rejectMatch = relativePath.match(/^\/aliases\/([^/]+)\/reject$/);
  if (rejectMatch && request.method === 'POST') {
    const adminError = requireAdmin(auth);
    if (adminError) return adminError;
    const aliasRecord = await updateEntityAliasStatus(
      env.DB,
      decodeURIComponent(rejectMatch[1]),
      'rejected',
      auth.principal_id
    );
    if (!aliasRecord) {
      return jsonResponse({ error: 'alias not found' }, { status: 404 });
    }
    return jsonResponse({ data: aliasRecord });
  }

  const deleteMatch = relativePath.match(/^\/aliases\/([^/]+)$/);
  if (deleteMatch && request.method === 'DELETE') {
    const adminError = requireAdmin(auth);
    if (adminError) return adminError;
    await deleteEntityAlias(env.DB, decodeURIComponent(deleteMatch[1]));
    return jsonResponse({ success: true });
  }

  return null;
}
