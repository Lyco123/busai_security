import type { AccessLevel } from '../models/access';
import type {
  AuditLogRecord,
  ClauseRecord,
  DocumentRecord,
  IngestPreviewRecord,
  IndexJobRecord,
} from '../models/contracts';
import { clickhouseGateway } from './clickhouse';

function nowIso(): string {
  return new Date().toISOString();
}

function sanitizeJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {});
  } catch {
    return '{}';
  }
}

export interface ClauseWithDocMeta {
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
  field_path: string;
  content_text: string;
  min_level: AccessLevel;
  min_rank: number;
  order_index: number;
  tags_json: string;
  content_hash: string;
  source_uri: string;
  title: string;
  file_name: string;
  updated_at: string;
}

export interface ClauseForIndexing extends ClauseRecord {
  title: string;
}

export class KbRepository {
  async insertDocumentVersion(record: DocumentRecord): Promise<void> {
    await clickhouseGateway.insert('kb_documents', [record]);
  }

  async insertClauseVersions(records: ClauseRecord[]): Promise<void> {
    await clickhouseGateway.insert('kb_clauses', records);
  }

  async getDocumentById(tenantId: string, kbId: string, docId: string): Promise<DocumentRecord | null> {
    return clickhouseGateway.selectOne<DocumentRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, title, source_uri, file_name, file_mime, file_size, file_hash, file_storage_key,
        default_min_level, default_min_rank,
        status, version, is_deleted, created_by, updated_by, created_at, updated_at
      FROM kb_documents FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND doc_id = {doc_id:String}
      LIMIT 1
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        doc_id: docId,
      }
    );
  }

  async listVisibleDocuments(
    tenantId: string,
    kbId: string,
    callerRank: number,
    limit: number,
    offset: number
  ): Promise<DocumentRecord[]> {
    return clickhouseGateway.selectRows<DocumentRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, title, source_uri, file_name, file_mime, file_size, file_hash, file_storage_key,
        default_min_level, default_min_rank,
        status, version, is_deleted, created_by, updated_by, created_at, updated_at
      FROM kb_documents FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND is_deleted = 0
        AND default_min_rank <= {caller_rank:UInt8}
      ORDER BY updated_at DESC, doc_id ASC
      LIMIT {limit:UInt32} OFFSET {offset:UInt32}
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        caller_rank: callerRank,
        limit,
        offset,
      }
    );
  }

  async searchVisibleDocumentsByTitle(
    tenantId: string,
    kbId: string,
    callerRank: number,
    query: string,
    limit: number
  ): Promise<DocumentRecord[]> {
    const normalized = query.trim();
    if (!normalized) return [];
    return clickhouseGateway.selectRows<DocumentRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, title, source_uri, file_name, file_mime, file_size, file_hash, file_storage_key,
        default_min_level, default_min_rank,
        status, version, is_deleted, created_by, updated_by, created_at, updated_at
      FROM kb_documents FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND is_deleted = 0
        AND default_min_rank <= {caller_rank:UInt8}
        AND (title ILIKE {query:String} OR file_name ILIKE {query:String})
      ORDER BY
        if(lowerUTF8(title) = lowerUTF8({exact:String}), 1, 0) DESC,
        if(lowerUTF8(file_name) = lowerUTF8({exact:String}), 1, 0) DESC,
        updated_at DESC,
        doc_id ASC
      LIMIT {limit:UInt32}
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        caller_rank: callerRank,
        query: `%${normalized}%`,
        exact: normalized,
        limit,
      }
    );
  }

  async countVisibleDocuments(tenantId: string, kbId: string, callerRank: number): Promise<number> {
    const row = await clickhouseGateway.selectOne<{ count: number }>(
      `
      SELECT count() AS count
      FROM kb_documents FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND is_deleted = 0
        AND default_min_rank <= {caller_rank:UInt8}
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        caller_rank: callerRank,
      }
    );
    return row?.count ?? 0;
  }

  async getClauseById(
    tenantId: string,
    kbId: string,
    docId: string,
    clauseId: string
  ): Promise<ClauseRecord | null> {
    return clickhouseGateway.selectOne<ClauseRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, clause_id, field_path, content_text, min_level, min_rank, order_index,
        tags_json, content_hash, vector_status, vector_error, status, version, inherits_default,
        is_deleted, created_at, updated_at
      FROM kb_clauses FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND doc_id = {doc_id:String}
        AND clause_id = {clause_id:String}
      LIMIT 1
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        doc_id: docId,
        clause_id: clauseId,
      }
    );
  }

  async getClauseForIndexing(
    tenantId: string,
    kbId: string,
    docId: string,
    clauseId: string
  ): Promise<ClauseForIndexing | null> {
    return clickhouseGateway.selectOne<ClauseForIndexing>(
      `
      SELECT
        c.tenant_id, c.kb_id, c.doc_id, c.clause_id, c.field_path, c.content_text, c.min_level, c.min_rank, c.order_index,
        c.tags_json, c.content_hash, c.vector_status, c.vector_error, c.status, c.version, c.inherits_default,
        c.is_deleted, c.created_at, c.updated_at,
        d.title
      FROM (
        SELECT
          tenant_id, kb_id, doc_id, clause_id, field_path, content_text, min_level, min_rank, order_index,
          tags_json, content_hash, vector_status, vector_error, status, version, inherits_default,
          is_deleted, created_at, updated_at
        FROM kb_clauses FINAL
      ) AS c
      INNER JOIN (
        SELECT tenant_id, kb_id, doc_id, title, is_deleted
        FROM kb_documents FINAL
      ) AS d
        ON c.tenant_id = d.tenant_id
       AND c.kb_id = d.kb_id
       AND c.doc_id = d.doc_id
      WHERE c.tenant_id = {tenant_id:String}
        AND c.kb_id = {kb_id:String}
        AND c.doc_id = {doc_id:String}
        AND c.clause_id = {clause_id:String}
        AND d.is_deleted = 0
      LIMIT 1
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        doc_id: docId,
        clause_id: clauseId,
      }
    );
  }

  async listClausesByDocument(
    tenantId: string,
    kbId: string,
    docId: string,
    callerRank: number
  ): Promise<ClauseRecord[]> {
    return clickhouseGateway.selectRows<ClauseRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, clause_id, field_path, content_text, min_level, min_rank, order_index,
        tags_json, content_hash, vector_status, vector_error, status, version, inherits_default,
        is_deleted, created_at, updated_at
      FROM kb_clauses FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND doc_id = {doc_id:String}
        AND is_deleted = 0
        AND min_rank <= {caller_rank:UInt8}
      ORDER BY order_index ASC, clause_id ASC
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        doc_id: docId,
        caller_rank: callerRank,
      }
    );
  }

  async listAllActiveClausesByDocument(tenantId: string, kbId: string, docId: string): Promise<ClauseRecord[]> {
    return clickhouseGateway.selectRows<ClauseRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, clause_id, field_path, content_text, min_level, min_rank, order_index,
        tags_json, content_hash, vector_status, vector_error, status, version, inherits_default,
        is_deleted, created_at, updated_at
      FROM kb_clauses FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND doc_id = {doc_id:String}
        AND is_deleted = 0
      ORDER BY order_index ASC, clause_id ASC
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        doc_id: docId,
      }
    );
  }

  async listActiveClausesByKBScope(
    tenantId: string,
    kbId: string,
    maxRank: number,
    limit: number
  ): Promise<ClauseRecord[]> {
    return clickhouseGateway.selectRows<ClauseRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, clause_id, field_path, content_text, min_level, min_rank, order_index,
        tags_json, content_hash, vector_status, vector_error, status, version, inherits_default,
        is_deleted, created_at, updated_at
      FROM kb_clauses FINAL
      WHERE tenant_id = {tenant_id:String}
        AND kb_id = {kb_id:String}
        AND is_deleted = 0
        AND min_rank <= {max_rank:UInt8}
      ORDER BY updated_at DESC
      LIMIT {limit:UInt32}
      `,
      {
        tenant_id: tenantId,
        kb_id: kbId,
        max_rank: maxRank,
        limit,
      }
    );
  }

  async fetchClausesByKeys(
    tenantId: string,
    kbId: string,
    callerRank: number,
    keys: Array<{ doc_id: string; clause_id: string }>
  ): Promise<ClauseWithDocMeta[]> {
    if (!keys.length) return [];
    const conditions: string[] = [];
    const params: Record<string, unknown> = {
      tenant_id: tenantId,
      kb_id: kbId,
      caller_rank: callerRank,
    };

    keys.forEach((key, index) => {
      conditions.push(`(c.doc_id = {doc_id_${index}:String} AND c.clause_id = {clause_id_${index}:String})`);
      params[`doc_id_${index}`] = key.doc_id;
      params[`clause_id_${index}`] = key.clause_id;
    });

    return clickhouseGateway.selectRows<ClauseWithDocMeta>(
      `
      SELECT
        c.tenant_id, c.kb_id, c.doc_id, c.clause_id, c.field_path, c.content_text,
        c.min_level, c.min_rank, c.order_index, c.tags_json, c.content_hash,
        d.source_uri, d.title, d.file_name, c.updated_at
      FROM (
        SELECT
          tenant_id, kb_id, doc_id, clause_id, field_path, content_text,
          min_level, min_rank, order_index, tags_json, content_hash, is_deleted, updated_at
        FROM kb_clauses FINAL
      ) AS c
      INNER JOIN (
        SELECT
          tenant_id, kb_id, doc_id, source_uri, title, file_name, is_deleted
        FROM kb_documents FINAL
      ) AS d
        ON c.tenant_id = d.tenant_id
       AND c.kb_id = d.kb_id
       AND c.doc_id = d.doc_id
      WHERE c.tenant_id = {tenant_id:String}
        AND c.kb_id = {kb_id:String}
        AND c.is_deleted = 0
        AND c.min_rank <= {caller_rank:UInt8}
        AND d.is_deleted = 0
        AND (${conditions.join(' OR ')})
      `,
      params
    );
  }

  async lexicalSearchClauses(
    tenantId: string,
    kbId: string,
    callerRank: number,
    searchTerms: string[],
    limit: number,
    filters?: {
      doc_ids?: string[];
      field_paths?: string[];
      tags?: string[];
    }
  ): Promise<ClauseWithDocMeta[]> {
    if (!searchTerms.length) return [];

    const termConditions: string[] = [];
    const termHitParts: string[] = [];
    const fieldHitParts: string[] = [];
    const titleHitParts: string[] = [];
    const params: Record<string, unknown> = {
      tenant_id: tenantId,
      kb_id: kbId,
      caller_rank: callerRank,
      limit,
    };
    searchTerms.forEach((term, index) => {
      const key = `term_${index}`;
      params[key] = `%${term}%`;
      termConditions.push(`(c.content_text ILIKE {${key}:String} OR c.field_path ILIKE {${key}:String})`);
      termHitParts.push(`if(c.content_text ILIKE {${key}:String} OR c.field_path ILIKE {${key}:String} OR d.title ILIKE {${key}:String}, 1, 0)`);
      fieldHitParts.push(`if(c.field_path ILIKE {${key}:String}, 1, 0)`);
      titleHitParts.push(`if(d.title ILIKE {${key}:String}, 1, 0)`);
    });

    const extraConditions: string[] = [];
    if (filters?.doc_ids?.length) {
      filters.doc_ids.forEach((docId, index) => {
        params[`doc_filter_${index}`] = docId;
      });
      extraConditions.push(
        `c.doc_id IN (${filters.doc_ids.map((_, index) => `{doc_filter_${index}:String}`).join(', ')})`
      );
    }
    if (filters?.field_paths?.length) {
      filters.field_paths.forEach((fieldPath, index) => {
        params[`field_filter_${index}`] = fieldPath;
      });
      extraConditions.push(
        `c.field_path IN (${filters.field_paths.map((_, index) => `{field_filter_${index}:String}`).join(', ')})`
      );
    }
    if (filters?.tags?.length) {
      filters.tags.forEach((tag, index) => {
        params[`tag_filter_${index}`] = `%${tag}%`;
      });
      extraConditions.push(
        `(${filters.tags.map((_, index) => `c.tags_json ILIKE {tag_filter_${index}:String}`).join(' OR ')})`
      );
    }

    return clickhouseGateway.selectRows<ClauseWithDocMeta>(
      `
      SELECT
        c.tenant_id, c.kb_id, c.doc_id, c.clause_id, c.field_path, c.content_text,
        c.min_level, c.min_rank, c.order_index, c.tags_json, c.content_hash,
        d.source_uri, d.title, d.file_name, c.updated_at
      FROM (
        SELECT
          tenant_id, kb_id, doc_id, clause_id, field_path, content_text,
          min_level, min_rank, order_index, tags_json, content_hash, is_deleted, updated_at
        FROM kb_clauses FINAL
      ) AS c
      INNER JOIN (
        SELECT
          tenant_id, kb_id, doc_id, source_uri, title, file_name, is_deleted
        FROM kb_documents FINAL
      ) AS d
        ON c.tenant_id = d.tenant_id
       AND c.kb_id = d.kb_id
       AND c.doc_id = d.doc_id
      WHERE c.tenant_id = {tenant_id:String}
        AND c.kb_id = {kb_id:String}
        AND c.is_deleted = 0
        AND d.is_deleted = 0
        AND c.min_rank <= {caller_rank:UInt8}
        AND (${termConditions.join(' OR ')})
        ${extraConditions.length ? `AND ${extraConditions.join(' AND ')}` : ''}
      ORDER BY
        (${termHitParts.join(' + ')}) DESC,
        (${fieldHitParts.join(' + ')}) DESC,
        (${titleHitParts.join(' + ')}) DESC,
        c.updated_at DESC
      LIMIT {limit:UInt32}
      `,
      params
    );
  }

  async createJobs(
    jobs: Array<
      Pick<IndexJobRecord, 'job_id' | 'job_type' | 'tenant_id' | 'kb_id' | 'doc_id' | 'clause_id' | 'payload_json'>
    >
  ): Promise<IndexJobRecord[]> {
    if (!jobs.length) return [];
    const timestamp = nowIso();
    const records: IndexJobRecord[] = jobs.map((job) => ({
      ...job,
      revision: 1,
      status: 'pending',
      retry_count: 0,
      next_run_at: timestamp,
      last_error: '',
      created_at: timestamp,
      updated_at: timestamp,
    }));
    await clickhouseGateway.insert('kb_index_jobs', records);
    return records;
  }

  async insertPreview(record: IngestPreviewRecord): Promise<void> {
    await clickhouseGateway.insert('kb_ingest_previews', [record]);
  }

  async getPreviewById(tenantId: string, previewId: string): Promise<IngestPreviewRecord | null> {
    return clickhouseGateway.selectOne<IngestPreviewRecord>(
      `
      SELECT
        preview_id, tenant_id, kb_id, file_hash, file_name, file_mime, file_size,
        temp_file_key, preview_token_hash, status, expires_at, created_at, updated_at
      FROM kb_ingest_previews FINAL
      WHERE tenant_id = {tenant_id:String}
        AND preview_id = {preview_id:String}
      LIMIT 1
      `,
      {
        tenant_id: tenantId,
        preview_id: previewId,
      }
    );
  }

  async updatePreviewStatus(
    tenantId: string,
    previewId: string,
    status: IngestPreviewRecord['status']
  ): Promise<IngestPreviewRecord | null> {
    const existing = await this.getPreviewById(tenantId, previewId);
    if (!existing) return null;
    const next: IngestPreviewRecord = {
      ...existing,
      status,
      updated_at: nowIso(),
    };
    await this.insertPreview(next);
    return next;
  }

  async listExpiredPendingPreviews(limit = 100): Promise<IngestPreviewRecord[]> {
    return clickhouseGateway.selectRows<IngestPreviewRecord>(
      `
      SELECT
        preview_id, tenant_id, kb_id, file_hash, file_name, file_mime, file_size,
        temp_file_key, preview_token_hash, status, expires_at, created_at, updated_at
      FROM kb_ingest_previews FINAL
      WHERE status = 'pending'
        AND expires_at <= now64(3)
      ORDER BY expires_at ASC
      LIMIT {limit:UInt32}
      `,
      { limit }
    );
  }

  async getJobLatest(jobId: string): Promise<IndexJobRecord | null> {
    return clickhouseGateway.selectOne<IndexJobRecord>(
      `
      SELECT
        job_id, revision, job_type, tenant_id, kb_id, doc_id, clause_id, payload_json,
        status, retry_count, next_run_at, last_error, created_at, updated_at
      FROM kb_index_jobs
      WHERE job_id = {job_id:String}
      ORDER BY revision DESC
      LIMIT 1
      `,
      { job_id: jobId }
    );
  }

  async listRunnableJobs(limit: number): Promise<IndexJobRecord[]> {
    return clickhouseGateway.selectRows<IndexJobRecord>(
      `
      SELECT
        job_id, revision, job_type, tenant_id, kb_id, doc_id, clause_id, payload_json,
        status, retry_count, next_run_at, last_error, created_at, updated_at
      FROM (
        SELECT
          job_id, revision, job_type, tenant_id, kb_id, doc_id, clause_id, payload_json,
          status, retry_count, next_run_at, last_error, created_at, updated_at,
          row_number() OVER (PARTITION BY job_id ORDER BY revision DESC) AS rn
        FROM kb_index_jobs
      ) latest
      WHERE rn = 1
        AND status IN ('pending', 'failed')
        AND next_run_at <= now64(3)
      ORDER BY next_run_at ASC, created_at ASC
      LIMIT {limit:UInt32}
      `,
      { limit }
    );
  }

  async appendJobRevision(
    base: IndexJobRecord,
    patch: Partial<Pick<IndexJobRecord, 'status' | 'retry_count' | 'next_run_at' | 'last_error' | 'payload_json'>>
  ): Promise<IndexJobRecord> {
    const next: IndexJobRecord = {
      ...base,
      revision: base.revision + 1,
      status: patch.status ?? base.status,
      retry_count: patch.retry_count ?? base.retry_count,
      next_run_at: patch.next_run_at ?? base.next_run_at,
      last_error: patch.last_error ?? base.last_error,
      payload_json: patch.payload_json ?? base.payload_json,
      updated_at: nowIso(),
    };
    await clickhouseGateway.insert('kb_index_jobs', [next]);
    return next;
  }

  async insertAuditLog(log: AuditLogRecord): Promise<void> {
    await clickhouseGateway.insert('kb_audit_logs', [log]);
  }

  async listClausesForScopeReindex(
    tenantId: string,
    kbId: string | undefined,
    docId: string | undefined,
    clauseId: string | undefined,
    maxRank: number
  ): Promise<ClauseRecord[]> {
    const params: Record<string, unknown> = {
      tenant_id: tenantId,
      max_rank: maxRank,
    };
    const conditions: string[] = [
      'tenant_id = {tenant_id:String}',
      'is_deleted = 0',
      'min_rank <= {max_rank:UInt8}',
    ];
    if (kbId) {
      conditions.push('kb_id = {kb_id:String}');
      params.kb_id = kbId;
    }
    if (docId) {
      conditions.push('doc_id = {doc_id:String}');
      params.doc_id = docId;
    }
    if (clauseId) {
      conditions.push('clause_id = {clause_id:String}');
      params.clause_id = clauseId;
    }
    return clickhouseGateway.selectRows<ClauseRecord>(
      `
      SELECT
        tenant_id, kb_id, doc_id, clause_id, field_path, content_text, min_level, min_rank, order_index,
        tags_json, content_hash, vector_status, vector_error, status, version, inherits_default,
        is_deleted, created_at, updated_at
      FROM kb_clauses FINAL
      WHERE ${conditions.join(' AND ')}
      `,
      params
    );
  }

  async duplicateClauseWithVectorState(
    clause: ClauseRecord,
    status: ClauseRecord['vector_status'],
    error: string
  ): Promise<void> {
    const next: ClauseRecord = {
      ...clause,
      vector_status: status,
      vector_error: error,
      updated_at: nowIso(),
    };
    await this.insertClauseVersions([next]);
  }

  async ensureSchemaFromSql(sql: string): Promise<void> {
    const statements = sql
      .split(';')
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    for (const statement of statements) {
      await clickhouseGateway.command(statement);
    }
  }

  async ensureLegacySchemaCompatibility(): Promise<void> {
    const statements = [
      `ALTER TABLE kb_clauses ADD COLUMN IF NOT EXISTS order_index UInt32 DEFAULT 0`,
      `ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS file_name String DEFAULT ''`,
      `ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS file_mime String DEFAULT 'application/octet-stream'`,
      `ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS file_size UInt64 DEFAULT 0`,
      `ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS file_hash String DEFAULT ''`,
      `ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS file_storage_key String DEFAULT ''`,
    ];
    for (const statement of statements) {
      await clickhouseGateway.command(statement);
    }
  }

  parseTags(tagsJson: string): string[] {
    try {
      const parsed = JSON.parse(tagsJson);
      return Array.isArray(parsed) ? parsed.map((item) => String(item)) : [];
    } catch {
      return [];
    }
  }

  toClauseRecord(input: {
    tenant_id: string;
    kb_id: string;
    doc_id: string;
    clause_id: string;
    field_path: string;
    content_text: string;
    min_level: AccessLevel;
    min_rank: number;
    order_index: number;
    tags: string[];
    content_hash: string;
    vector_status: ClauseRecord['vector_status'];
    vector_error?: string;
    status?: string;
    version: number;
    inherits_default: number;
    is_deleted: number;
    created_at: string;
    updated_at: string;
  }): ClauseRecord {
    return {
      tenant_id: input.tenant_id,
      kb_id: input.kb_id,
      doc_id: input.doc_id,
      clause_id: input.clause_id,
      field_path: input.field_path,
      content_text: input.content_text,
      min_level: input.min_level,
      min_rank: input.min_rank,
      order_index: input.order_index,
      tags_json: sanitizeJson(input.tags),
      content_hash: input.content_hash,
      vector_status: input.vector_status,
      vector_error: input.vector_error ?? '',
      status: input.status ?? 'active',
      version: input.version,
      inherits_default: input.inherits_default,
      is_deleted: input.is_deleted,
      created_at: input.created_at,
      updated_at: input.updated_at,
    };
  }
}

export const kbRepository = new KbRepository();
