import { DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE } from '../../core/constants';

export type EvalConclusion = 'pass' | 'warning' | 'fail';
export type IssueSeverity = 'low' | 'medium' | 'high' | 'critical';
export type IssuePriority = 'p0' | 'p1' | 'p2' | 'p3';
export type IssueStatus = 'pending_confirm' | 'in_progress' | 'pending_verify' | 'closed';
export type IssueSubmitMode = 'quick' | 'full';
export type EvalSource = 'assistant' | 'research';
export type IssueTypeFilterMode = 'any' | 'all';

export interface IssueTypeRef {
  id: string;
  name: string;
}

export interface EvalRecord {
  id: string;
  session_id: string;
  conclusion: EvalConclusion;
  issue_types: IssueTypeRef[];
  confidence?: number | null;
  note?: string | null;
  tags: string[];
  model_version?: string | null;
  scenario?: string | null;
  org_group?: string | null;
  org_company?: string | null;
  org_fleet?: string | null;
  org_line?: string | null;
  referenced_message_ids: string[];
  is_read: boolean;
  is_favorite: boolean;
  source: EvalSource;
  created_at: string;
  updated_at: string;
}

export interface IssueRecord {
  id: string;
  title: string;
  issue_types: IssueTypeRef[];
  severity: IssueSeverity;
  priority: IssuePriority;
  status: IssueStatus;
  description: string;
  expected_result?: string | null;
  business_impact?: string | null;
  repro_steps?: string | null;
  session_id: string;
  source_eval_id?: string | null;
  referenced_message_ids: string[];
  context_summary?: string | null;
  model_version?: string | null;
  scenario?: string | null;
  org_group?: string | null;
  org_company?: string | null;
  org_fleet?: string | null;
  org_line?: string | null;
  assignee?: string | null;
  due_at?: string | null;
  submit_mode: IssueSubmitMode;
  source_metric?: Record<string, unknown> | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
}

export interface IssueEventRecord {
  id: string;
  issue_id: string;
  action: string;
  from_status?: string | null;
  to_status?: string | null;
  note?: string | null;
  operator?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface IssueOperationComment {
  handling_type: string;
  description: string;
  commit_id: string;
}

export interface IssueTypeRecord {
  id: string;
  name: string;
  normalized_name: string;
  enabled: boolean;
  merged_into_id?: string | null;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
  updated_by?: string | null;
  eval_count?: number;
  issue_count?: number;
}

export interface ResearchFilters {
  from?: string;
  to?: string;
  modelVersion?: string;
  scenario?: string;
  orgGroup?: string;
  orgCompany?: string;
  orgFleet?: string;
  orgLine?: string;
  issueTypeIds?: string[];
  issueTypeMode?: IssueTypeFilterMode;
  severity?: IssueSeverity;
  priority?: IssuePriority;
  status?: IssueStatus;
  assignee?: string;
  conclusion?: EvalConclusion;
  isRead?: boolean;
  isFavorite?: boolean;
  keyword?: string;
}

export const VALID_EVAL_CONCLUSIONS: EvalConclusion[] = ['pass', 'warning', 'fail'];
export const VALID_ISSUE_SEVERITIES: IssueSeverity[] = ['low', 'medium', 'high', 'critical'];
export const VALID_ISSUE_PRIORITIES: IssuePriority[] = ['p0', 'p1', 'p2', 'p3'];
export const VALID_ISSUE_STATUSES: IssueStatus[] = ['pending_confirm', 'in_progress', 'pending_verify', 'closed'];
export const VALID_ISSUE_SUBMIT_MODES: IssueSubmitMode[] = ['quick', 'full'];

export function normalizeEvalConclusion(value: unknown, fallback: EvalConclusion = 'warning'): EvalConclusion {
  return VALID_EVAL_CONCLUSIONS.includes(value as EvalConclusion) ? (value as EvalConclusion) : fallback;
}

export function normalizeIssueSeverity(value: unknown, fallback: IssueSeverity = 'medium'): IssueSeverity {
  return VALID_ISSUE_SEVERITIES.includes(value as IssueSeverity) ? (value as IssueSeverity) : fallback;
}

export function normalizeIssuePriority(value: unknown, fallback: IssuePriority = 'p2'): IssuePriority {
  return VALID_ISSUE_PRIORITIES.includes(value as IssuePriority) ? (value as IssuePriority) : fallback;
}

export function normalizeIssueStatus(value: unknown, fallback: IssueStatus = 'pending_confirm'): IssueStatus {
  return VALID_ISSUE_STATUSES.includes(value as IssueStatus) ? (value as IssueStatus) : fallback;
}

export function normalizeIssueSubmitMode(value: unknown, fallback: IssueSubmitMode = 'quick'): IssueSubmitMode {
  return VALID_ISSUE_SUBMIT_MODES.includes(value as IssueSubmitMode) ? (value as IssueSubmitMode) : fallback;
}

export function normalizeEvalSource(value: unknown, fallback: EvalSource = 'research'): EvalSource {
  return value === 'assistant' || value === 'research' ? value : fallback;
}

function parseBooleanQuery(value: string | null): boolean | undefined {
  if (value === null) return undefined;
  if (value === '1' || value.toLowerCase() === 'true') return true;
  if (value === '0' || value.toLowerCase() === 'false') return false;
  return undefined;
}

function parseNumberQuery(value: string | null): number | undefined {
  if (value === null) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function parseIssueTypeFilterMode(
  value: unknown,
  fallback: IssueTypeFilterMode = 'any'
): IssueTypeFilterMode {
  return value === 'all' || value === 'any' ? value : fallback;
}

export function parseResearchFilters(url: URL): ResearchFilters {
  const modelVersion = url.searchParams.get('modelVersion')?.trim();
  const scenario = url.searchParams.get('scenario')?.trim();
  const orgGroup = url.searchParams.get('orgGroup')?.trim();
  const orgCompany = url.searchParams.get('orgCompany')?.trim();
  const orgFleet = url.searchParams.get('orgFleet')?.trim();
  const orgLine = url.searchParams.get('orgLine')?.trim();
  const legacyIssueType = url.searchParams.get('issueType')?.trim();
  const issueTypeIds = Array.from(
    new Set(
      [
        ...url.searchParams
          .getAll('issueTypeIds')
          .flatMap((value) => value.split(','))
          .map((value) => value.trim())
          .filter(Boolean),
        ...url.searchParams
          .getAll('issueTypeId')
          .flatMap((value) => value.split(','))
          .map((value) => value.trim())
          .filter(Boolean),
      ]
    )
  );
  const assignee = url.searchParams.get('assignee')?.trim();
  const keyword = url.searchParams.get('keyword')?.trim();
  const conclusionRaw = url.searchParams.get('conclusion');
  const severityRaw = url.searchParams.get('severity');
  const priorityRaw = url.searchParams.get('priority');
  const statusRaw = url.searchParams.get('status');
  const issueTypeModeRaw = url.searchParams.get('issueTypeMode');
  const issueTypeMode: IssueTypeFilterMode = issueTypeModeRaw === 'all' ? 'all' : 'any';

  return {
    from: url.searchParams.get('from') ?? undefined,
    to: url.searchParams.get('to') ?? undefined,
    modelVersion: modelVersion || undefined,
    scenario: scenario || undefined,
    orgGroup: orgGroup || undefined,
    orgCompany: orgCompany || undefined,
    orgFleet: orgFleet || undefined,
    orgLine: orgLine || undefined,
    issueTypeIds:
      issueTypeIds.length > 0
        ? issueTypeIds
        : legacyIssueType
        ? [legacyIssueType]
        : undefined,
    issueTypeMode,
    severity: severityRaw ? normalizeIssueSeverity(severityRaw) : undefined,
    priority: priorityRaw ? normalizeIssuePriority(priorityRaw) : undefined,
    status: statusRaw ? normalizeIssueStatus(statusRaw) : undefined,
    assignee: assignee || undefined,
    conclusion: conclusionRaw ? normalizeEvalConclusion(conclusionRaw) : undefined,
    isRead: parseBooleanQuery(url.searchParams.get('isRead')),
    isFavorite: parseBooleanQuery(url.searchParams.get('isFavorite')),
    keyword: keyword || undefined,
  };
}

export function parsePagination(url: URL): { page: number; pageSize: number } {
  const pageRaw = parseNumberQuery(url.searchParams.get('page'));
  const pageSizeRaw = parseNumberQuery(url.searchParams.get('pageSize'));
  const page = Math.max(1, Math.floor(pageRaw ?? 1));
  const pageSize = Math.min(MAX_PAGE_SIZE, Math.max(1, Math.floor(pageSizeRaw ?? DEFAULT_PAGE_SIZE)));
  return { page, pageSize };
}

export function buildResearchEvalWhereClause(
  filters: ResearchFilters,
  alias = 'e',
  ownerId?: string
): { clause: string; params: unknown[] } {
  const conditions: string[] = [];
  const params: unknown[] = [];
  if (filters.from) {
    conditions.push(`${alias}.created_at >= ?`);
    params.push(filters.from);
  }
  if (filters.to) {
    conditions.push(`${alias}.created_at <= ?`);
    params.push(filters.to);
  }
  if (filters.modelVersion) {
    conditions.push(`${alias}.model_version = ?`);
    params.push(filters.modelVersion);
  }
  if (filters.scenario) {
    conditions.push(`${alias}.scenario = ?`);
    params.push(filters.scenario);
  }
  if (filters.orgGroup) {
    conditions.push(`${alias}.org_group = ?`);
    params.push(filters.orgGroup);
  }
  if (filters.orgCompany) {
    conditions.push(`${alias}.org_company = ?`);
    params.push(filters.orgCompany);
  }
  if (filters.orgFleet) {
    conditions.push(`${alias}.org_fleet = ?`);
    params.push(filters.orgFleet);
  }
  if (filters.orgLine) {
    conditions.push(`${alias}.org_line = ?`);
    params.push(filters.orgLine);
  }
  if (filters.issueTypeIds && filters.issueTypeIds.length > 0) {
    const placeholders = filters.issueTypeIds.map(() => '?').join(', ');
    if (filters.issueTypeMode === 'all') {
      conditions.push(
        `${alias}.id IN (
          SELECT eit.eval_id
          FROM agent_eval_issue_types eit
          WHERE eit.issue_type_id IN (${placeholders})
          GROUP BY eit.eval_id
          HAVING COUNT(DISTINCT eit.issue_type_id) = ?
        )`
      );
      params.push(...filters.issueTypeIds, filters.issueTypeIds.length);
    } else {
      conditions.push(
        `${alias}.id IN (
          SELECT DISTINCT eit.eval_id
          FROM agent_eval_issue_types eit
          WHERE eit.issue_type_id IN (${placeholders})
        )`
      );
      params.push(...filters.issueTypeIds);
    }
  }
  if (filters.conclusion) {
    conditions.push(`${alias}.conclusion = ?`);
    params.push(filters.conclusion);
  }
  if (typeof filters.isRead === 'boolean') {
    conditions.push(`${alias}.is_read = ?`);
    params.push(filters.isRead ? 1 : 0);
  }
  if (typeof filters.isFavorite === 'boolean') {
    conditions.push(`${alias}.is_favorite = ?`);
    params.push(filters.isFavorite ? 1 : 0);
  }
  if (filters.keyword) {
    conditions.push(`(${alias}.note LIKE ? OR ${alias}.session_id LIKE ?)`);
    params.push(`%${filters.keyword}%`, `%${filters.keyword}%`);
  }
  if (ownerId) {
    conditions.push(
      `EXISTS (SELECT 1 FROM agent_sessions auth_session WHERE auth_session.id = ${alias}.session_id AND auth_session.owner_id = ?)`
    );
    params.push(ownerId);
  }
  return {
    clause: conditions.length ? `WHERE ${conditions.join(' AND ')}` : '',
    params,
  };
}

export function buildResearchIssueWhereClause(
  filters: ResearchFilters,
  alias = 'i',
  ownerId?: string
): { clause: string; params: unknown[] } {
  const conditions: string[] = [];
  const params: unknown[] = [];
  if (filters.from) {
    conditions.push(`${alias}.created_at >= ?`);
    params.push(filters.from);
  }
  if (filters.to) {
    conditions.push(`${alias}.created_at <= ?`);
    params.push(filters.to);
  }
  if (filters.modelVersion) {
    conditions.push(`${alias}.model_version = ?`);
    params.push(filters.modelVersion);
  }
  if (filters.scenario) {
    conditions.push(`${alias}.scenario = ?`);
    params.push(filters.scenario);
  }
  if (filters.orgGroup) {
    conditions.push(`${alias}.org_group = ?`);
    params.push(filters.orgGroup);
  }
  if (filters.orgCompany) {
    conditions.push(`${alias}.org_company = ?`);
    params.push(filters.orgCompany);
  }
  if (filters.orgFleet) {
    conditions.push(`${alias}.org_fleet = ?`);
    params.push(filters.orgFleet);
  }
  if (filters.orgLine) {
    conditions.push(`${alias}.org_line = ?`);
    params.push(filters.orgLine);
  }
  if (filters.issueTypeIds && filters.issueTypeIds.length > 0) {
    const placeholders = filters.issueTypeIds.map(() => '?').join(', ');
    if (filters.issueTypeMode === 'all') {
      conditions.push(
        `${alias}.id IN (
          SELECT iit.issue_id
          FROM agent_issue_issue_types iit
          WHERE iit.issue_type_id IN (${placeholders})
          GROUP BY iit.issue_id
          HAVING COUNT(DISTINCT iit.issue_type_id) = ?
        )`
      );
      params.push(...filters.issueTypeIds, filters.issueTypeIds.length);
    } else {
      conditions.push(
        `${alias}.id IN (
          SELECT DISTINCT iit.issue_id
          FROM agent_issue_issue_types iit
          WHERE iit.issue_type_id IN (${placeholders})
        )`
      );
      params.push(...filters.issueTypeIds);
    }
  }
  if (filters.severity) {
    conditions.push(`${alias}.severity = ?`);
    params.push(filters.severity);
  }
  if (filters.priority) {
    conditions.push(`${alias}.priority = ?`);
    params.push(filters.priority);
  }
  if (filters.status) {
    conditions.push(`${alias}.status = ?`);
    params.push(filters.status);
  }
  if (filters.assignee) {
    conditions.push(`${alias}.assignee = ?`);
    params.push(filters.assignee);
  }
  if (filters.keyword) {
    conditions.push(
      `(${alias}.title LIKE ? OR ${alias}.description LIKE ? OR ${alias}.context_summary LIKE ? OR ${alias}.session_id LIKE ?)`
    );
    params.push(`%${filters.keyword}%`, `%${filters.keyword}%`, `%${filters.keyword}%`, `%${filters.keyword}%`);
  }
  if (ownerId) {
    conditions.push(
      `EXISTS (SELECT 1 FROM agent_sessions auth_session WHERE auth_session.id = ${alias}.session_id AND auth_session.owner_id = ?)`
    );
    params.push(ownerId);
  }
  return {
    clause: conditions.length ? `WHERE ${conditions.join(' AND ')}` : '',
    params,
  };
}
