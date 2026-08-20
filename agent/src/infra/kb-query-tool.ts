export type QueryKbAction = 'retrieve' | 'get_document' | 'list_documents';

export interface QueryKbArgs {
  action: QueryKbAction;
  kb_id?: string;
  query?: string;
  doc_id?: string;
  top_k?: number;
  include_clauses?: boolean;
  limit?: number;
  offset?: number;
}

export interface QueryKbResult {
  success: boolean;
  action: QueryKbAction;
  disabled?: boolean;
  data?: unknown;
  error?: string;
}

export interface KbQueryToolEnv {
  KB_API_BASE_URL?: string;
  KB_API_TIMEOUT_MS?: string;
  KB_DEFAULT_ID?: string;
  KB_TOOL_ENABLED?: string;
  KB_TENANT_ID?: string;
}

export function isKbToolEnabled(env: KbQueryToolEnv): boolean {
  const raw = String(env.KB_TOOL_ENABLED ?? 'false').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on';
}

export function resolveKbTimeoutMs(env: KbQueryToolEnv): number {
  const value = Number(env.KB_API_TIMEOUT_MS ?? '20000');
  if (!Number.isFinite(value) || value <= 0) {
    return 20000;
  }
  return Math.floor(value);
}

function createKbToolRequestHeaders(env: KbQueryToolEnv): Headers {
  const headers = new Headers();
  headers.set('Content-Type', 'application/json; charset=utf-8');
  headers.set('X-Tenant-Id', String(env.KB_TENANT_ID || 'default'));
  headers.set('X-Caller-Level', 'group');
  headers.set('X-Caller-Id', 'agent-runtime');
  return headers;
}

export async function executeQueryKb(env: KbQueryToolEnv, args: QueryKbArgs): Promise<QueryKbResult> {
  if (!isKbToolEnabled(env)) {
    return {
      success: false,
      action: args.action,
      disabled: true,
      error: 'KB tool is disabled (KB_TOOL_ENABLED=false)',
    };
  }

  const baseUrl = String(env.KB_API_BASE_URL ?? '').replace(/\/+$/, '');
  if (!baseUrl) {
    return {
      success: false,
      action: args.action,
      error: 'KB_API_BASE_URL is not configured',
    };
  }

  const kbId = String(args.kb_id || env.KB_DEFAULT_ID || 'regulations');
  const timeoutMs = resolveKbTimeoutMs(env);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    if (args.action === 'retrieve') {
      const response = await fetch(`${baseUrl}/v1/retrieve`, {
        method: 'POST',
        headers: createKbToolRequestHeaders(env),
        body: JSON.stringify({
          kb_id: kbId,
          query: String(args.query ?? ''),
          top_k: args.top_k,
        }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        return {
          success: false,
          action: args.action,
          error: (data as { error?: { message?: string } } | null)?.error?.message || 'query_kb retrieve failed',
        };
      }
      return { success: true, action: args.action, data };
    }

    if (args.action === 'get_document') {
      const docId = String(args.doc_id ?? '').trim();
      if (!docId) {
        return { success: false, action: args.action, error: 'doc_id is required' };
      }
      const include = args.include_clauses === false ? 'false' : 'true';
      const response = await fetch(
        `${baseUrl}/v1/documents/${encodeURIComponent(docId)}?kb_id=${encodeURIComponent(kbId)}&include_clauses=${include}`,
        {
          headers: createKbToolRequestHeaders(env),
          signal: controller.signal,
        }
      );
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        return {
          success: false,
          action: args.action,
          error: (data as { error?: { message?: string } } | null)?.error?.message || 'query_kb get_document failed',
        };
      }
      return { success: true, action: args.action, data };
    }

    const params = new URLSearchParams({
      kb_id: kbId,
      limit: String(args.limit ?? 20),
      offset: String(args.offset ?? 0),
    });
    const response = await fetch(`${baseUrl}/v1/documents?${params.toString()}`, {
      headers: createKbToolRequestHeaders(env),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      return {
        success: false,
        action: args.action,
        error: (data as { error?: { message?: string } } | null)?.error?.message || 'query_kb list_documents failed',
      };
    }
    return { success: true, action: args.action, data };
  } catch (error) {
    return {
      success: false,
      action: args.action,
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timer);
  }
}
