import { safeJsonParse } from '../../shared/json';
import type { D1Database } from '../scenarios/repository';

export interface RuleEmbeddingPayload {
  anchor?: number[];
  examples?: number[][];
}

export interface RuleRecord {
  id: string;
  name: string;
  match_text: string;
  enabled: boolean;
  priority: number;
  version: number;
  embedding?: RuleEmbeddingPayload | null;
  data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function parseRuleEmbedding(value?: string | null): RuleEmbeddingPayload | null {
  if (!value) return null;
  const parsed = safeJsonParse(value);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
  const record = parsed as Record<string, unknown>;
  const anchor =
    Array.isArray(record.anchor) && record.anchor.every((n) => typeof n === 'number')
      ? (record.anchor as number[])
      : undefined;
  const examplesRaw = record.examples;
  const examples =
    Array.isArray(examplesRaw) &&
    examplesRaw.every((row) => Array.isArray(row) && row.every((n) => typeof n === 'number'))
      ? (examplesRaw as number[][])
      : undefined;
  return { anchor, examples };
}

function parseRuleRow(row: Record<string, unknown>): RuleRecord {
  const data = safeJsonParse(String(row.data ?? '')) as Record<string, unknown> | null;
  return {
    id: String(row.id ?? ''),
    name: String(row.name ?? ''),
    match_text: String(row.match_text ?? ''),
    enabled: Number(row.enabled ?? 1) === 1,
    priority: Number(row.priority ?? 50),
    version: Number(row.version ?? 1),
    embedding: parseRuleEmbedding(row.embedding as string | null),
    data: data && typeof data === 'object' ? data : {},
    created_at: String(row.created_at ?? ''),
    updated_at: String(row.updated_at ?? ''),
  };
}

export async function listRules(
  db: D1Database,
  options?: { includeDisabled?: boolean; limit?: number }
): Promise<RuleRecord[]> {
  const includeDisabled = options?.includeDisabled ?? true;
  const limit = Math.min(options?.limit ?? 200, 200);
  let query =
    'SELECT id, name, match_text, enabled, priority, version, embedding, data, created_at, updated_at FROM rules';
  if (!includeDisabled) {
    query += ' WHERE enabled = 1';
  }
  query += ' ORDER BY updated_at DESC LIMIT ?';
  const result = await db.prepare(query).bind(limit).all<Record<string, unknown>>();
  return result.results.map(parseRuleRow);
}

export async function getRuleById(db: D1Database, id: string): Promise<RuleRecord | null> {
  const row = await db
    .prepare(
      'SELECT id, name, match_text, enabled, priority, version, embedding, data, created_at, updated_at FROM rules WHERE id = ?'
    )
    .bind(id)
    .first<Record<string, unknown>>();
  return row ? parseRuleRow(row) : null;
}

export async function getRuleByIdOrName(db: D1Database, value: string): Promise<RuleRecord | null> {
  const row = await db
    .prepare(
      'SELECT id, name, match_text, enabled, priority, version, embedding, data, created_at, updated_at FROM rules WHERE id = ? OR name = ? LIMIT 1'
    )
    .bind(value, value)
    .first<Record<string, unknown>>();
  if (row) return parseRuleRow(row);

  const fuzzy = await db
    .prepare(
      'SELECT id, name, match_text, enabled, priority, version, embedding, data, created_at, updated_at FROM rules WHERE name LIKE ? LIMIT 1'
    )
    .bind(`%${value}%`)
    .first<Record<string, unknown>>();
  return fuzzy ? parseRuleRow(fuzzy) : null;
}

export async function insertRule(
  db: D1Database,
  rule: {
    id: string;
    name: string;
    match_text: string;
    enabled?: boolean;
    priority?: number;
    version?: number;
    embedding?: RuleEmbeddingPayload | null;
    data: Record<string, unknown>;
  }
): Promise<RuleRecord> {
  const now = new Date().toISOString();
  await db
    .prepare(
      'INSERT INTO rules (id, name, match_text, enabled, priority, version, embedding, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .bind(
      rule.id,
      rule.name,
      rule.match_text,
      rule.enabled === false ? 0 : 1,
      rule.priority ?? 50,
      rule.version ?? 1,
      rule.embedding ? JSON.stringify(rule.embedding) : null,
      JSON.stringify(rule.data ?? {}),
      now,
      now
    )
    .run();

  return {
    id: rule.id,
    name: rule.name,
    match_text: rule.match_text,
    enabled: rule.enabled !== false,
    priority: rule.priority ?? 50,
    version: rule.version ?? 1,
    embedding: rule.embedding ?? null,
    data: rule.data ?? {},
    created_at: now,
    updated_at: now,
  };
}

export async function updateRule(
  db: D1Database,
  id: string,
  updates: Partial<{
    name: string;
    match_text: string;
    enabled: boolean;
    priority: number;
    version: number;
    embedding: RuleEmbeddingPayload | null;
    data: Record<string, unknown>;
  }>
): Promise<RuleRecord | null> {
  const existing = await getRuleById(db, id);
  if (!existing) return null;

  const next: RuleRecord = {
    ...existing,
    name: updates.name ?? existing.name,
    match_text: updates.match_text ?? existing.match_text,
    enabled: updates.enabled ?? existing.enabled,
    priority: updates.priority ?? existing.priority,
    version: updates.version ?? existing.version,
    embedding: updates.embedding ?? existing.embedding,
    data: updates.data ?? existing.data,
    updated_at: new Date().toISOString(),
  };

  await db
    .prepare(
      'UPDATE rules SET name = ?, match_text = ?, enabled = ?, priority = ?, version = ?, embedding = ?, data = ?, updated_at = ? WHERE id = ?'
    )
    .bind(
      next.name,
      next.match_text,
      next.enabled ? 1 : 0,
      next.priority,
      next.version,
      next.embedding ? JSON.stringify(next.embedding) : null,
      JSON.stringify(next.data ?? {}),
      next.updated_at,
      id
    )
    .run();

  return next;
}

export async function deleteRule(db: D1Database, id: string): Promise<boolean> {
  await db.prepare('DELETE FROM rules WHERE id = ?').bind(id).run();
  return true;
}
