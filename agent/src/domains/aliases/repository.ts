export type D1Database = {
  prepare: (query: string) => D1PreparedStatement;
};

export type D1PreparedStatement = {
  bind: (...values: unknown[]) => D1PreparedStatement;
  first: <T = Record<string, unknown>>() => Promise<T | null>;
  all: <T = Record<string, unknown>>() => Promise<{ results: T[] }>;
  run: () => Promise<unknown>;
};

export type EntityAliasType = 'unit' | 'route' | 'fleet';
export type EntityAliasStatus = 'pending' | 'approved' | 'rejected';

export interface EntityStandardName {
  id: string;
  entity_type: EntityAliasType;
  standard_name: string;
  enabled: boolean;
  unit_level: string | null;
  can_compose_with_fleet: boolean;
  created_at: string;
  updated_at: string;
}

export interface EntityAliasRecord {
  id: string;
  entity_type: EntityAliasType;
  standard_name: string;
  alias: string;
  status: EntityAliasStatus;
  submitted_by: string | null;
  submitted_by_role: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

function normalizeEntityType(value: unknown): EntityAliasType {
  if (value === 'route' || value === 'fleet') return value;
  return 'unit';
}

function normalizeAliasStatus(value: unknown): EntityAliasStatus {
  if (value === 'approved' || value === 'rejected') {
    return value;
  }
  return 'pending';
}

function parseBoolean(value: unknown): boolean {
  return Number(value ?? 0) === 1;
}

function parseStandardRow(row: Record<string, unknown>): EntityStandardName {
  return {
    id: String(row.id),
    entity_type: normalizeEntityType(row.entity_type),
    standard_name: String(row.standard_name),
    enabled: parseBoolean(row.enabled),
    unit_level: row.unit_level == null ? null : String(row.unit_level),
    can_compose_with_fleet: parseBoolean(row.can_compose_with_fleet),
    created_at: String(row.created_at),
    updated_at: String(row.updated_at),
  };
}

function parseAliasRow(row: Record<string, unknown>): EntityAliasRecord {
  return {
    id: String(row.id),
    entity_type: normalizeEntityType(row.entity_type),
    standard_name: String(row.standard_name),
    alias: String(row.alias),
    status: normalizeAliasStatus(row.status),
    submitted_by: row.submitted_by == null ? null : String(row.submitted_by),
    submitted_by_role: row.submitted_by_role == null ? null : String(row.submitted_by_role),
    reviewed_by: row.reviewed_by == null ? null : String(row.reviewed_by),
    reviewed_at: row.reviewed_at == null ? null : String(row.reviewed_at),
    created_at: String(row.created_at),
    updated_at: String(row.updated_at),
  };
}

export async function listEntityStandardNames(
  db: D1Database,
  options?: { entityType?: EntityAliasType; includeDisabled?: boolean }
): Promise<EntityStandardName[]> {
  const clauses: string[] = [];
  const values: unknown[] = [];
  if (options?.entityType) {
    clauses.push('entity_type = ?');
    values.push(options.entityType);
  }
  if (!options?.includeDisabled) {
    clauses.push('enabled = 1');
  }

  let query =
    `SELECT id, entity_type, standard_name, enabled, unit_level, can_compose_with_fleet, created_at, updated_at
       FROM entity_standard_names`;
  if (clauses.length > 0) {
    query += ` WHERE ${clauses.join(' AND ')}`;
  }
  query += ' ORDER BY entity_type ASC, standard_name ASC';

  const result = await db.prepare(query).bind(...values).all<Record<string, unknown>>();
  return result.results.map(parseStandardRow);
}

export async function upsertEntityStandardName(
  db: D1Database,
  input: { id: string; entityType: EntityAliasType; standardName: string }
): Promise<void> {
  const now = new Date().toISOString();
  await db
    .prepare(
      `INSERT INTO entity_standard_names (
         id, entity_type, standard_name, enabled, unit_level, can_compose_with_fleet, created_at, updated_at
       )
       VALUES (?, ?, ?, 1, NULL, 0, ?, ?)
       ON CONFLICT(entity_type, standard_name) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at`
    )
    .bind(input.id, input.entityType, input.standardName, now, now)
    .run();
}

export async function listEntityAliases(
  db: D1Database,
  options?: { entityType?: EntityAliasType; status?: EntityAliasStatus }
): Promise<EntityAliasRecord[]> {
  const clauses: string[] = [];
  const values: unknown[] = [];
  if (options?.entityType) {
    clauses.push('entity_type = ?');
    values.push(options.entityType);
  }
  if (options?.status) {
    clauses.push('status = ?');
    values.push(options.status);
  }

  let query =
    `SELECT id, entity_type, standard_name, alias, status, submitted_by, submitted_by_role, reviewed_by, reviewed_at,
            created_at, updated_at
       FROM entity_aliases`;
  if (clauses.length > 0) {
    query += ` WHERE ${clauses.join(' AND ')}`;
  }
  query += " ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, updated_at DESC";

  const result = await db.prepare(query).bind(...values).all<Record<string, unknown>>();
  return result.results.map(parseAliasRow);
}

export async function listApprovedEntityAliases(
  db: D1Database,
  entityType?: EntityAliasType
): Promise<EntityAliasRecord[]> {
  return listEntityAliases(db, { entityType, status: 'approved' });
}

export async function getEntityAlias(db: D1Database, id: string): Promise<EntityAliasRecord | null> {
  const row = await db
    .prepare(
      `SELECT id, entity_type, standard_name, alias, status, submitted_by, submitted_by_role, reviewed_by, reviewed_at,
              created_at, updated_at
         FROM entity_aliases
        WHERE id = ?
        LIMIT 1`
    )
    .bind(id)
    .first<Record<string, unknown>>();
  return row ? parseAliasRow(row) : null;
}

export async function insertEntityAlias(
  db: D1Database,
  input: {
    id: string;
    entityType: EntityAliasType;
    standardName: string;
    alias: string;
    status: EntityAliasStatus;
    submittedBy: string | null;
    submittedByRole: string | null;
    reviewedBy?: string | null;
  }
): Promise<EntityAliasRecord> {
  const now = new Date().toISOString();
  const reviewedAt = input.status === 'approved' || input.status === 'rejected' ? now : null;
  await db
    .prepare(
      `INSERT INTO entity_aliases (
         id, entity_type, standard_name, alias, status, submitted_by, submitted_by_role, reviewed_by, reviewed_at,
         created_at, updated_at
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .bind(
      input.id,
      input.entityType,
      input.standardName,
      input.alias,
      input.status,
      input.submittedBy,
      input.submittedByRole,
      input.reviewedBy ?? null,
      reviewedAt,
      now,
      now
    )
    .run();

  return {
    id: input.id,
    entity_type: input.entityType,
    standard_name: input.standardName,
    alias: input.alias,
    status: input.status,
    submitted_by: input.submittedBy,
    submitted_by_role: input.submittedByRole,
    reviewed_by: input.reviewedBy ?? null,
    reviewed_at: reviewedAt,
    created_at: now,
    updated_at: now,
  };
}

export async function updateEntityAliasStatus(
  db: D1Database,
  id: string,
  status: EntityAliasStatus,
  reviewedBy: string | null
): Promise<EntityAliasRecord | null> {
  const existing = await getEntityAlias(db, id);
  if (!existing) return null;

  const now = new Date().toISOString();
  await db
    .prepare('UPDATE entity_aliases SET status = ?, reviewed_by = ?, reviewed_at = ?, updated_at = ? WHERE id = ?')
    .bind(status, reviewedBy, now, now, id)
    .run();

  return {
    ...existing,
    status,
    reviewed_by: reviewedBy,
    reviewed_at: now,
    updated_at: now,
  };
}

export async function deleteEntityAlias(db: D1Database, id: string): Promise<void> {
  await db.prepare('DELETE FROM entity_aliases WHERE id = ?').bind(id).run();
}
