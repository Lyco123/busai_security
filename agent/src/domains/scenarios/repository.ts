export type D1Database = {
  prepare: (query: string) => D1PreparedStatement;
  batch?: (statements: D1PreparedStatement[]) => Promise<unknown>;
};

export type D1PreparedStatement = {
  bind: (...values: unknown[]) => D1PreparedStatement;
  first: <T = Record<string, unknown>>() => Promise<T | null>;
  all: <T = Record<string, unknown>>() => Promise<{ results: T[] }>;
  run: () => Promise<unknown>;
};

export interface WorkScenario {
  id: string;
  name: string;
  description: string;
  keywords?: string[];
  embedding?: number[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

function parseStringArray(value?: string | null): string[] | undefined {
  if (!value) return undefined;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String) : undefined;
  } catch {
    return undefined;
  }
}

function parseNumberArray(value?: string | null): number[] | undefined {
  if (!value) return undefined;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(Number).filter(Number.isFinite) : undefined;
  } catch {
    return undefined;
  }
}

function parseScenarioRow(row: Record<string, unknown>): WorkScenario {
  return {
    id: String(row.id),
    name: String(row.name),
    description: String(row.description),
    keywords: parseStringArray(row.keywords as string | null),
    embedding: parseNumberArray(row.embedding as string | null),
    enabled: Boolean(row.enabled),
    created_at: String(row.created_at),
    updated_at: String(row.updated_at),
  };
}

export async function listWorkScenarios(
  db: D1Database,
  options?: { includeDisabled?: boolean; limit?: number }
): Promise<WorkScenario[]> {
  const includeDisabled = options?.includeDisabled ?? false;
  const limit = Math.max(1, Math.min(options?.limit ?? 200, 500));
  let query =
    'SELECT id, name, description, keywords, embedding, enabled, created_at, updated_at FROM work_scenarios';
  if (!includeDisabled) {
    query += ' WHERE enabled = 1';
  }
  query += ' ORDER BY updated_at DESC LIMIT ?';

  const result = await db.prepare(query).bind(limit).all<Record<string, unknown>>();
  return result.results.map(parseScenarioRow);
}

export async function getWorkScenario(db: D1Database, id: string): Promise<WorkScenario | null> {
  const row = await db
    .prepare(
      'SELECT id, name, description, keywords, embedding, enabled, created_at, updated_at FROM work_scenarios WHERE id = ? LIMIT 1'
    )
    .bind(id)
    .first<Record<string, unknown>>();
  return row ? parseScenarioRow(row) : null;
}

export async function insertWorkScenario(
  db: D1Database,
  scenario: {
    id: string;
    name: string;
    description: string;
    keywords?: string[];
    embedding?: number[] | null;
    enabled?: boolean;
  }
): Promise<WorkScenario> {
  const now = new Date().toISOString();
  await db
    .prepare(
      'INSERT INTO work_scenarios (id, name, description, keywords, embedding, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .bind(
      scenario.id,
      scenario.name,
      scenario.description,
      scenario.keywords ? JSON.stringify(scenario.keywords) : null,
      scenario.embedding ? JSON.stringify(scenario.embedding) : null,
      scenario.enabled === false ? 0 : 1,
      now,
      now
    )
    .run();

  return {
    id: scenario.id,
    name: scenario.name,
    description: scenario.description,
    keywords: scenario.keywords,
    embedding: scenario.embedding ?? undefined,
    enabled: scenario.enabled !== false,
    created_at: now,
    updated_at: now,
  };
}

export async function updateWorkScenario(
  db: D1Database,
  id: string,
  updates: Partial<{
    name: string;
    description: string;
    keywords: string[];
    embedding: number[] | null;
    enabled: boolean;
  }>
): Promise<WorkScenario | null> {
  const existing = await getWorkScenario(db, id);
  if (!existing) {
    return null;
  }

  const next: WorkScenario = {
    ...existing,
    name: updates.name ?? existing.name,
    description: updates.description ?? existing.description,
    keywords: updates.keywords ?? existing.keywords,
    embedding: updates.embedding ?? existing.embedding,
    enabled: updates.enabled ?? existing.enabled,
    updated_at: new Date().toISOString(),
  };

  await db
    .prepare(
      'UPDATE work_scenarios SET name = ?, description = ?, keywords = ?, embedding = ?, enabled = ?, updated_at = ? WHERE id = ?'
    )
    .bind(
      next.name,
      next.description,
      next.keywords ? JSON.stringify(next.keywords) : null,
      next.embedding ? JSON.stringify(next.embedding) : null,
      next.enabled ? 1 : 0,
      next.updated_at,
      id
    )
    .run();

  return next;
}

export async function deleteWorkScenario(db: D1Database, id: string): Promise<boolean> {
  await db.prepare('DELETE FROM work_scenarios WHERE id = ?').bind(id).run();
  return true;
}
