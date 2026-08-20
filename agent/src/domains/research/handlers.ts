import { jsonResponse, readJson } from '../../infra/http/response';
import {
  buildMcpToolSummary,
  callMcpToolDebug,
  getMcpToolDetail,
  probeMcpServer,
} from '../../shared/mcp';
import type { D1Database } from '../scenarios/repository';

type EvalConclusion = 'pass' | 'warning' | 'fail';
type IssueSeverity = 'low' | 'medium' | 'high' | 'critical';
type IssuePriority = 'p0' | 'p1' | 'p2' | 'p3';
type IssueStatus = 'pending_confirm' | 'in_progress' | 'pending_verify' | 'closed';
type IssueSubmitMode = 'quick' | 'full';
type EvalSource = 'assistant' | 'research';

interface ResearchHandlersDeps {
  request: Request;
  relativePath: string;
  url: URL;
  env: {
    DB: D1Database;
    MCP_SERVER_URL?: string;
    CF_ACCESS_CLIENT_ID?: string;
    CF_ACCESS_CLIENT_SECRET?: string;
    MCP_ACCESS_TOKEN?: string;
  };
  ownerScope?: string;
  parseResearchFilters: any;
  resolveResearchFilterIssueTypes: any;
  parsePagination: any;
  listIssueTypes: any;
  ensureIssueTypeByName: any;
  updateIssueTypeRecord: any;
  mergeIssueTypes: any;
  getResearchOptions: any;
  getResearchOverview: any;
  listResearchEvals: any;
  createEvalRecord: any;
  getAgentSessionMeta: any;
  getEvalRecordById: any;
  normalizeIssueSeverity: any;
  normalizeIssuePriority: any;
  normalizeIssueStatus: any;
  updateEvalRecord: any;
  listResearchIssues: any;
  createIssueRecord: any;
  getIssueRecordById: any;
  listIssueEventsByIssueId: any;
  updateIssueRecord: any;
}

const getMcpConfig = (env: ResearchHandlersDeps['env']) => ({
  serverUrl: env.MCP_SERVER_URL,
  clientId: env.CF_ACCESS_CLIENT_ID,
  clientSecret: env.CF_ACCESS_CLIENT_SECRET,
  accessToken: env.MCP_ACCESS_TOKEN,
});

export async function handleResearchApiRequest(deps: ResearchHandlersDeps): Promise<Response | null> {
  const {
    request,
    relativePath,
    url,
    env,
    ownerScope,
    parseResearchFilters,
    resolveResearchFilterIssueTypes,
    parsePagination,
    listIssueTypes,
    ensureIssueTypeByName,
    updateIssueTypeRecord,
    mergeIssueTypes,
    getResearchOptions,
    getResearchOverview,
    listResearchEvals,
    createEvalRecord,
    getAgentSessionMeta,
    getEvalRecordById,
    normalizeIssueSeverity,
    normalizeIssuePriority,
    normalizeIssueStatus,
    updateEvalRecord,
    listResearchIssues,
    createIssueRecord,
    getIssueRecordById,
    listIssueEventsByIssueId,
    updateIssueRecord,
  } = deps;

  if (relativePath === '/research/mcp/status' && request.method === 'GET') {
    const data = await probeMcpServer(getMcpConfig(env));
    return jsonResponse({ data });
  }

  if (relativePath === '/research/mcp/tools' && request.method === 'GET') {
    const probe = await probeMcpServer(getMcpConfig(env));
    const data = {
      configured: probe.configured,
      ok: probe.ok,
      target_url: probe.target_url,
      protocol_version: probe.protocol_version,
      tool_count: probe.tool_count,
      stages: probe.stages,
      total_duration_ms: probe.total_duration_ms,
      tools: probe.tools.map(buildMcpToolSummary),
      ...(probe.error ? { error: probe.error } : {}),
      timestamp: probe.timestamp,
    };
    return jsonResponse({ data });
  }

  const mcpToolDetailMatch = relativePath.match(/^\/research\/mcp\/tools\/([^/]+)$/);
  if (mcpToolDetailMatch && request.method === 'GET') {
    const toolName = decodeURIComponent(mcpToolDetailMatch[1]);
    const data = await getMcpToolDetail(getMcpConfig(env), toolName);
    return jsonResponse({ data });
  }

  const mcpToolCallMatch = relativePath.match(/^\/research\/mcp\/tools\/([^/]+)\/call$/);
  if (mcpToolCallMatch && request.method === 'POST') {
    const toolName = decodeURIComponent(mcpToolCallMatch[1]);
    const payload = await readJson<{ arguments?: Record<string, unknown> }>(request);
    const args = payload?.arguments;
    if (args && (typeof args !== 'object' || Array.isArray(args))) {
      return jsonResponse({ error: 'arguments must be an object' }, { status: 400 });
    }
    const data = await callMcpToolDebug(getMcpConfig(env), toolName, args ?? {});
    return jsonResponse({ data });
  }

  if (relativePath === '/research/options' && request.method === 'GET') {
    const data = await getResearchOptions(env.DB, ownerScope);
    return jsonResponse({ data });
  }

  if (relativePath === '/research/issue-types' && request.method === 'GET') {
    const includeDisabled = url.searchParams.get('include_disabled') === 'true';
    const includeMerged = url.searchParams.get('include_merged') === 'true';
    const keyword = url.searchParams.get('keyword')?.trim() || undefined;
    const data = await listIssueTypes(env.DB, { includeDisabled, includeMerged, keyword });
    return jsonResponse({ data });
  }

  if (relativePath === '/research/issue-types' && request.method === 'POST') {
    const payload = await readJson<{
      name?: string;
      created_by?: string;
    }>(request);
    if (!payload?.name?.trim()) {
      return jsonResponse({ error: 'missing issue type name' }, { status: 400 });
    }
    const created = await ensureIssueTypeByName(env.DB, payload.name, payload.created_by);
    if (!created) {
      return jsonResponse({ error: 'invalid issue type name' }, { status: 400 });
    }
    return jsonResponse({ data: created });
  }

  const issueTypeDetailMatch = relativePath.match(/^\/research\/issue-types\/([^/]+)$/);
  if (issueTypeDetailMatch && request.method === 'PATCH') {
    const issueTypeId = decodeURIComponent(issueTypeDetailMatch[1]);
    const payload = await readJson<{
      name?: string;
      enabled?: boolean;
      updated_by?: string;
    }>(request);
    try {
      const data = await updateIssueTypeRecord(env.DB, issueTypeId, {
        name: payload?.name,
        enabled: payload?.enabled,
        updated_by: payload?.updated_by,
      });
      if (!data) {
        return jsonResponse({ error: 'issue type not found' }, { status: 404 });
      }
      return jsonResponse({ data });
    } catch (error) {
      return jsonResponse(
        { error: error instanceof Error ? error.message : 'failed to update issue type' },
        { status: 400 }
      );
    }
  }

  if (relativePath === '/research/issue-types/merge' && request.method === 'POST') {
    const payload = await readJson<{
      target_type_id?: string;
      source_type_ids?: string[];
      operator?: string;
      note?: string;
    }>(request);
    if (!payload?.target_type_id?.trim()) {
      return jsonResponse({ error: 'missing target_type_id' }, { status: 400 });
    }
    if (!payload?.source_type_ids || payload.source_type_ids.length === 0) {
      return jsonResponse({ error: 'missing source_type_ids' }, { status: 400 });
    }
    try {
      const data = await mergeIssueTypes(env.DB, {
        target_type_id: payload.target_type_id,
        source_type_ids: payload.source_type_ids,
        operator: payload.operator,
        note: payload.note,
      });
      return jsonResponse({ data });
    } catch (error) {
      return jsonResponse({ error: error instanceof Error ? error.message : 'failed to merge issue types' }, { status: 400 });
    }
  }

  if (relativePath === '/research/overview' && request.method === 'GET') {
    const filters = parseResearchFilters(url);
    const normalized = await resolveResearchFilterIssueTypes(env.DB, filters);
    const data = await getResearchOverview(env.DB, normalized.filters, ownerScope);
    return jsonResponse({
      data,
      meta: normalized.issue_type_redirects.length > 0 ? { issue_type_redirects: normalized.issue_type_redirects } : undefined,
    });
  }

  if (relativePath === '/research/evals' && request.method === 'GET') {
    const filters = parseResearchFilters(url);
    const normalized = await resolveResearchFilterIssueTypes(env.DB, filters);
    const { page, pageSize } = parsePagination(url);
    const sortBy = url.searchParams.get('sortBy') ?? undefined;
    const sortOrder = url.searchParams.get('sortOrder') ?? undefined;
    const data = await listResearchEvals(env.DB, normalized.filters, page, pageSize, sortBy, sortOrder, ownerScope);
    return jsonResponse({
      data,
      meta: normalized.issue_type_redirects.length > 0 ? { issue_type_redirects: normalized.issue_type_redirects } : undefined,
    });
  }

  if (relativePath === '/research/evals' && request.method === 'POST') {
    const payload = await readJson<{
      session_id?: string;
      sessionId?: string;
      conclusion?: EvalConclusion;
      issue_type_ids?: string[];
      new_issue_type_names?: string[];
      confidence?: number;
      note?: string;
      tags?: string[];
      model_version?: string;
      scenario?: string;
      org_group?: string;
      org_company?: string;
      org_fleet?: string;
      org_line?: string;
      referenced_message_ids?: string[];
      source?: EvalSource;
      is_read?: boolean;
      is_favorite?: boolean;
    }>(request);
    const sessionId = payload?.session_id || payload?.sessionId;
    if (!sessionId) {
      return jsonResponse({ error: 'missing session_id' }, { status: 400 });
    }
    const session = await getAgentSessionMeta(env.DB, sessionId);
    if (!session) {
      return jsonResponse({ error: 'session not found' }, { status: 404 });
    }
    const data = await createEvalRecord(env.DB, env, {
      session_id: sessionId,
      conclusion: payload?.conclusion,
      issue_type_ids: payload?.issue_type_ids,
      new_issue_type_names: payload?.new_issue_type_names,
      confidence: payload?.confidence,
      note: payload?.note,
      tags: payload?.tags,
      model_version: payload?.model_version ?? null,
      scenario: payload?.scenario,
      org_group: payload?.org_group,
      org_company: payload?.org_company,
      org_fleet: payload?.org_fleet,
      org_line: payload?.org_line,
      referenced_message_ids: payload?.referenced_message_ids,
      source: payload?.source,
      is_read: payload?.is_read,
      is_favorite: payload?.is_favorite,
    });
    return jsonResponse({ data });
  }

  const evalDetailMatch = relativePath.match(/^\/research\/evals\/([^/]+)$/);
  if (evalDetailMatch && request.method === 'GET') {
    const evalId = decodeURIComponent(evalDetailMatch[1]);
    const evalRecord = await getEvalRecordById(env.DB, evalId, ownerScope);
    if (!evalRecord) {
      return jsonResponse({ error: 'eval not found' }, { status: 404 });
    }
    const linkedIssues = await env.DB
      .prepare(
        'SELECT id, title, severity, priority, status, updated_at FROM agent_issues WHERE source_eval_id = ? ORDER BY updated_at DESC'
      )
      .bind(evalId)
      .all<Record<string, unknown>>();
    const sessionMeta = await getAgentSessionMeta(env.DB, evalRecord.session_id);
    return jsonResponse({
      data: {
        ...evalRecord,
        linked_issues: linkedIssues.results.map((row) => ({
          id: String(row.id ?? ''),
          title: String(row.title ?? ''),
          severity: normalizeIssueSeverity(row.severity, 'medium'),
          priority: normalizeIssuePriority(row.priority, 'p2'),
          status: normalizeIssueStatus(row.status, 'pending_confirm'),
          updated_at: String(row.updated_at ?? ''),
        })),
        session: sessionMeta,
      },
    });
  }

  if (evalDetailMatch && request.method === 'PATCH') {
    const evalId = decodeURIComponent(evalDetailMatch[1]);
    const payload = await readJson<{
      conclusion?: EvalConclusion;
      issue_type_ids?: string[];
      new_issue_type_names?: string[];
      confidence?: number | null;
      note?: string;
      tags?: string[];
      is_read?: boolean;
      is_favorite?: boolean;
    }>(request);
    const data = await updateEvalRecord(env.DB, evalId, {
      conclusion: payload?.conclusion,
      issue_type_ids: payload?.issue_type_ids,
      new_issue_type_names: payload?.new_issue_type_names,
      confidence: payload?.confidence,
      note: payload?.note,
      tags: payload?.tags,
      is_read: payload?.is_read,
      is_favorite: payload?.is_favorite,
    });
    if (!data) {
      return jsonResponse({ error: 'eval not found' }, { status: 404 });
    }
    return jsonResponse({ data });
  }

  if (relativePath === '/research/issues' && request.method === 'GET') {
    const filters = parseResearchFilters(url);
    const normalized = await resolveResearchFilterIssueTypes(env.DB, filters);
    const { page, pageSize } = parsePagination(url);
    const sortBy = url.searchParams.get('sortBy') ?? undefined;
    const sortOrder = url.searchParams.get('sortOrder') ?? undefined;
    const data = await listResearchIssues(env.DB, normalized.filters, page, pageSize, sortBy, sortOrder, ownerScope);
    return jsonResponse({
      data,
      meta: normalized.issue_type_redirects.length > 0 ? { issue_type_redirects: normalized.issue_type_redirects } : undefined,
    });
  }

  if (relativePath === '/research/issues' && request.method === 'POST') {
    const payload = await readJson<{
      title?: string;
      issue_type_ids?: string[];
      new_issue_type_names?: string[];
      severity?: IssueSeverity;
      priority?: IssuePriority;
      status?: IssueStatus;
      description?: string;
      expected_result?: string;
      business_impact?: string;
      repro_steps?: string;
      session_id?: string;
      sessionId?: string;
      source_eval_id?: string;
      referenced_message_ids?: string[];
      context_summary?: string;
      model_version?: string;
      scenario?: string;
      org_group?: string;
      org_company?: string;
      org_fleet?: string;
      org_line?: string;
      assignee?: string;
      due_at?: string;
      submit_mode?: IssueSubmitMode;
      source_metric?: Record<string, unknown>;
      created_by?: string;
      updated_by?: string;
      event_note?: string;
      comment?: {
        handling_type?: string;
        description?: string;
        commit_id?: string;
      };
      operator?: string;
    }>(request);
    const sessionId = payload?.session_id || payload?.sessionId;
    if (!payload?.description?.trim()) {
      return jsonResponse({ error: 'missing description' }, { status: 400 });
    }
    if (!sessionId) {
      return jsonResponse({ error: 'missing session_id' }, { status: 400 });
    }
    const session = await getAgentSessionMeta(env.DB, sessionId);
    if (!session) {
      return jsonResponse({ error: 'session not found' }, { status: 404 });
    }
    if (payload?.source_eval_id) {
      const linkedEval = await getEvalRecordById(env.DB, payload.source_eval_id, ownerScope);
      if (!linkedEval) {
        return jsonResponse({ error: 'source eval not found' }, { status: 404 });
      }
    }
    try {
      const data = await createIssueRecord(env.DB, env, {
        title: payload.title,
        issue_type_ids: payload.issue_type_ids,
        new_issue_type_names: payload.new_issue_type_names,
        severity: payload.severity,
        priority: payload.priority,
        status: payload.status,
        description: payload.description,
        expected_result: payload.expected_result,
        business_impact: payload.business_impact,
        repro_steps: payload.repro_steps,
        session_id: sessionId,
        source_eval_id: payload.source_eval_id,
        referenced_message_ids: payload.referenced_message_ids,
        context_summary: payload.context_summary,
        model_version: payload.model_version ?? null,
        scenario: payload.scenario,
        org_group: payload.org_group,
        org_company: payload.org_company,
        org_fleet: payload.org_fleet,
        org_line: payload.org_line,
        assignee: payload.assignee,
        due_at: payload.due_at,
        submit_mode: payload.submit_mode,
        source_metric: payload.source_metric,
        created_by: payload.created_by,
        updated_by: payload.updated_by,
        event_note: payload.event_note,
        comment: payload.comment,
        operator: payload.operator,
      });
      return jsonResponse({ data });
    } catch (error) {
      return jsonResponse(
        { error: error instanceof Error ? error.message : 'failed to create issue' },
        { status: 400 }
      );
    }
  }

  const issueDetailMatch = relativePath.match(/^\/research\/issues\/([^/]+)$/);
  if (issueDetailMatch && request.method === 'GET') {
    const issueId = decodeURIComponent(issueDetailMatch[1]);
    const issue = await getIssueRecordById(env.DB, issueId, ownerScope);
    if (!issue) {
      return jsonResponse({ error: 'issue not found' }, { status: 404 });
    }
    const events = await listIssueEventsByIssueId(env.DB, issueId);
    const linkedEval = issue.source_eval_id ? await getEvalRecordById(env.DB, issue.source_eval_id, ownerScope) : null;
    const sessionMeta = await getAgentSessionMeta(env.DB, issue.session_id);
    return jsonResponse({
      data: {
        ...issue,
        events,
        linked_eval: linkedEval,
        session: sessionMeta,
      },
    });
  }

  if (issueDetailMatch && request.method === 'PATCH') {
    const issueId = decodeURIComponent(issueDetailMatch[1]);
    const payload = await readJson<{
      title?: string;
      issue_type_ids?: string[];
      new_issue_type_names?: string[];
      severity?: IssueSeverity;
      priority?: IssuePriority;
      status?: IssueStatus;
      description?: string;
      expected_result?: string;
      business_impact?: string;
      repro_steps?: string;
      assignee?: string;
      due_at?: string | null;
      context_summary?: string;
      scenario?: string;
      org_group?: string;
      org_company?: string;
      org_fleet?: string;
      org_line?: string;
      submit_mode?: IssueSubmitMode;
      updated_by?: string;
      event_note?: string;
      comment?: {
        handling_type?: string;
        description?: string;
        commit_id?: string;
      };
      operator?: string;
    }>(request);

    try {
      const data = await updateIssueRecord(env.DB, issueId, {
        title: payload?.title,
        issue_type_ids: payload?.issue_type_ids,
        new_issue_type_names: payload?.new_issue_type_names,
        severity: payload?.severity,
        priority: payload?.priority,
        status: payload?.status,
        description: payload?.description,
        expected_result: payload?.expected_result,
        business_impact: payload?.business_impact,
        repro_steps: payload?.repro_steps,
        assignee: payload?.assignee,
        due_at: payload?.due_at,
        context_summary: payload?.context_summary,
        scenario: payload?.scenario,
        org_group: payload?.org_group,
        org_company: payload?.org_company,
        org_fleet: payload?.org_fleet,
        org_line: payload?.org_line,
        submit_mode: payload?.submit_mode,
        updated_by: payload?.updated_by,
        event_note: payload?.event_note,
        comment: payload?.comment ?? null,
        operator: payload?.operator,
      });
      if (!data) {
        return jsonResponse({ error: 'issue not found' }, { status: 404 });
      }
      return jsonResponse({ data });
    } catch (error) {
      return jsonResponse(
        { error: error instanceof Error ? error.message : 'failed to update issue' },
        { status: 400 }
      );
    }
  }

  return null;
}
