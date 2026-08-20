import type { D1Database } from '../scenarios/repository';
import { safeJsonParse } from '../../shared/json';
import {
  buildResearchEvalWhereClause,
  buildResearchIssueWhereClause,
  normalizeEvalConclusion,
  normalizeEvalSource,
  normalizeIssuePriority,
  normalizeIssueSeverity,
  normalizeIssueStatus,
  normalizeIssueSubmitMode,
  parseIssueTypeFilterMode,
  type EvalConclusion,
  type EvalRecord,
  type EvalSource,
  type IssueEventRecord,
  type IssueOperationComment,
  type IssuePriority,
  type IssueRecord,
  type IssueSeverity,
  type IssueStatus,
  type IssueSubmitMode,
  type IssueTypeRecord,
  type IssueTypeRef,
  type ResearchFilters,
  VALID_EVAL_CONCLUSIONS,
  VALID_ISSUE_PRIORITIES,
  VALID_ISSUE_SEVERITIES,
  VALID_ISSUE_STATUSES,
  VALID_ISSUE_SUBMIT_MODES,
} from './filters';

export interface ResearchModelEnvLike {
  OPENAI_MODEL?: string;
  OPENAI_WORKER_MODEL?: string;
}

function createResearchId(prefix: string): string {
  return `${prefix}_${crypto.randomUUID()}`;
}

function parseStringArrayField(value?: string | null): string[] {
  if (!value) return [];
  const parsed = safeJsonParse(value);
  if (!Array.isArray(parsed)) return [];
  return parsed.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function parseObjectField(value?: string | null): Record<string, unknown> | null {
  if (!value) return null;
  const parsed = safeJsonParse(value);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return null;
  }
  return parsed as Record<string, unknown>;
}

function formatUtc8DateTime(value: Date): string {
  const formatter = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  return formatter.format(value).replace('T', ' ');
}

function buildIssueTitle(rawTitle: unknown, at: Date = new Date()): string {
  const base = formatUtc8DateTime(at);
  const suffix = typeof rawTitle === 'string' ? rawTitle.trim() : '';
  return suffix ? `${base} ${suffix}` : base;
}

function parseEvalRow(row: Record<string, unknown>): EvalRecord {
  const issueTypesRaw = safeJsonParse(String(row.issue_types_json ?? '[]'));
  const issueTypes = Array.isArray(issueTypesRaw)
    ? issueTypesRaw
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
        .map((item) => ({
          id: String(item.id ?? '').trim(),
          name: String(item.name ?? '').trim(),
        }))
        .filter((item) => item.id.length > 0 && item.name.length > 0)
    : [];
  return {
    id: String(row.id ?? ''),
    session_id: String(row.session_id ?? ''),
    conclusion: normalizeEvalConclusion(row.conclusion, 'warning'),
    issue_types: issueTypes,
    confidence: row.confidence === null || row.confidence === undefined ? null : Number(row.confidence),
    note: row.note ? String(row.note) : null,
    tags: parseStringArrayField((row.tags_json as string | null) ?? null),
    model_version: row.model_version ? String(row.model_version) : null,
    scenario: row.scenario ? String(row.scenario) : null,
    org_group: row.org_group ? String(row.org_group) : null,
    org_company: row.org_company ? String(row.org_company) : null,
    org_fleet: row.org_fleet ? String(row.org_fleet) : null,
    org_line: row.org_line ? String(row.org_line) : null,
    referenced_message_ids: parseStringArrayField((row.referenced_message_ids_json as string | null) ?? null),
    is_read: Number(row.is_read ?? 0) === 1,
    is_favorite: Number(row.is_favorite ?? 0) === 1,
    source: normalizeEvalSource(row.source, 'research'),
    created_at: String(row.created_at ?? ''),
    updated_at: String(row.updated_at ?? ''),
  };
}

function parseIssueRow(row: Record<string, unknown>): IssueRecord {
  const issueTypesRaw = safeJsonParse(String(row.issue_types_json ?? '[]'));
  const issueTypes = Array.isArray(issueTypesRaw)
    ? issueTypesRaw
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
        .map((item) => ({
          id: String(item.id ?? '').trim(),
          name: String(item.name ?? '').trim(),
        }))
        .filter((item) => item.id.length > 0 && item.name.length > 0)
    : [];
  return {
    id: String(row.id ?? ''),
    title: String(row.title ?? ''),
    issue_types: issueTypes,
    severity: normalizeIssueSeverity(row.severity, 'medium'),
    priority: normalizeIssuePriority(row.priority, 'p2'),
    status: normalizeIssueStatus(row.status, 'pending_confirm'),
    description: String(row.description ?? ''),
    expected_result: row.expected_result ? String(row.expected_result) : null,
    business_impact: row.business_impact ? String(row.business_impact) : null,
    repro_steps: row.repro_steps ? String(row.repro_steps) : null,
    session_id: String(row.session_id ?? ''),
    source_eval_id: row.source_eval_id ? String(row.source_eval_id) : null,
    referenced_message_ids: parseStringArrayField((row.referenced_message_ids_json as string | null) ?? null),
    context_summary: row.context_summary ? String(row.context_summary) : null,
    model_version: row.model_version ? String(row.model_version) : null,
    scenario: row.scenario ? String(row.scenario) : null,
    org_group: row.org_group ? String(row.org_group) : null,
    org_company: row.org_company ? String(row.org_company) : null,
    org_fleet: row.org_fleet ? String(row.org_fleet) : null,
    org_line: row.org_line ? String(row.org_line) : null,
    assignee: row.assignee ? String(row.assignee) : null,
    due_at: row.due_at ? String(row.due_at) : null,
    submit_mode: normalizeIssueSubmitMode(row.submit_mode, 'quick'),
    source_metric: parseObjectField((row.source_metric_json as string | null) ?? null),
    created_by: row.created_by ? String(row.created_by) : null,
    updated_by: row.updated_by ? String(row.updated_by) : null,
    created_at: String(row.created_at ?? ''),
    updated_at: String(row.updated_at ?? ''),
    closed_at: row.closed_at ? String(row.closed_at) : null,
  };
}

function parseIssueEventRow(row: Record<string, unknown>): IssueEventRecord {
  return {
    id: String(row.id ?? ''),
    issue_id: String(row.issue_id ?? ''),
    action: String(row.action ?? ''),
    from_status: row.from_status ? String(row.from_status) : null,
    to_status: row.to_status ? String(row.to_status) : null,
    note: row.note ? String(row.note) : null,
    operator: row.operator ? String(row.operator) : null,
    metadata: parseObjectField((row.metadata_json as string | null) ?? null),
    created_at: String(row.created_at ?? ''),
  };
}

function normalizeIssueOperationComment(value: unknown): IssueOperationComment | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const handlingType = typeof record.handling_type === 'string' ? record.handling_type.trim() : '';
  const description = typeof record.description === 'string' ? record.description.trim() : '';
  const commitId = typeof record.commit_id === 'string' ? record.commit_id.trim() : '';

  if (!handlingType && !description && !commitId) return null;

  return {
    handling_type: handlingType,
    description,
    commit_id: commitId,
  };
}

function assertIssueInProgressComment(status: IssueStatus, comment: IssueOperationComment | null): void {
  if (status !== 'in_progress') return;
  if (!comment || !comment.handling_type || !comment.description || !comment.commit_id) {
    throw new Error('in_progress comment requires handling_type, description, and commit_id');
  }
}

function buildIssueCommentNote(comment: IssueOperationComment | null): string | null {
  if (!comment) return null;
  return `handling_type: ${comment.handling_type}\ncommit_id: ${comment.commit_id}\ndescription: ${comment.description}`;
}

function normalizeIssueTypeName(value: unknown): { name: string; normalized_name: string } | null {
  if (typeof value !== 'string') return null;
  const name = value
    .normalize('NFKC')
    .replace(/\s+/g, ' ')
    .trim();
  if (!name) return null;
  return {
    name,
    normalized_name: name.toLocaleLowerCase(),
  };
}

function parseIssueTypeRow(row: Record<string, unknown>): IssueTypeRecord {
  return {
    id: String(row.id ?? ''),
    name: String(row.name ?? ''),
    normalized_name: String(row.normalized_name ?? ''),
    enabled: Number(row.enabled ?? 1) === 1,
    merged_into_id: row.merged_into_id ? String(row.merged_into_id) : null,
    created_at: String(row.created_at ?? ''),
    updated_at: String(row.updated_at ?? ''),
    created_by: row.created_by ? String(row.created_by) : null,
    updated_by: row.updated_by ? String(row.updated_by) : null,
    eval_count: row.eval_count === undefined ? undefined : Number(row.eval_count ?? 0),
    issue_count: row.issue_count === undefined ? undefined : Number(row.issue_count ?? 0),
  };
}

async function getIssueTypeById(db: D1Database, id: string): Promise<IssueTypeRecord | null> {
  const row = await db.prepare('SELECT * FROM agent_issue_types WHERE id = ?').bind(id).first<Record<string, unknown>>();
  return row ? parseIssueTypeRow(row) : null;
}

async function getIssueTypeByNormalizedName(db: D1Database, normalizedName: string): Promise<IssueTypeRecord | null> {
  const row = await db
    .prepare('SELECT * FROM agent_issue_types WHERE normalized_name = ?')
    .bind(normalizedName)
    .first<Record<string, unknown>>();
  return row ? parseIssueTypeRow(row) : null;
}

async function resolveMergedIssueTypeId(
  db: D1Database,
  issueTypeId: string
): Promise<{ id: string; redirects: Array<{ from: string; to: string }> }> {
  let current = issueTypeId;
  const redirects: Array<{ from: string; to: string }> = [];
  const visited = new Set<string>();

  while (current && !visited.has(current)) {
    visited.add(current);
    const row = await db
      .prepare('SELECT id, merged_into_id FROM agent_issue_types WHERE id = ?')
      .bind(current)
      .first<{ id: string; merged_into_id: string | null }>();
    if (!row) {
      break;
    }
    if (!row.merged_into_id || row.merged_into_id === row.id) {
      return { id: row.id, redirects };
    }
    redirects.push({ from: row.id, to: row.merged_into_id });
    current = row.merged_into_id;
  }

  return { id: issueTypeId, redirects };
}

async function resolveIssueTypeIds(
  db: D1Database,
  issueTypeIds: string[]
): Promise<{ ids: string[]; redirects: Array<{ from: string; to: string }> }> {
  const nextIds = new Set<string>();
  const redirects: Array<{ from: string; to: string }> = [];

  for (const rawId of issueTypeIds) {
    const input = rawId.trim();
    if (!input) continue;
    let id = input;
    const typeById = await getIssueTypeById(db, input);
    if (!typeById) {
      const normalized = normalizeIssueTypeName(input);
      if (!normalized) continue;
      const typeByName = await getIssueTypeByNormalizedName(db, normalized.normalized_name);
      if (!typeByName) continue;
      id = typeByName.id;
    }

    const resolved = await resolveMergedIssueTypeId(db, id);
    nextIds.add(resolved.id);
    redirects.push(...resolved.redirects);
  }

  return {
    ids: Array.from(nextIds),
    redirects,
  };
}

export async function ensureIssueTypeByName(
  db: D1Database,
  nameInput: string,
  operator?: string
): Promise<IssueTypeRecord | null> {
  const normalized = normalizeIssueTypeName(nameInput);
  if (!normalized) return null;

  const existing = await getIssueTypeByNormalizedName(db, normalized.normalized_name);
  if (existing) {
    const resolved = await resolveMergedIssueTypeId(db, existing.id);
    return getIssueTypeById(db, resolved.id);
  }

  const now = new Date().toISOString();
  const id = createResearchId('issue_type');
  try {
    await db
      .prepare(
        'INSERT INTO agent_issue_types (id, name, normalized_name, enabled, merged_into_id, created_at, updated_at, created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
      )
      .bind(id, normalized.name, normalized.normalized_name, 1, null, now, now, operator ?? null, operator ?? null)
      .run();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error ?? '');
    if (/unique|constraint/i.test(message)) {
      const existingAfterRace = await getIssueTypeByNormalizedName(db, normalized.normalized_name);
      if (existingAfterRace) {
        const resolved = await resolveMergedIssueTypeId(db, existingAfterRace.id);
        return getIssueTypeById(db, resolved.id);
      }
    }
    throw error;
  }

  return getIssueTypeById(db, id);
}

async function resolveIssueTypeIdsForWrite(
  db: D1Database,
  issueTypeIdsInput?: string[],
  newIssueTypeNames?: string[],
  operator?: string
): Promise<{ ids: string[]; redirects: Array<{ from: string; to: string }> }> {
  const directIds = Array.isArray(issueTypeIdsInput)
    ? issueTypeIdsInput.map((value) => value.trim()).filter(Boolean)
    : [];
  const createdIds: string[] = [];

  if (Array.isArray(newIssueTypeNames)) {
    for (const name of newIssueTypeNames) {
      const created = await ensureIssueTypeByName(db, name, operator);
      if (created) {
        createdIds.push(created.id);
      }
    }
  }

  const resolved = await resolveIssueTypeIds(db, [...directIds, ...createdIds]);
  return {
    ids: Array.from(new Set(resolved.ids)),
    redirects: resolved.redirects,
  };
}

export async function listIssueTypes(
  db: D1Database,
  options?: {
    includeDisabled?: boolean;
    includeMerged?: boolean;
    keyword?: string;
  }
): Promise<IssueTypeRecord[]> {
  const includeDisabled = options?.includeDisabled === true;
  const includeMerged = options?.includeMerged === true;
  const keyword = options?.keyword?.trim();

  const conditions: string[] = [];
  const params: unknown[] = [];
  if (!includeDisabled) {
    conditions.push('t.enabled = 1');
  }
  if (!includeMerged) {
    conditions.push('t.merged_into_id IS NULL');
  }
  if (keyword) {
    conditions.push('(t.name LIKE ? OR t.normalized_name LIKE ?)');
    params.push(`%${keyword}%`, `%${keyword.toLocaleLowerCase()}%`);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  const sql = `
    SELECT t.*,
      (SELECT COUNT(*) FROM agent_eval_issue_types eit WHERE eit.issue_type_id = t.id) AS eval_count,
      (SELECT COUNT(*) FROM agent_issue_issue_types iit WHERE iit.issue_type_id = t.id) AS issue_count
    FROM agent_issue_types t
    ${where}
    ORDER BY t.enabled DESC, t.name COLLATE NOCASE ASC
  `;
  const rows = await db.prepare(sql).bind(...params).all<Record<string, unknown>>();
  return rows.results.map(parseIssueTypeRow);
}

export async function updateIssueTypeRecord(
  db: D1Database,
  id: string,
  payload: Partial<{
    name: string;
    enabled: boolean;
    updated_by: string;
  }>
): Promise<IssueTypeRecord | null> {
  const existing = await getIssueTypeById(db, id);
  if (!existing) return null;
  if (existing.merged_into_id) return existing;

  const now = new Date().toISOString();
  let nextName = existing.name;
  let nextNormalized = existing.normalized_name;
  if (payload.name !== undefined) {
    const normalized = normalizeIssueTypeName(payload.name);
    if (!normalized) {
      throw new Error('invalid issue type name');
    }
    if (normalized.normalized_name !== existing.normalized_name) {
      const conflict = await getIssueTypeByNormalizedName(db, normalized.normalized_name);
      if (conflict && conflict.id !== id) {
        throw new Error('issue type name already exists');
      }
    }
    nextName = normalized.name;
    nextNormalized = normalized.normalized_name;
  }

  const nextEnabled = payload.enabled === undefined ? existing.enabled : payload.enabled;
  await db
    .prepare(
      'UPDATE agent_issue_types SET name = ?, normalized_name = ?, enabled = ?, updated_at = ?, updated_by = ? WHERE id = ?'
    )
    .bind(nextName, nextNormalized, nextEnabled ? 1 : 0, now, payload.updated_by?.trim() || null, id)
    .run();

  return getIssueTypeById(db, id);
}

export async function mergeIssueTypes(
  db: D1Database,
  payload: {
    target_type_id: string;
    source_type_ids: string[];
    operator?: string;
    note?: string;
  }
): Promise<{
  target_type_id: string;
  merged: Array<{ source_type_id: string; affected_eval_count: number; affected_issue_count: number }>;
}> {
  const targetResolved = await resolveMergedIssueTypeId(db, payload.target_type_id);
  const targetType = await getIssueTypeById(db, targetResolved.id);
  if (!targetType) {
    throw new Error('target issue type not found');
  }
  if (!targetType.enabled) {
    throw new Error('target issue type is disabled');
  }

  const resolvedSources = await resolveIssueTypeIds(db, payload.source_type_ids);
  const sourceIds = Array.from(new Set(resolvedSources.ids)).filter((value) => value !== targetType.id);
  const merged: Array<{ source_type_id: string; affected_eval_count: number; affected_issue_count: number }> = [];
  const now = new Date().toISOString();

  if (!sourceIds.length) {
    return {
      target_type_id: targetType.id,
      merged,
    };
  }

  await db.prepare('BEGIN').run();
  let committed = false;
  try {
    for (const sourceId of sourceIds) {
      const sourceType = await getIssueTypeById(db, sourceId);
      if (!sourceType || sourceType.id === targetType.id) {
        continue;
      }

      const evalCountRow = await db
        .prepare('SELECT COUNT(DISTINCT eval_id) AS count FROM agent_eval_issue_types WHERE issue_type_id = ?')
        .bind(sourceId)
        .first<{ count: number | string }>();
      const issueCountRow = await db
        .prepare('SELECT COUNT(DISTINCT issue_id) AS count FROM agent_issue_issue_types WHERE issue_type_id = ?')
        .bind(sourceId)
        .first<{ count: number | string }>();
      const affectedEvalCount = Number(evalCountRow?.count ?? 0);
      const affectedIssueCount = Number(issueCountRow?.count ?? 0);

      await db
        .prepare(
          'INSERT OR IGNORE INTO agent_eval_issue_types (eval_id, issue_type_id, created_at) SELECT eval_id, ?, ? FROM agent_eval_issue_types WHERE issue_type_id = ?'
        )
        .bind(targetType.id, now, sourceId)
        .run();
      await db.prepare('DELETE FROM agent_eval_issue_types WHERE issue_type_id = ?').bind(sourceId).run();

      await db
        .prepare(
          'INSERT OR IGNORE INTO agent_issue_issue_types (issue_id, issue_type_id, created_at) SELECT issue_id, ?, ? FROM agent_issue_issue_types WHERE issue_type_id = ?'
        )
        .bind(targetType.id, now, sourceId)
        .run();
      await db.prepare('DELETE FROM agent_issue_issue_types WHERE issue_type_id = ?').bind(sourceId).run();

      await db
        .prepare('UPDATE agent_issue_types SET enabled = 0, merged_into_id = ?, updated_at = ?, updated_by = ? WHERE id = ?')
        .bind(targetType.id, now, payload.operator?.trim() || null, sourceId)
        .run();

      await db
        .prepare(
          'INSERT INTO agent_issue_type_merges (id, target_type_id, source_type_id, affected_eval_count, affected_issue_count, operator, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        )
        .bind(
          createResearchId('issue_type_merge'),
          targetType.id,
          sourceId,
          affectedEvalCount,
          affectedIssueCount,
          payload.operator?.trim() || null,
          payload.note?.trim() || null,
          now
        )
        .run();

      merged.push({
        source_type_id: sourceId,
        affected_eval_count: affectedEvalCount,
        affected_issue_count: affectedIssueCount,
      });
    }

    await db.prepare('COMMIT').run();
    committed = true;
  } catch (error) {
    if (!committed) {
      try {
        await db.prepare('ROLLBACK').run();
      } catch {
        // Ignore rollback failures and return the original error.
      }
    }
    throw error;
  }

  return {
    target_type_id: targetType.id,
    merged,
  };
}

async function assignEvalIssueTypes(
  db: D1Database,
  evalId: string,
  issueTypeIds: string[],
  replace = false
): Promise<void> {
  if (replace) {
    await db.prepare('DELETE FROM agent_eval_issue_types WHERE eval_id = ?').bind(evalId).run();
  }
  if (!issueTypeIds.length) return;
  const now = new Date().toISOString();
  for (const issueTypeId of issueTypeIds) {
    await db
      .prepare('INSERT OR IGNORE INTO agent_eval_issue_types (eval_id, issue_type_id, created_at) VALUES (?, ?, ?)')
      .bind(evalId, issueTypeId, now)
      .run();
  }
}

async function assignIssueIssueTypes(
  db: D1Database,
  issueId: string,
  issueTypeIds: string[],
  replace = false
): Promise<void> {
  if (replace) {
    await db.prepare('DELETE FROM agent_issue_issue_types WHERE issue_id = ?').bind(issueId).run();
  }
  if (!issueTypeIds.length) return;
  const now = new Date().toISOString();
  for (const issueTypeId of issueTypeIds) {
    await db
      .prepare('INSERT OR IGNORE INTO agent_issue_issue_types (issue_id, issue_type_id, created_at) VALUES (?, ?, ?)')
      .bind(issueId, issueTypeId, now)
      .run();
  }
}

async function loadEvalIssueTypeMap(db: D1Database, evalIds: string[]): Promise<Map<string, IssueTypeRef[]>> {
  const map = new Map<string, IssueTypeRef[]>();
  if (!evalIds.length) return map;
  const placeholders = evalIds.map(() => '?').join(', ');
  const sql = `
    SELECT eit.eval_id, t.id AS issue_type_id, t.name AS issue_type_name
    FROM agent_eval_issue_types eit
    JOIN agent_issue_types t ON t.id = eit.issue_type_id
    WHERE eit.eval_id IN (${placeholders})
    ORDER BY t.name COLLATE NOCASE ASC
  `;
  const rows = await db.prepare(sql).bind(...evalIds).all<Record<string, unknown>>();
  rows.results.forEach((row) => {
    const evalId = String(row.eval_id ?? '');
    const existing = map.get(evalId) ?? [];
    const typeId = String(row.issue_type_id ?? '').trim();
    const typeName = String(row.issue_type_name ?? '').trim();
    if (typeId && typeName) {
      existing.push({ id: typeId, name: typeName });
      map.set(evalId, existing);
    }
  });
  return map;
}

async function loadIssueIssueTypeMap(db: D1Database, issueIds: string[]): Promise<Map<string, IssueTypeRef[]>> {
  const map = new Map<string, IssueTypeRef[]>();
  if (!issueIds.length) return map;
  const placeholders = issueIds.map(() => '?').join(', ');
  const sql = `
    SELECT iit.issue_id, t.id AS issue_type_id, t.name AS issue_type_name
    FROM agent_issue_issue_types iit
    JOIN agent_issue_types t ON t.id = iit.issue_type_id
    WHERE iit.issue_id IN (${placeholders})
    ORDER BY t.name COLLATE NOCASE ASC
  `;
  const rows = await db.prepare(sql).bind(...issueIds).all<Record<string, unknown>>();
  rows.results.forEach((row) => {
    const issueId = String(row.issue_id ?? '');
    const existing = map.get(issueId) ?? [];
    const typeId = String(row.issue_type_id ?? '').trim();
    const typeName = String(row.issue_type_name ?? '').trim();
    if (typeId && typeName) {
      existing.push({ id: typeId, name: typeName });
      map.set(issueId, existing);
    }
  });
  return map;
}

async function listIssueTypeRefsByIds(db: D1Database, issueTypeIds: string[]): Promise<IssueTypeRef[]> {
  if (!issueTypeIds.length) return [];
  const placeholders = issueTypeIds.map(() => '?').join(', ');
  const rows = await db
    .prepare(`SELECT id, name FROM agent_issue_types WHERE id IN (${placeholders}) ORDER BY name COLLATE NOCASE ASC`)
    .bind(...issueTypeIds)
    .all<{ id: string; name: string }>();
  return rows.results
    .map((row) => ({ id: String(row.id ?? '').trim(), name: String(row.name ?? '').trim() }))
    .filter((row) => row.id && row.name);
}

export async function resolveResearchFilterIssueTypes(
  db: D1Database,
  filters: ResearchFilters
): Promise<{ filters: ResearchFilters; issue_type_redirects: Array<{ from: string; to: string }> }> {
  if (!filters.issueTypeIds || filters.issueTypeIds.length === 0) {
    return {
      filters: {
        ...filters,
        issueTypeMode: parseIssueTypeFilterMode(filters.issueTypeMode, 'any'),
      },
      issue_type_redirects: [],
    };
  }
  const resolved = await resolveIssueTypeIds(db, filters.issueTypeIds);
  return {
    filters: {
      ...filters,
      issueTypeIds: resolved.ids,
      issueTypeMode: parseIssueTypeFilterMode(filters.issueTypeMode, 'any'),
    },
    issue_type_redirects: resolved.redirects,
  };
}

async function getSessionModelVersion(
  db: D1Database,
  env: ResearchModelEnvLike,
  sessionId: string,
  requested?: string | null
): Promise<string> {
  const direct = (requested || '').trim();
  if (direct) return direct;

  const row = await db
    .prepare('SELECT metadata FROM agent_messages WHERE session_id = ? AND role = ? ORDER BY created_at DESC LIMIT 1')
    .bind(sessionId, 'assistant')
    .first<{ metadata: string | null }>();

  if (row?.metadata) {
    const parsed = safeJsonParse(row.metadata);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      const record = parsed as Record<string, unknown>;
      const abTest = record.ab_test as Record<string, unknown> | undefined;
      const candidates = [record.model_version, record.model, abTest?.model_version, abTest?.model];
      const hit = candidates.find((candidate) => typeof candidate === 'string' && candidate.trim().length > 0);
      if (typeof hit === 'string') {
        return hit.trim();
      }
    }
  }
  return env.OPENAI_WORKER_MODEL || env.OPENAI_MODEL || 'gpt-4o-mini';
}

export async function getEvalRecordById(db: D1Database, id: string, ownerId?: string): Promise<EvalRecord | null> {
  const sql = ownerId
    ? 'SELECT e.*, ? AS issue_types_json FROM agent_eval_records e JOIN agent_sessions s ON s.id = e.session_id WHERE e.id = ? AND s.owner_id = ?'
    : 'SELECT e.*, ? AS issue_types_json FROM agent_eval_records e WHERE e.id = ?';
  const row = await db
    .prepare(sql)
    .bind('[]', id, ...(ownerId ? [ownerId] : []))
    .first<Record<string, unknown>>();
  if (!row) return null;
  const record = parseEvalRow(row);
  const issueTypeMap = await loadEvalIssueTypeMap(db, [id]);
  record.issue_types = issueTypeMap.get(id) ?? [];
  return record;
}

export async function getIssueRecordById(db: D1Database, id: string, ownerId?: string): Promise<IssueRecord | null> {
  const sql = ownerId
    ? 'SELECT i.*, ? AS issue_types_json FROM agent_issues i JOIN agent_sessions s ON s.id = i.session_id WHERE i.id = ? AND s.owner_id = ?'
    : 'SELECT i.*, ? AS issue_types_json FROM agent_issues i WHERE i.id = ?';
  const row = await db
    .prepare(sql)
    .bind('[]', id, ...(ownerId ? [ownerId] : []))
    .first<Record<string, unknown>>();
  if (!row) return null;
  const record = parseIssueRow(row);
  const issueTypeMap = await loadIssueIssueTypeMap(db, [id]);
  record.issue_types = issueTypeMap.get(id) ?? [];
  return record;
}

export async function listIssueEventsByIssueId(db: D1Database, issueId: string): Promise<IssueEventRecord[]> {
  const result = await db
    .prepare('SELECT * FROM agent_issue_events WHERE issue_id = ? ORDER BY created_at ASC')
    .bind(issueId)
    .all<Record<string, unknown>>();
  return result.results.map(parseIssueEventRow);
}

async function createIssueEvent(
  db: D1Database,
  input: {
    issue_id: string;
    action: string;
    from_status?: string | null;
    to_status?: string | null;
    note?: string | null;
    operator?: string | null;
    metadata?: Record<string, unknown> | null;
  }
): Promise<IssueEventRecord> {
  const now = new Date().toISOString();
  const record: IssueEventRecord = {
    id: createResearchId('issue_event'),
    issue_id: input.issue_id,
    action: input.action,
    from_status: input.from_status ?? null,
    to_status: input.to_status ?? null,
    note: input.note ?? null,
    operator: input.operator ?? null,
    metadata: input.metadata ?? null,
    created_at: now,
  };
  await db
    .prepare(
      'INSERT INTO agent_issue_events (id, issue_id, action, from_status, to_status, note, operator, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .bind(
      record.id,
      record.issue_id,
      record.action,
      record.from_status,
      record.to_status,
      record.note,
      record.operator,
      record.metadata ? JSON.stringify(record.metadata) : null,
      record.created_at
    )
    .run();
  return record;
}

export async function listResearchEvals(
  db: D1Database,
  filters: ResearchFilters,
  page: number,
  pageSize: number,
  sortBy?: string,
  sortOrder?: string,
  ownerId?: string
): Promise<{ items: Array<EvalRecord & Record<string, unknown>>; total: number; page: number; pageSize: number }> {
  const { clause, params } = buildResearchEvalWhereClause(filters, 'e', ownerId);
  const orderFieldMap: Record<string, string> = {
    created_at: 'e.created_at',
    updated_at: 'e.updated_at',
    confidence: 'e.confidence',
  };
  const orderField = orderFieldMap[sortBy || ''] || 'e.created_at';
  const orderDirection = String(sortOrder || 'desc').toLowerCase() === 'asc' ? 'ASC' : 'DESC';
  const offset = (page - 1) * pageSize;

  const listSql = `
    SELECT e.*, s.title AS session_title, s.preview AS session_preview,
      ? AS issue_types_json,
      (SELECT COUNT(*) FROM agent_issues i WHERE i.source_eval_id = e.id) AS issue_count
    FROM agent_eval_records e
    LEFT JOIN agent_sessions s ON s.id = e.session_id
    ${clause}
    ORDER BY ${orderField} ${orderDirection}
    LIMIT ? OFFSET ?
  `;
  const listResult = await db
    .prepare(listSql)
    .bind('[]', ...params, pageSize, offset)
    .all<Record<string, unknown>>();

  const countSql = `SELECT COUNT(*) AS total FROM agent_eval_records e ${clause}`;
  const countRow = await db.prepare(countSql).bind(...params).first<{ total: number | string }>();
  const total = Number(countRow?.total ?? 0);

  const items = listResult.results.map((row) => ({
    ...parseEvalRow(row),
    issue_count: Number(row.issue_count ?? 0),
    session_title: row.session_title ? String(row.session_title) : '',
    session_preview: row.session_preview ? String(row.session_preview) : '',
  }));
  const evalIssueTypes = await loadEvalIssueTypeMap(
    db,
    items.map((item) => item.id)
  );
  items.forEach((item) => {
    item.issue_types = evalIssueTypes.get(item.id) ?? [];
  });
  return { items, total, page, pageSize };
}

export async function listResearchIssues(
  db: D1Database,
  filters: ResearchFilters,
  page: number,
  pageSize: number,
  sortBy?: string,
  sortOrder?: string,
  ownerId?: string
): Promise<{
  items: IssueRecord[];
  total: number;
  page: number;
  pageSize: number;
  kanban: Record<IssueStatus, IssueRecord[]>;
  status_counts: Record<IssueStatus, number>;
  severity_distribution: Array<{ severity: IssueSeverity; count: number }>;
  trend: Array<{ date: string; count: number }>;
}> {
  const { clause, params } = buildResearchIssueWhereClause(filters, 'i', ownerId);
  const orderFieldMap: Record<string, string> = {
    created_at: 'i.created_at',
    updated_at: 'i.updated_at',
    due_at: 'i.due_at',
    severity: 'i.severity',
    priority: 'i.priority',
  };
  const orderField = orderFieldMap[sortBy || ''] || 'i.updated_at';
  const orderDirection = String(sortOrder || 'desc').toLowerCase() === 'asc' ? 'ASC' : 'DESC';
  const offset = (page - 1) * pageSize;

  const listSql = `
    SELECT i.*, ? AS issue_types_json
    FROM agent_issues i
    ${clause}
    ORDER BY ${orderField} ${orderDirection}
    LIMIT ? OFFSET ?
  `;
  const listResult = await db
    .prepare(listSql)
    .bind('[]', ...params, pageSize, offset)
    .all<Record<string, unknown>>();
  const items = listResult.results.map(parseIssueRow);
  const issueTypeMap = await loadIssueIssueTypeMap(
    db,
    items.map((item) => item.id)
  );
  items.forEach((item) => {
    item.issue_types = issueTypeMap.get(item.id) ?? [];
  });

  const countSql = `SELECT COUNT(*) AS total FROM agent_issues i ${clause}`;
  const countRow = await db.prepare(countSql).bind(...params).first<{ total: number | string }>();
  const total = Number(countRow?.total ?? 0);

  const statusRows = await db
    .prepare(`SELECT i.status, COUNT(*) AS count FROM agent_issues i ${clause} GROUP BY i.status`)
    .bind(...params)
    .all<{ status: string; count: number | string }>();
  const statusCounts: Record<IssueStatus, number> = {
    pending_confirm: 0,
    in_progress: 0,
    pending_verify: 0,
    closed: 0,
  };
  statusRows.results.forEach((row) => {
    const status = normalizeIssueStatus(row.status, 'pending_confirm');
    statusCounts[status] = Number(row.count ?? 0);
  });

  const severityRows = await db
    .prepare(`SELECT i.severity, COUNT(*) AS count FROM agent_issues i ${clause} GROUP BY i.severity`)
    .bind(...params)
    .all<{ severity: string; count: number | string }>();
  const severityDistribution = severityRows.results.map((row) => ({
    severity: normalizeIssueSeverity(row.severity, 'medium'),
    count: Number(row.count ?? 0),
  }));

  const trendRows = await db
    .prepare(
      `SELECT substr(i.created_at, 1, 10) AS date, COUNT(*) AS count FROM agent_issues i ${clause} GROUP BY substr(i.created_at, 1, 10) ORDER BY date ASC`
    )
    .bind(...params)
    .all<{ date: string; count: number | string }>();
  const trend = trendRows.results.map((row) => ({
    date: String(row.date ?? ''),
    count: Number(row.count ?? 0),
  }));

  const kanbanRows = await db
    .prepare(`SELECT i.*, ? AS issue_types_json FROM agent_issues i ${clause} ORDER BY i.updated_at DESC LIMIT 300`)
    .bind('[]', ...params)
    .all<Record<string, unknown>>();
  const kanban: Record<IssueStatus, IssueRecord[]> = {
    pending_confirm: [],
    in_progress: [],
    pending_verify: [],
    closed: [],
  };
  const kanbanItems = kanbanRows.results.map(parseIssueRow);
  const kanbanIssueTypeMap = await loadIssueIssueTypeMap(
    db,
    kanbanItems.map((item) => item.id)
  );
  kanbanItems.forEach((issue) => {
    issue.issue_types = kanbanIssueTypeMap.get(issue.id) ?? [];
    kanban[issue.status].push(issue);
  });

  return {
    items,
    total,
    page,
    pageSize,
    kanban,
    status_counts: statusCounts,
    severity_distribution: severityDistribution,
    trend,
  };
}

export async function getResearchOptions(db: D1Database, ownerId?: string): Promise<Record<string, unknown>> {
  const evalSql = ownerId
    ? 'SELECT e.model_version, e.scenario, e.org_group, e.org_company, e.org_fleet, e.org_line FROM agent_eval_records e JOIN agent_sessions s ON s.id = e.session_id WHERE s.owner_id = ?'
    : 'SELECT model_version, scenario, org_group, org_company, org_fleet, org_line FROM agent_eval_records';
  const issueSql = ownerId
    ? 'SELECT i.model_version, i.scenario, i.org_group, i.org_company, i.org_fleet, i.org_line, i.assignee FROM agent_issues i JOIN agent_sessions s ON s.id = i.session_id WHERE s.owner_id = ?'
    : 'SELECT model_version, scenario, org_group, org_company, org_fleet, org_line, assignee FROM agent_issues';
  const evalRows = await db.prepare(evalSql).bind(...(ownerId ? [ownerId] : [])).all<Record<string, unknown>>();
  const issueRows = await db.prepare(issueSql).bind(...(ownerId ? [ownerId] : [])).all<Record<string, unknown>>();
  const issueTypes = await listIssueTypes(db, { includeDisabled: false, includeMerged: false });

  const models = new Set<string>();
  const scenarios = new Set<string>();
  const orgGroups = new Set<string>();
  const orgCompanies = new Set<string>();
  const orgFleets = new Set<string>();
  const orgLines = new Set<string>();
  const assignees = new Set<string>();

  [...evalRows.results, ...issueRows.results].forEach((row) => {
    const model = String(row.model_version ?? '').trim();
    const scenario = String(row.scenario ?? '').trim();
    const orgGroup = String(row.org_group ?? '').trim();
    const orgCompany = String(row.org_company ?? '').trim();
    const orgFleet = String(row.org_fleet ?? '').trim();
    const orgLine = String(row.org_line ?? '').trim();
    const assignee = String(row.assignee ?? '').trim();
    if (model) models.add(model);
    if (scenario) scenarios.add(scenario);
    if (orgGroup) orgGroups.add(orgGroup);
    if (orgCompany) orgCompanies.add(orgCompany);
    if (orgFleet) orgFleets.add(orgFleet);
    if (orgLine) orgLines.add(orgLine);
    if (assignee) assignees.add(assignee);
  });

  return {
    model_versions: Array.from(models).sort(),
    scenarios: Array.from(scenarios).sort(),
    org_groups: Array.from(orgGroups).sort(),
    org_companies: Array.from(orgCompanies).sort(),
    org_fleets: Array.from(orgFleets).sort(),
    org_lines: Array.from(orgLines).sort(),
    issue_types: issueTypes.map((item) => ({
      id: item.id,
      name: item.name,
      enabled: item.enabled,
      merged_into_id: item.merged_into_id ?? null,
    })),
    assignees: Array.from(assignees).sort(),
    conclusions: VALID_EVAL_CONCLUSIONS,
    statuses: VALID_ISSUE_STATUSES,
    severities: VALID_ISSUE_SEVERITIES,
    priorities: VALID_ISSUE_PRIORITIES,
    submit_modes: VALID_ISSUE_SUBMIT_MODES,
  };
}

export async function getResearchOverview(
  db: D1Database,
  filters: ResearchFilters,
  ownerId?: string
): Promise<Record<string, unknown>> {
  const evalFilter = buildResearchEvalWhereClause(filters, 'e', ownerId);
  const issueFilter = buildResearchIssueWhereClause(filters, 'i', ownerId);

  const evalSummaryRow = await db
    .prepare(
      `SELECT
        COUNT(*) AS total_eval,
        SUM(CASE WHEN e.conclusion = 'pass' THEN 1 ELSE 0 END) AS pass_count,
        SUM(CASE WHEN e.conclusion IN ('warning', 'fail') THEN 1 ELSE 0 END) AS issue_like_count
      FROM agent_eval_records e ${evalFilter.clause}`
    )
    .bind(...evalFilter.params)
    .first<{
      total_eval: number | string;
      pass_count: number | string | null;
      issue_like_count: number | string | null;
    }>();

  const issueSummaryRow = await db
    .prepare(
      `SELECT
        COUNT(*) AS total_issue,
        SUM(CASE WHEN i.severity IN ('high', 'critical') THEN 1 ELSE 0 END) AS high_severity_count,
        SUM(CASE WHEN i.status != 'closed' THEN 1 ELSE 0 END) AS pending_count
      FROM agent_issues i ${issueFilter.clause}`
    )
    .bind(...issueFilter.params)
    .first<{
      total_issue: number | string;
      high_severity_count: number | string | null;
      pending_count: number | string | null;
    }>();

  const totalEval = Number(evalSummaryRow?.total_eval ?? 0);
  const passCount = Number(evalSummaryRow?.pass_count ?? 0);
  const issueLikeCount = Number(evalSummaryRow?.issue_like_count ?? 0);
  const totalIssue = Number(issueSummaryRow?.total_issue ?? 0);
  const highSeverityCount = Number(issueSummaryRow?.high_severity_count ?? 0);
  const pendingCount = Number(issueSummaryRow?.pending_count ?? 0);

  const passRate = totalEval > 0 ? Number(((passCount / totalEval) * 100).toFixed(2)) : 0;
  const issueRate = totalEval > 0 ? Number(((issueLikeCount / totalEval) * 100).toFixed(2)) : 0;

  const evalTrendRows = await db
    .prepare(
      `SELECT substr(e.created_at, 1, 10) AS date, COUNT(*) AS eval_count
       FROM agent_eval_records e ${evalFilter.clause}
       GROUP BY substr(e.created_at, 1, 10)
       ORDER BY date ASC`
    )
    .bind(...evalFilter.params)
    .all<{ date: string; eval_count: number | string }>();
  const issueTrendRows = await db
    .prepare(
      `SELECT substr(i.created_at, 1, 10) AS date, COUNT(*) AS issue_count
       FROM agent_issues i ${issueFilter.clause}
       GROUP BY substr(i.created_at, 1, 10)
       ORDER BY date ASC`
    )
    .bind(...issueFilter.params)
    .all<{ date: string; issue_count: number | string }>();

  const trendMap = new Map<string, { date: string; eval_count: number; issue_count: number }>();
  evalTrendRows.results.forEach((row) => {
    const date = String(row.date ?? '');
    trendMap.set(date, { date, eval_count: Number(row.eval_count ?? 0), issue_count: 0 });
  });
  issueTrendRows.results.forEach((row) => {
    const date = String(row.date ?? '');
    const existing = trendMap.get(date) || { date, eval_count: 0, issue_count: 0 };
    existing.issue_count = Number(row.issue_count ?? 0);
    trendMap.set(date, existing);
  });
  const trend = Array.from(trendMap.values())
    .sort((left, right) => left.date.localeCompare(right.date))
    .map((item) => ({
      ...item,
      issue_rate: item.eval_count > 0 ? Number(((item.issue_count / item.eval_count) * 100).toFixed(2)) : 0,
    }));

  const evalTypeRows = await db
    .prepare(
      `SELECT t.id AS id, t.name AS name, COUNT(*) AS count
       FROM agent_eval_records e
       JOIN agent_eval_issue_types eit ON eit.eval_id = e.id
       JOIN agent_issue_types t ON t.id = eit.issue_type_id
       ${evalFilter.clause}
       GROUP BY t.id, t.name
       ORDER BY count DESC`
    )
    .bind(...evalFilter.params)
    .all<{ id: string; name: string; count: number | string }>();
  const issueTypeRows = await db
    .prepare(
      `SELECT t.id AS id, t.name AS name, COUNT(*) AS count
       FROM agent_issues i
       JOIN agent_issue_issue_types iit ON iit.issue_id = i.id
       JOIN agent_issue_types t ON t.id = iit.issue_type_id
       ${issueFilter.clause}
       GROUP BY t.id, t.name
       ORDER BY count DESC`
    )
    .bind(...issueFilter.params)
    .all<{ id: string; name: string; count: number | string }>();
  const issue_type_distribution_eval = evalTypeRows.results
    .map((row) => ({
      id: String(row.id ?? ''),
      name: String(row.name ?? ''),
      eval_count: Number(row.count ?? 0),
      issue_count: 0,
      total_count: Number(row.count ?? 0),
    }))
    .filter((row) => row.id && row.name && row.total_count > 0);
  const issue_type_distribution_issue = issueTypeRows.results
    .map((row) => ({
      id: String(row.id ?? ''),
      name: String(row.name ?? ''),
      eval_count: 0,
      issue_count: Number(row.count ?? 0),
      total_count: Number(row.count ?? 0),
    }))
    .filter((row) => row.id && row.name && row.total_count > 0);
  const fusedTypeMap = new Map<string, { id: string; name: string; eval_count: number; issue_count: number; total_count: number }>();
  issue_type_distribution_eval.forEach((row) => {
    fusedTypeMap.set(row.id, { ...row });
  });
  issue_type_distribution_issue.forEach((row) => {
    const existing = fusedTypeMap.get(row.id);
    if (existing) {
      existing.issue_count += row.issue_count;
      existing.total_count = existing.eval_count + existing.issue_count;
      return;
    }
    fusedTypeMap.set(row.id, { ...row });
  });
  const issue_type_distribution_fused = Array.from(fusedTypeMap.values()).sort(
    (left, right) => right.total_count - left.total_count
  );

  const scenarioRows = await db
    .prepare(
      `SELECT i.scenario AS name, COUNT(*) AS count
       FROM agent_issues i ${issueFilter.clause}
       GROUP BY i.scenario
       ORDER BY count DESC`
    )
    .bind(...issueFilter.params)
    .all<{ name: string | null; count: number | string }>();
  const scenario_distribution = scenarioRows.results
    .map((row) => ({ name: String(row.name ?? 'Uncategorized'), count: Number(row.count ?? 0) }))
    .filter((row) => row.count > 0);

  const modelRows = await db
    .prepare(
      `SELECT e.model_version AS name, COUNT(*) AS count
       FROM agent_eval_records e ${evalFilter.clause}
       GROUP BY e.model_version
       ORDER BY count DESC`
    )
    .bind(...evalFilter.params)
    .all<{ name: string | null; count: number | string }>();
  const model_distribution = modelRows.results
    .map((row) => ({ name: String(row.name ?? 'unknown'), count: Number(row.count ?? 0) }))
    .filter((row) => row.count > 0);

  const issueHotRows = await db
    .prepare(
      `SELECT
        COALESCE(NULLIF(i.org_company, ''), NULLIF(i.org_fleet, ''), NULLIF(i.org_group, ''), 'unknown') AS hotspot_key,
        COUNT(*) AS issue_count,
        SUM(
          CASE
            WHEN i.severity = 'critical' THEN 4
            WHEN i.severity = 'high' THEN 3
            WHEN i.severity = 'medium' THEN 2
            ELSE 1
          END
        ) AS risk_score
      FROM agent_issues i ${issueFilter.clause}
      GROUP BY hotspot_key
      ORDER BY risk_score DESC
      LIMIT 10`
    )
    .bind(...issueFilter.params)
    .all<{ hotspot_key: string; issue_count: number | string; risk_score: number | string }>();
  const evalHotRows = await db
    .prepare(
      `SELECT
        COALESCE(NULLIF(e.org_company, ''), NULLIF(e.org_fleet, ''), NULLIF(e.org_group, ''), 'unknown') AS hotspot_key,
        COUNT(*) AS eval_count
      FROM agent_eval_records e ${evalFilter.clause}
      GROUP BY hotspot_key`
    )
    .bind(...evalFilter.params)
    .all<{ hotspot_key: string; eval_count: number | string }>();
  const evalHotMap = new Map<string, number>();
  evalHotRows.results.forEach((row) => {
    evalHotMap.set(String(row.hotspot_key ?? 'unknown'), Number(row.eval_count ?? 0));
  });
  const risk_hotspots = issueHotRows.results.map((row) => {
    const key = String(row.hotspot_key ?? 'unknown');
    return {
      key,
      eval_count: evalHotMap.get(key) ?? 0,
      issue_count: Number(row.issue_count ?? 0),
      risk_score: Number(row.risk_score ?? 0),
    };
  });

  return {
    kpi: {
      total_eval: totalEval,
      pass_rate: passRate,
      issue_rate: issueRate,
      high_severity_issue_count: highSeverityCount,
      pending_issue_count: pendingCount,
      total_issue: totalIssue,
    },
    trend,
    issue_type_distribution_eval,
    issue_type_distribution_issue,
    issue_type_distribution_fused,
    scenario_distribution,
    model_distribution,
    risk_hotspots,
    updated_at: new Date().toISOString(),
  };
}

export async function createEvalRecord(
  db: D1Database,
  env: ResearchModelEnvLike,
  payload: {
    session_id: string;
    conclusion?: EvalConclusion;
    issue_type_ids?: string[];
    new_issue_type_names?: string[];
    confidence?: number;
    note?: string;
    tags?: string[];
    model_version?: string | null;
    scenario?: string;
    org_group?: string;
    org_company?: string;
    org_fleet?: string;
    org_line?: string;
    referenced_message_ids?: string[];
    source?: EvalSource;
    is_read?: boolean;
    is_favorite?: boolean;
  }
): Promise<EvalRecord> {
  const now = new Date().toISOString();
  const modelVersion = await getSessionModelVersion(db, env, payload.session_id, payload.model_version ?? null);
  const resolvedIssueTypeIds = await resolveIssueTypeIdsForWrite(
    db,
    payload.issue_type_ids,
    payload.new_issue_type_names,
    payload.source
  );
  const issueTypes = await listIssueTypeRefsByIds(db, resolvedIssueTypeIds.ids);
  const legacyIssueType = issueTypes[0]?.name ?? null;
  const record: EvalRecord = {
    id: createResearchId('eval'),
    session_id: payload.session_id,
    conclusion: normalizeEvalConclusion(payload.conclusion, 'warning'),
    issue_types: issueTypes,
    confidence: Number.isFinite(payload.confidence) ? Number(payload.confidence) : null,
    note: payload.note?.trim() || null,
    tags: Array.isArray(payload.tags) ? payload.tags.filter(Boolean) : [],
    model_version: modelVersion,
    scenario: payload.scenario?.trim() || null,
    org_group: payload.org_group?.trim() || null,
    org_company: payload.org_company?.trim() || null,
    org_fleet: payload.org_fleet?.trim() || null,
    org_line: payload.org_line?.trim() || null,
    referenced_message_ids: Array.isArray(payload.referenced_message_ids)
      ? payload.referenced_message_ids.filter(Boolean)
      : [],
    is_read: payload.is_read === true,
    is_favorite: payload.is_favorite === true,
    source: normalizeEvalSource(payload.source, 'research'),
    created_at: now,
    updated_at: now,
  };

  await db
    .prepare(
      'INSERT INTO agent_eval_records (id, session_id, conclusion, issue_type, confidence, note, tags_json, model_version, scenario, org_group, org_company, org_fleet, org_line, referenced_message_ids_json, is_read, is_favorite, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .bind(
      record.id,
      record.session_id,
      record.conclusion,
      legacyIssueType,
      record.confidence,
      record.note,
      JSON.stringify(record.tags),
      record.model_version,
      record.scenario,
      record.org_group,
      record.org_company,
      record.org_fleet,
      record.org_line,
      JSON.stringify(record.referenced_message_ids),
      record.is_read ? 1 : 0,
      record.is_favorite ? 1 : 0,
      record.source,
      record.created_at,
      record.updated_at
    )
    .run();

  await assignEvalIssueTypes(db, record.id, resolvedIssueTypeIds.ids, true);

  return record;
}

export async function updateEvalRecord(
  db: D1Database,
  id: string,
  payload: Partial<{
    conclusion: EvalConclusion;
    issue_type_ids: string[];
    new_issue_type_names: string[];
    confidence: number | null;
    note: string;
    tags: string[];
    is_read: boolean;
    is_favorite: boolean;
  }>
): Promise<EvalRecord | null> {
  const existing = await getEvalRecordById(db, id);
  if (!existing) return null;

  const hasIssueTypePayload = payload.issue_type_ids !== undefined || payload.new_issue_type_names !== undefined;
  const resolvedIssueTypeIds = hasIssueTypePayload
    ? await resolveIssueTypeIdsForWrite(db, payload.issue_type_ids, payload.new_issue_type_names)
    : { ids: existing.issue_types.map((item) => item.id), redirects: [] as Array<{ from: string; to: string }> };
  const issueTypes = await listIssueTypeRefsByIds(db, resolvedIssueTypeIds.ids);
  const legacyIssueType = issueTypes[0]?.name ?? null;

  const next: EvalRecord = {
    ...existing,
    conclusion: payload.conclusion ? normalizeEvalConclusion(payload.conclusion, existing.conclusion) : existing.conclusion,
    issue_types: issueTypes,
    confidence:
      payload.confidence === undefined
        ? existing.confidence
        : payload.confidence === null
        ? null
        : Number.isFinite(payload.confidence)
        ? Number(payload.confidence)
        : existing.confidence,
    note: payload.note !== undefined ? payload.note.trim() || null : existing.note,
    tags: payload.tags ? payload.tags.filter(Boolean) : existing.tags,
    is_read: payload.is_read === undefined ? existing.is_read : payload.is_read,
    is_favorite: payload.is_favorite === undefined ? existing.is_favorite : payload.is_favorite,
    updated_at: new Date().toISOString(),
  };

  await db
    .prepare(
      'UPDATE agent_eval_records SET conclusion = ?, issue_type = ?, confidence = ?, note = ?, tags_json = ?, is_read = ?, is_favorite = ?, updated_at = ? WHERE id = ?'
    )
    .bind(
      next.conclusion,
      legacyIssueType,
      next.confidence,
      next.note,
      JSON.stringify(next.tags),
      next.is_read ? 1 : 0,
      next.is_favorite ? 1 : 0,
      next.updated_at,
      id
    )
    .run();

  if (hasIssueTypePayload) {
    await assignEvalIssueTypes(db, id, resolvedIssueTypeIds.ids, true);
  }

  return next;
}

export async function createIssueRecord(
  db: D1Database,
  env: ResearchModelEnvLike,
  payload: {
    title?: string;
    issue_type_ids?: string[];
    new_issue_type_names?: string[];
    severity?: IssueSeverity;
    priority?: IssuePriority;
    status?: IssueStatus;
    description: string;
    expected_result?: string;
    business_impact?: string;
    repro_steps?: string;
    session_id: string;
    source_eval_id?: string;
    referenced_message_ids?: string[];
    context_summary?: string;
    model_version?: string | null;
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
    comment?: Partial<IssueOperationComment> | null;
    operator?: string;
  }
): Promise<IssueRecord> {
  const nowDate = new Date();
  const now = nowDate.toISOString();
  const modelVersion = await getSessionModelVersion(db, env, payload.session_id, payload.model_version ?? null);
  const resolvedIssueTypeIds = await resolveIssueTypeIdsForWrite(
    db,
    payload.issue_type_ids,
    payload.new_issue_type_names,
    payload.operator
  );
  const issueTypes = await listIssueTypeRefsByIds(db, resolvedIssueTypeIds.ids);
  const legacyIssueType = issueTypes[0]?.name ?? null;
  const status = normalizeIssueStatus(payload.status, 'pending_confirm');
  const comment = normalizeIssueOperationComment(payload.comment);
  assertIssueInProgressComment(status, comment);
  const commentNote = buildIssueCommentNote(comment);
  const issueTitle = buildIssueTitle(payload.title, nowDate);
  const record: IssueRecord = {
    id: createResearchId('issue'),
    title: issueTitle,
    issue_types: issueTypes,
    severity: normalizeIssueSeverity(payload.severity, 'medium'),
    priority: normalizeIssuePriority(payload.priority, 'p2'),
    status,
    description: payload.description.trim(),
    expected_result: payload.expected_result?.trim() || null,
    business_impact: payload.business_impact?.trim() || null,
    repro_steps: payload.repro_steps?.trim() || null,
    session_id: payload.session_id,
    source_eval_id: payload.source_eval_id?.trim() || null,
    referenced_message_ids: payload.referenced_message_ids?.filter(Boolean) ?? [],
    context_summary: payload.context_summary?.trim() || null,
    model_version: modelVersion,
    scenario: payload.scenario?.trim() || null,
    org_group: payload.org_group?.trim() || null,
    org_company: payload.org_company?.trim() || null,
    org_fleet: payload.org_fleet?.trim() || null,
    org_line: payload.org_line?.trim() || null,
    assignee: payload.assignee?.trim() || null,
    due_at: payload.due_at?.trim() || null,
    submit_mode: normalizeIssueSubmitMode(payload.submit_mode, 'quick'),
    source_metric: payload.source_metric ?? null,
    created_by: payload.created_by?.trim() || null,
    updated_by: payload.updated_by?.trim() || null,
    created_at: now,
    updated_at: now,
    closed_at: status === 'closed' ? now : null,
  };

  await db
    .prepare(
      'INSERT INTO agent_issues (id, title, issue_type, severity, priority, status, description, expected_result, business_impact, repro_steps, session_id, source_eval_id, referenced_message_ids_json, context_summary, model_version, scenario, org_group, org_company, org_fleet, org_line, assignee, due_at, submit_mode, source_metric_json, created_by, updated_by, created_at, updated_at, closed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .bind(
      record.id,
      record.title,
      legacyIssueType,
      record.severity,
      record.priority,
      record.status,
      record.description,
      record.expected_result,
      record.business_impact,
      record.repro_steps,
      record.session_id,
      record.source_eval_id,
      JSON.stringify(record.referenced_message_ids),
      record.context_summary,
      record.model_version,
      record.scenario,
      record.org_group,
      record.org_company,
      record.org_fleet,
      record.org_line,
      record.assignee,
      record.due_at,
      record.submit_mode,
      record.source_metric ? JSON.stringify(record.source_metric) : null,
      record.created_by,
      record.updated_by,
      record.created_at,
      record.updated_at,
      record.closed_at
    )
    .run();

  await assignIssueIssueTypes(db, record.id, resolvedIssueTypeIds.ids, true);

  await createIssueEvent(db, {
    issue_id: record.id,
    action: 'created',
    from_status: null,
    to_status: record.status,
    note: payload.event_note?.trim() || commentNote || null,
    operator: payload.operator ?? record.created_by ?? null,
    metadata: {
      submit_mode: record.submit_mode,
      source_eval_id: record.source_eval_id,
      comment,
    },
  });

  return record;
}

export async function updateIssueRecord(
  db: D1Database,
  id: string,
  payload: Partial<{
    title: string;
    issue_type_ids: string[];
    new_issue_type_names: string[];
    severity: IssueSeverity;
    priority: IssuePriority;
    status: IssueStatus;
    description: string;
    expected_result: string;
    business_impact: string;
    repro_steps: string;
    assignee: string;
    due_at: string | null;
    context_summary: string;
    scenario: string;
    org_group: string;
    org_company: string;
    org_fleet: string;
    org_line: string;
    submit_mode: IssueSubmitMode;
    updated_by: string;
    event_note: string;
    comment: Partial<IssueOperationComment> | null;
    operator: string;
  }>
): Promise<IssueRecord | null> {
  const existing = await getIssueRecordById(db, id);
  if (!existing) return null;

  const hasIssueTypePayload = payload.issue_type_ids !== undefined || payload.new_issue_type_names !== undefined;
  const resolvedIssueTypeIds = hasIssueTypePayload
    ? await resolveIssueTypeIdsForWrite(db, payload.issue_type_ids, payload.new_issue_type_names, payload.operator)
    : { ids: existing.issue_types.map((item) => item.id), redirects: [] as Array<{ from: string; to: string }> };
  const issueTypes = await listIssueTypeRefsByIds(db, resolvedIssueTypeIds.ids);
  const legacyIssueType = issueTypes[0]?.name ?? null;

  const nextStatus =
    payload.status !== undefined ? normalizeIssueStatus(payload.status, existing.status) : existing.status;
  const comment = normalizeIssueOperationComment(payload.comment);
  assertIssueInProgressComment(nextStatus, comment);
  const commentNote = buildIssueCommentNote(comment);
  const now = new Date().toISOString();
  const next: IssueRecord = {
    ...existing,
    title: payload.title !== undefined ? payload.title.trim() || existing.title : existing.title,
    issue_types: issueTypes,
    severity: payload.severity !== undefined ? normalizeIssueSeverity(payload.severity, existing.severity) : existing.severity,
    priority: payload.priority !== undefined ? normalizeIssuePriority(payload.priority, existing.priority) : existing.priority,
    status: nextStatus,
    description: payload.description !== undefined ? payload.description.trim() || existing.description : existing.description,
    expected_result:
      payload.expected_result !== undefined ? payload.expected_result.trim() || null : existing.expected_result,
    business_impact:
      payload.business_impact !== undefined ? payload.business_impact.trim() || null : existing.business_impact,
    repro_steps: payload.repro_steps !== undefined ? payload.repro_steps.trim() || null : existing.repro_steps,
    assignee: payload.assignee !== undefined ? payload.assignee.trim() || null : existing.assignee,
    due_at: payload.due_at !== undefined ? (payload.due_at ? payload.due_at.trim() : null) : existing.due_at,
    context_summary:
      payload.context_summary !== undefined ? payload.context_summary.trim() || null : existing.context_summary,
    scenario: payload.scenario !== undefined ? payload.scenario.trim() || null : existing.scenario,
    org_group: payload.org_group !== undefined ? payload.org_group.trim() || null : existing.org_group,
    org_company: payload.org_company !== undefined ? payload.org_company.trim() || null : existing.org_company,
    org_fleet: payload.org_fleet !== undefined ? payload.org_fleet.trim() || null : existing.org_fleet,
    org_line: payload.org_line !== undefined ? payload.org_line.trim() || null : existing.org_line,
    submit_mode:
      payload.submit_mode !== undefined ? normalizeIssueSubmitMode(payload.submit_mode, existing.submit_mode) : existing.submit_mode,
    updated_by: payload.updated_by !== undefined ? payload.updated_by.trim() || null : existing.updated_by,
    updated_at: now,
    closed_at: nextStatus === 'closed' ? existing.closed_at || now : null,
  };

  await db
    .prepare(
      'UPDATE agent_issues SET title = ?, issue_type = ?, severity = ?, priority = ?, status = ?, description = ?, expected_result = ?, business_impact = ?, repro_steps = ?, assignee = ?, due_at = ?, context_summary = ?, scenario = ?, org_group = ?, org_company = ?, org_fleet = ?, org_line = ?, submit_mode = ?, updated_by = ?, updated_at = ?, closed_at = ? WHERE id = ?'
    )
    .bind(
      next.title,
      legacyIssueType,
      next.severity,
      next.priority,
      next.status,
      next.description,
      next.expected_result,
      next.business_impact,
      next.repro_steps,
      next.assignee,
      next.due_at,
      next.context_summary,
      next.scenario,
      next.org_group,
      next.org_company,
      next.org_fleet,
      next.org_line,
      next.submit_mode,
      next.updated_by,
      next.updated_at,
      next.closed_at,
      id
    )
    .run();

  if (hasIssueTypePayload) {
    await assignIssueIssueTypes(db, id, resolvedIssueTypeIds.ids, true);
  }

  const statusChanged = existing.status !== next.status;
  await createIssueEvent(db, {
    issue_id: next.id,
    action: statusChanged ? 'status_changed' : 'updated',
    from_status: statusChanged ? existing.status : null,
    to_status: statusChanged ? next.status : null,
    note: payload.event_note?.trim() || commentNote || null,
    operator: payload.operator ?? next.updated_by ?? null,
    metadata: {
      severity: next.severity,
      priority: next.priority,
      assignee: next.assignee,
      comment,
    },
  });

  return next;
}
