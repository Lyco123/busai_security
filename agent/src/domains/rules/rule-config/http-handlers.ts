import { jsonResponse, readJson } from '../../../infra/http/response';

interface RuleConfigHttpHandlersDeps {
  request: Request;
  relativePath: string;
  env: any;
  auth: { principal_id: string };
  ruleConfigService: {
    startSession: (
      env: any,
      principalId: string,
      payload?: { sessionId?: string; rule_id?: string }
    ) => Promise<{ session_id: string; draft: unknown }>;
    executeRuleDraftTest: (
      env: any,
      sessionId: string,
      payload?: {
        queries?: string[];
        top_k?: number;
        min_score?: number;
        preview_reply?: boolean;
      }
    ) => Promise<{ success: boolean; data?: unknown; error?: string }>;
    confirmSession: (
      env: any,
      sessionId: string,
      options?: { forceSave?: boolean }
    ) => Promise<{
      status: string;
      state: string;
      rule_id?: string;
      conflict?: unknown;
      message: string;
      draft: unknown;
      missing_fields: string[];
      updated_fields: string[];
      rework_ticket?: unknown;
    }>;
    cancelSession: (env: any, sessionId: string) => Promise<{ success: true }>;
  };
}

export async function handleRuleConfigApiRequest(
  deps: RuleConfigHttpHandlersDeps
): Promise<Response | null> {
  const { request, relativePath, env, auth, ruleConfigService } = deps;

  if (relativePath === '/rule-config/session' && request.method === 'POST') {
    const payload = await readJson<{ sessionId?: string; rule_id?: string }>(request);
    try {
      const result = await ruleConfigService.startSession(env, auth.principal_id, payload ?? undefined);
      return jsonResponse(result);
    } catch (error) {
      if (error instanceof Error && error.message === 'rule_not_found') {
        return jsonResponse({ error: 'rule_not_found' }, { status: 404 });
      }
      return jsonResponse({ error: 'rule_config_session_create_failed' }, { status: 500 });
    }
  }

  if (
    relativePath.startsWith('/rule-config/') &&
    relativePath.endsWith('/test') &&
    request.method === 'POST'
  ) {
    const sessionId = decodeURIComponent(relativePath.replace('/rule-config/', '').replace('/test', ''));
    const payload = await readJson<{
      queries?: string[];
      top_k?: number;
      min_score?: number;
      preview_reply?: boolean;
    }>(request);
    const result = await ruleConfigService.executeRuleDraftTest(env, sessionId, payload ?? undefined);
    return jsonResponse(result);
  }

  if (
    relativePath.startsWith('/rule-config/') &&
    relativePath.endsWith('/confirm') &&
    request.method === 'POST'
  ) {
    const sessionId = decodeURIComponent(relativePath.replace('/rule-config/', '').replace('/confirm', ''));
    const payload = await readJson<{ force_save?: boolean }>(request);
    try {
      const result = await ruleConfigService.confirmSession(env, sessionId, {
        forceSave: payload?.force_save,
      });
      return jsonResponse(result);
    } catch (error) {
      if (error instanceof Error && error.message === 'rule_draft_not_found') {
        return jsonResponse({ error: 'rule_draft_not_found' }, { status: 404 });
      }
      return jsonResponse({ error: 'rule_config_confirm_failed' }, { status: 500 });
    }
  }

  if (
    relativePath.startsWith('/rule-config/') &&
    relativePath.endsWith('/cancel') &&
    request.method === 'POST'
  ) {
    const sessionId = decodeURIComponent(relativePath.replace('/rule-config/', '').replace('/cancel', ''));
    const result = await ruleConfigService.cancelSession(env, sessionId);
    return jsonResponse(result);
  }

  return null;
}
