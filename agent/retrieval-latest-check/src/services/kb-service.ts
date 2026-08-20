import { z } from 'zod';
import { config } from '../config';
import { kbRepository, type ClauseWithDocMeta } from '../db/repository';
import type { AccessLevel } from '../models/access';
import { levelToRank } from '../models/access';
import type {
  CallerContext,
  ClauseInput,
  DocumentRecord,
  IngestPreviewRecord,
  RetrieveItem,
} from '../models/contracts';
import { ensureCanWriteLevel, ensureDocumentVisibleOr404, ensureWritableContext } from '../permissions';
import { ApiError } from '../utils/errors';
import { sha256 } from '../utils/hash';
import { newId } from '../utils/id';
import { parseDocumentForPreview } from './document-parser';
import { commitPreviewFile, readStoredFile, removePreviewFile, savePreviewFile } from './file-storage';
import { generateEmbedding } from './embedding';
import { searchClauseVectors, type QdrantSearchResult } from './qdrant';

const accessLevelSchema = z.enum(['driver', 'fleet', 'company', 'group']);

const createClauseSchema = z.object({
  clause_id: z.string().min(1).optional(),
  field_path: z.string().min(1),
  content: z.string().min(1),
  min_level: accessLevelSchema.optional(),
  tags: z.array(z.string().min(1)).optional(),
  order_index: z.number().int().min(0).optional(),
});

const createDocumentSchema = z.object({
  kb_id: z.string().min(1),
  doc_id: z.string().min(1).optional(),
  title: z.string().min(1),
  source_uri: z.string().default(''),
  file_name: z.string().default(''),
  file_mime: z.string().default('application/octet-stream'),
  file_size: z.number().int().nonnegative().default(0),
  file_hash: z.string().default(''),
  file_storage_key: z.string().default(''),
  default_min_level: accessLevelSchema.default('driver'),
  status: z.string().default('active'),
  clauses: z.array(createClauseSchema).default([]),
});

const patchDocumentSchema = z.object({
  kb_id: z.string().min(1),
  title: z.string().min(1).optional(),
  source_uri: z.string().optional(),
  default_min_level: accessLevelSchema.optional(),
  status: z.string().optional(),
});

const batchUpsertSchema = z.object({
  kb_id: z.string().min(1),
  clauses: z.array(createClauseSchema).min(1),
});

const reindexSchema = z.object({
  scope: z.enum(['kb', 'document', 'clause', 'all']),
  kb_id: z.string().optional(),
  doc_id: z.string().optional(),
  clause_id: z.string().optional(),
});

const retrieveSchema = z.object({
  kb_id: z.string().min(1),
  query: z.string().min(1),
  top_k: z.number().int().min(1).max(50).optional(),
  filters: z
    .object({
      doc_ids: z.array(z.string().min(1)).optional(),
      field_paths: z.array(z.string().min(1)).optional(),
      tags: z.array(z.string().min(1)).optional(),
    })
    .optional(),
});

const splitOptionsSchema = z
  .object({
    min_clause_chars: z.number().int().min(20).max(5000).optional(),
    max_clause_chars: z.number().int().min(50).max(10000).optional(),
  })
  .optional();

const previewCommitPayloadSchema = z.object({
  kb_id: z.string().min(1),
  title: z.string().min(1),
  source_uri: z.string().optional().default(''),
  default_min_level: accessLevelSchema,
  file_hash: z.string().min(1),
  clauses: z.array(createClauseSchema).min(1),
});

const commitDocumentSchema = z.object({
  preview_id: z.string().min(1),
  preview_token: z.string().min(1),
  payload: previewCommitPayloadSchema,
});

const replaceDocumentSchema = commitDocumentSchema;

export interface PreviewUploadInput {
  kb_id: string;
  title?: string;
  default_min_level: AccessLevel;
  file_name: string;
  file_mime: string;
  file_size: number;
  content: Buffer;
  split_options?: z.infer<typeof splitOptionsSchema>;
}

function nowIso(): string {
  return new Date().toISOString();
}

function normalizeTags(tags: unknown): string[] {
  if (!Array.isArray(tags)) return [];
  return tags.map((item) => String(item).trim()).filter((item) => item.length > 0);
}

function safeFileName(value: string): string {
  return value.replace(/[\\/:*?"<>|]/g, '_').trim() || 'file';
}

function ensureClauseLimit(clauses: unknown[]): void {
  if (clauses.length > config.maxClausesPerDocument) {
    throw new ApiError(
      400,
      'TOO_MANY_CLAUSES',
      `Clause count exceeds limit ${config.maxClausesPerDocument}`
    );
  }
}

function toDocumentResponse(document: DocumentRecord) {
  return {
    tenant_id: document.tenant_id,
    kb_id: document.kb_id,
    doc_id: document.doc_id,
    title: document.title,
    source_uri: document.source_uri,
    file_name: document.file_name,
    file_mime: document.file_mime,
    file_size: document.file_size,
    file_hash: document.file_hash,
    file_storage_key: document.file_storage_key,
    default_min_level: document.default_min_level,
    status: document.status,
    version: document.version,
    created_at: document.created_at,
    updated_at: document.updated_at,
  };
}

async function writeAudit(
  caller: CallerContext,
  params: {
    action: string;
    resource_type: string;
    resource_id: string;
    result: 'success' | 'failed';
    details?: Record<string, unknown>;
  }
): Promise<void> {
  try {
    await kbRepository.insertAuditLog({
      event_id: newId('audit'),
      tenant_id: caller.tenant_id,
      actor_level: caller.caller_level,
      actor_id: caller.caller_id,
      action: params.action,
      resource_type: params.resource_type,
      resource_id: params.resource_id,
      request_id: caller.request_id,
      result: params.result,
      details_json: JSON.stringify(params.details ?? {}),
      created_at: nowIso(),
    });
  } catch {
    // Audit failures should not block business request flow.
  }
}

function buildClauseJobPayload(input: {
  reason: string;
  doc_version: number;
  clause_version: number;
}): string {
  return JSON.stringify(input);
}

function splitKeywordQuery(value: string): string[] {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return [];
  return normalized
    .split(/[\s,，。；;、]+/g)
    .map((word) => word.trim())
    .filter((word) => word.length >= 2)
    .slice(0, 8);
}

function mapClauseResult(row: ClauseWithDocMeta, score: number, tags: string[]): RetrieveItem {
  return {
    doc_id: row.doc_id,
    clause_id: row.clause_id,
    field_path: row.field_path,
    content: row.content_text,
    score,
    min_level: row.min_level,
    metadata: {
      title: row.title,
      source_uri: row.source_uri,
      tags,
      file_name: row.file_name,
      order_index: row.order_index,
    },
  };
}

function buildClauseRecord(input: {
  caller: CallerContext;
  kb_id: string;
  doc_id: string;
  clause: ClauseInput;
  order_index: number;
  default_min_level: AccessLevel;
  version: number;
  inherits_default: number;
  created_at: string;
  updated_at: string;
  is_deleted: number;
  vector_status: 'pending' | 'ready' | 'failed' | 'deleted';
  status: string;
}) {
  const minLevel = input.clause.min_level ?? input.default_min_level;
  ensureCanWriteLevel(input.caller, minLevel);
  return kbRepository.toClauseRecord({
    tenant_id: input.caller.tenant_id,
    kb_id: input.kb_id,
    doc_id: input.doc_id,
    clause_id: input.clause.clause_id ?? newId('clause'),
    field_path: input.clause.field_path,
    content_text: input.clause.content,
    min_level: minLevel,
    min_rank: levelToRank(minLevel),
    order_index: input.order_index,
    tags: normalizeTags(input.clause.tags),
    content_hash: sha256(input.clause.content),
    vector_status: input.vector_status,
    vector_error: '',
    status: input.status,
    version: input.version,
    inherits_default: input.inherits_default,
    is_deleted: input.is_deleted,
    created_at: input.created_at,
    updated_at: input.updated_at,
  });
}

async function consumePreviewOrThrow(input: {
  caller: CallerContext;
  preview_id: string;
  preview_token: string;
  expected_file_hash: string;
  expected_kb_id: string;
}): Promise<IngestPreviewRecord> {
  const preview = await kbRepository.getPreviewById(input.caller.tenant_id, input.preview_id);
  if (!preview) {
    throw new ApiError(400, 'PREVIEW_MISMATCH', 'Preview session mismatch');
  }
  if (preview.status === 'committed') {
    throw new ApiError(409, 'PREVIEW_ALREADY_USED', 'Preview session already used');
  }
  if (preview.status === 'expired' || Date.parse(preview.expires_at) <= Date.now()) {
    await kbRepository.updatePreviewStatus(input.caller.tenant_id, input.preview_id, 'expired');
    throw new ApiError(409, 'PREVIEW_EXPIRED', 'Preview session expired');
  }
  const tokenHash = sha256(input.preview_token);
  if (
    tokenHash !== preview.preview_token_hash ||
    preview.file_hash !== input.expected_file_hash ||
    preview.kb_id !== input.expected_kb_id
  ) {
    throw new ApiError(400, 'PREVIEW_MISMATCH', 'Preview session mismatch');
  }
  return preview;
}

function assertFileSize(size: number): void {
  if (size > config.maxFileSizeBytes) {
    throw new ApiError(
      400,
      'FILE_TOO_LARGE',
      `File size exceeds limit ${config.maxFileSizeBytes} bytes`
    );
  }
}

async function expireStalePreviews(): Promise<void> {
  const previews = await kbRepository.listExpiredPendingPreviews(50);
  if (!previews.length) return;
  await Promise.all(
    previews.map(async (preview) => {
      await kbRepository.updatePreviewStatus(preview.tenant_id, preview.preview_id, 'expired');
      await removePreviewFile(preview.temp_file_key).catch(() => undefined);
    })
  );
}

export async function previewDocument(caller: CallerContext, payload: PreviewUploadInput) {
  ensureWritableContext(caller);
  ensureCanWriteLevel(caller, payload.default_min_level);
  await expireStalePreviews();
  assertFileSize(payload.file_size);

  const kbId = payload.kb_id || config.defaultKbId;
  const previewParsed = await parseDocumentForPreview({
    file_name: payload.file_name,
    file_mime: payload.file_mime,
    content: payload.content,
    split_options: splitOptionsSchema.parse(payload.split_options),
  });
  ensureClauseLimit(previewParsed.clauses);

  const previewId = newId('preview');
  const previewToken = newId('preview_token');
  const fileHash = sha256(payload.content);
  const expiresAt = new Date(Date.now() + config.previewTtlSeconds * 1000).toISOString();
  const tempFileKey = await savePreviewFile({
    preview_id: previewId,
    file_name: payload.file_name,
    content: payload.content,
  });

  await kbRepository.insertPreview({
    preview_id: previewId,
    tenant_id: caller.tenant_id,
    kb_id: kbId,
    file_hash: fileHash,
    file_name: payload.file_name,
    file_mime: payload.file_mime,
    file_size: payload.file_size,
    temp_file_key: tempFileKey,
    preview_token_hash: sha256(previewToken),
    status: 'pending',
    expires_at: expiresAt,
    created_at: nowIso(),
    updated_at: nowIso(),
  });

  return {
    statusCode: 200,
    data: {
      preview: {
        file_name: payload.file_name,
        file_mime: payload.file_mime,
        file_size: payload.file_size,
        warnings: previewParsed.warnings,
        clauses: previewParsed.clauses.map((clause, index) => ({
          clause_id: `preview_clause_${index + 1}`,
          field_path: clause.field_path,
          content: clause.content,
          min_level: payload.default_min_level,
          tags: clause.tags,
          order_index: index + 1,
        })),
        preview_id: previewId,
        preview_token: previewToken,
        file_hash: fileHash,
        expires_at: expiresAt,
      },
    },
  };
}

export async function commitDocument(caller: CallerContext, payload: unknown) {
  ensureWritableContext(caller);
  const body = commitDocumentSchema.parse(payload);
  ensureCanWriteLevel(caller, body.payload.default_min_level);
  ensureClauseLimit(body.payload.clauses);

  const preview = await consumePreviewOrThrow({
    caller,
    preview_id: body.preview_id,
    preview_token: body.preview_token,
    expected_file_hash: body.payload.file_hash,
    expected_kb_id: body.payload.kb_id,
  });

  const now = nowIso();
  const docId = newId('doc');
  const finalFileKey = `${body.payload.kb_id}/${docId}/${Date.now()}_${safeFileName(preview.file_name)}`;

  const document: DocumentRecord = {
    tenant_id: caller.tenant_id,
    kb_id: body.payload.kb_id,
    doc_id: docId,
    title: body.payload.title,
    source_uri: body.payload.source_uri ?? '',
    file_name: preview.file_name,
    file_mime: preview.file_mime,
    file_size: preview.file_size,
    file_hash: preview.file_hash,
    file_storage_key: finalFileKey,
    default_min_level: body.payload.default_min_level,
    default_min_rank: levelToRank(body.payload.default_min_level),
    status: 'active',
    version: 1,
    is_deleted: 0,
    created_by: caller.caller_id,
    updated_by: caller.caller_id,
    created_at: now,
    updated_at: now,
  };

  const clauseRecords = body.payload.clauses.map((clause, index) =>
    buildClauseRecord({
      caller,
      kb_id: body.payload.kb_id,
      doc_id: docId,
      clause,
      order_index: index + 1,
      default_min_level: body.payload.default_min_level,
      version: 1,
      inherits_default: clause.min_level ? 0 : 1,
      created_at: now,
      updated_at: now,
      is_deleted: 0,
      vector_status: 'pending',
      status: 'active',
    })
  );

  await kbRepository.insertDocumentVersion(document);
  await kbRepository.insertClauseVersions(clauseRecords);
  const jobs = await kbRepository.createJobs(
    clauseRecords.map((row) => ({
      job_id: newId('job'),
      job_type: 'upsert',
      tenant_id: row.tenant_id,
      kb_id: row.kb_id,
      doc_id: row.doc_id,
      clause_id: row.clause_id,
      payload_json: buildClauseJobPayload({
        reason: 'document_commit',
        doc_version: document.version,
        clause_version: row.version,
      }),
    }))
  );

  await commitPreviewFile(preview.temp_file_key, finalFileKey);
  await kbRepository.updatePreviewStatus(caller.tenant_id, body.preview_id, 'committed');

  await writeAudit(caller, {
    action: 'document.commit',
    resource_type: 'document',
    resource_id: `${body.payload.kb_id}/${docId}`,
    result: 'success',
    details: {
      clause_count: clauseRecords.length,
      job_count: jobs.length,
    },
  });

  return {
    statusCode: 202,
    data: {
      document: toDocumentResponse(document),
      job_ids: jobs.map((item) => item.job_id),
    },
  };
}

export async function replaceDocument(caller: CallerContext, docId: string, payload: unknown) {
  ensureWritableContext(caller);
  const body = replaceDocumentSchema.parse(payload);
  ensureCanWriteLevel(caller, body.payload.default_min_level);
  ensureClauseLimit(body.payload.clauses);

  const existingDocument = await kbRepository.getDocumentById(caller.tenant_id, body.payload.kb_id, docId);
  if (!existingDocument || existingDocument.is_deleted === 1) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
  ensureDocumentVisibleOr404(caller, existingDocument.default_min_rank);
  ensureCanWriteLevel(caller, existingDocument.default_min_level);

  const preview = await consumePreviewOrThrow({
    caller,
    preview_id: body.preview_id,
    preview_token: body.preview_token,
    expected_file_hash: body.payload.file_hash,
    expected_kb_id: body.payload.kb_id,
  });

  const now = nowIso();
  const finalFileKey = `${body.payload.kb_id}/${docId}/${Date.now()}_${safeFileName(preview.file_name)}`;

  const replacedDocument: DocumentRecord = {
    ...existingDocument,
    title: body.payload.title,
    source_uri: body.payload.source_uri ?? '',
    file_name: preview.file_name,
    file_mime: preview.file_mime,
    file_size: preview.file_size,
    file_hash: preview.file_hash,
    file_storage_key: finalFileKey,
    default_min_level: body.payload.default_min_level,
    default_min_rank: levelToRank(body.payload.default_min_level),
    version: existingDocument.version + 1,
    updated_by: caller.caller_id,
    updated_at: now,
  };
  await kbRepository.insertDocumentVersion(replacedDocument);

  const activeClauses = await kbRepository.listAllActiveClausesByDocument(caller.tenant_id, body.payload.kb_id, docId);
  const deletedClauseRows = activeClauses.map((clause) =>
    kbRepository.toClauseRecord({
      tenant_id: clause.tenant_id,
      kb_id: clause.kb_id,
      doc_id: clause.doc_id,
      clause_id: clause.clause_id,
      field_path: clause.field_path,
      content_text: clause.content_text,
      min_level: clause.min_level,
      min_rank: clause.min_rank,
      order_index: clause.order_index,
      tags: kbRepository.parseTags(clause.tags_json),
      content_hash: clause.content_hash,
      vector_status: 'deleted',
      vector_error: '',
      status: 'inactive',
      version: clause.version + 1,
      inherits_default: clause.inherits_default,
      is_deleted: 1,
      created_at: clause.created_at,
      updated_at: now,
    })
  );
  if (deletedClauseRows.length > 0) {
    await kbRepository.insertClauseVersions(deletedClauseRows);
  }
  const deleteJobs = await kbRepository.createJobs(
    deletedClauseRows.map((row) => ({
      job_id: newId('job'),
      job_type: 'delete',
      tenant_id: row.tenant_id,
      kb_id: row.kb_id,
      doc_id: row.doc_id,
      clause_id: row.clause_id,
      payload_json: buildClauseJobPayload({
        reason: 'document_replace_delete',
        doc_version: replacedDocument.version,
        clause_version: row.version,
      }),
    }))
  );

  const newClauseRows = body.payload.clauses.map((clause, index) =>
    buildClauseRecord({
      caller,
      kb_id: body.payload.kb_id,
      doc_id: docId,
      clause: {
        ...clause,
        clause_id: clause.clause_id || newId('clause'),
      },
      order_index: index + 1,
      default_min_level: body.payload.default_min_level,
      version: 1,
      inherits_default: clause.min_level ? 0 : 1,
      created_at: now,
      updated_at: now,
      is_deleted: 0,
      vector_status: 'pending',
      status: 'active',
    })
  );
  await kbRepository.insertClauseVersions(newClauseRows);

  const upsertJobs = await kbRepository.createJobs(
    newClauseRows.map((row) => ({
      job_id: newId('job'),
      job_type: 'upsert',
      tenant_id: row.tenant_id,
      kb_id: row.kb_id,
      doc_id: row.doc_id,
      clause_id: row.clause_id,
      payload_json: buildClauseJobPayload({
        reason: 'document_replace_upsert',
        doc_version: replacedDocument.version,
        clause_version: row.version,
      }),
    }))
  );

  await commitPreviewFile(preview.temp_file_key, finalFileKey);
  await kbRepository.updatePreviewStatus(caller.tenant_id, body.preview_id, 'committed');

  await writeAudit(caller, {
    action: 'document.replace',
    resource_type: 'document',
    resource_id: `${body.payload.kb_id}/${docId}`,
    result: 'success',
    details: {
      deleted_clause_count: deletedClauseRows.length,
      new_clause_count: newClauseRows.length,
      delete_job_count: deleteJobs.length,
      upsert_job_count: upsertJobs.length,
    },
  });

  return {
    statusCode: 202,
    data: {
      document: toDocumentResponse(replacedDocument),
      deleted_clause_count: deletedClauseRows.length,
      new_clause_count: newClauseRows.length,
      delete_job_ids: deleteJobs.map((item) => item.job_id),
      upsert_job_ids: upsertJobs.map((item) => item.job_id),
    },
  };
}

export async function getDocumentFile(caller: CallerContext, kbId: string, docId: string) {
  const document = await kbRepository.getDocumentById(caller.tenant_id, kbId, docId);
  if (!document || document.is_deleted === 1) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
  ensureDocumentVisibleOr404(caller, document.default_min_rank);
  if (!document.file_storage_key) {
    throw new ApiError(404, 'FILE_NOT_FOUND', 'Document file not found');
  }
  const buffer = await readStoredFile(document.file_storage_key);
  return {
    file_name: document.file_name || `${docId}.txt`,
    file_mime: document.file_mime || 'application/octet-stream',
    file_size: buffer.length,
    buffer,
  };
}

export async function createDocument(caller: CallerContext, payload: unknown) {
  const body = createDocumentSchema.parse(payload);
  ensureWritableContext(caller);
  ensureCanWriteLevel(caller, body.default_min_level);
  ensureClauseLimit(body.clauses);

  const existing = body.doc_id
    ? await kbRepository.getDocumentById(caller.tenant_id, body.kb_id, body.doc_id)
    : null;
  if (existing && existing.is_deleted === 0) {
    throw new ApiError(409, 'DOCUMENT_EXISTS', 'Document already exists');
  }

  const now = nowIso();
  const docId = body.doc_id ?? newId('doc');
  const document: DocumentRecord = {
    tenant_id: caller.tenant_id,
    kb_id: body.kb_id,
    doc_id: docId,
    title: body.title,
    source_uri: body.source_uri,
    file_name: body.file_name,
    file_mime: body.file_mime,
    file_size: body.file_size,
    file_hash: body.file_hash,
    file_storage_key: body.file_storage_key,
    default_min_level: body.default_min_level,
    default_min_rank: levelToRank(body.default_min_level),
    status: body.status,
    version: 1,
    is_deleted: 0,
    created_by: caller.caller_id,
    updated_by: caller.caller_id,
    created_at: now,
    updated_at: now,
  };

  const clauseRecords = body.clauses.map((clause, index) =>
    buildClauseRecord({
      caller,
      kb_id: body.kb_id,
      doc_id: docId,
      clause,
      order_index: clause.order_index ?? index + 1,
      default_min_level: body.default_min_level,
      version: 1,
      inherits_default: clause.min_level ? 0 : 1,
      created_at: now,
      updated_at: now,
      is_deleted: 0,
      vector_status: 'pending',
      status: 'active',
    })
  );

  await kbRepository.insertDocumentVersion(document);
  if (clauseRecords.length) {
    await kbRepository.insertClauseVersions(clauseRecords);
  }
  const jobs = await kbRepository.createJobs(
    clauseRecords.map((row) => ({
      job_id: newId('job'),
      job_type: 'upsert',
      tenant_id: row.tenant_id,
      kb_id: row.kb_id,
      doc_id: row.doc_id,
      clause_id: row.clause_id,
      payload_json: buildClauseJobPayload({
        reason: 'document_create',
        doc_version: document.version,
        clause_version: row.version,
      }),
    }))
  );

  await writeAudit(caller, {
    action: 'document.create',
    resource_type: 'document',
    resource_id: `${body.kb_id}/${docId}`,
    result: 'success',
    details: {
      clause_count: clauseRecords.length,
      job_count: jobs.length,
    },
  });

  return {
    statusCode: 202,
    data: {
      document: toDocumentResponse(document),
      clause_ids: clauseRecords.map((item) => item.clause_id),
      job_ids: jobs.map((item) => item.job_id),
    },
  };
}

export async function patchDocument(caller: CallerContext, docId: string, payload: unknown) {
  const body = patchDocumentSchema.parse(payload);
  ensureWritableContext(caller);

  const existing = await kbRepository.getDocumentById(caller.tenant_id, body.kb_id, docId);
  if (!existing || existing.is_deleted === 1) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
  ensureDocumentVisibleOr404(caller, existing.default_min_rank);
  ensureCanWriteLevel(caller, existing.default_min_level);

  const nextLevel = body.default_min_level ?? existing.default_min_level;
  ensureCanWriteLevel(caller, nextLevel);

  const now = nowIso();
  const nextDoc: DocumentRecord = {
    ...existing,
    title: body.title ?? existing.title,
    source_uri: body.source_uri ?? existing.source_uri,
    default_min_level: nextLevel,
    default_min_rank: levelToRank(nextLevel),
    status: body.status ?? existing.status,
    version: existing.version + 1,
    updated_by: caller.caller_id,
    updated_at: now,
  };
  await kbRepository.insertDocumentVersion(nextDoc);

  const jobsToCreate: Array<{
    job_id: string;
    job_type: 'upsert';
    tenant_id: string;
    kb_id: string;
    doc_id: string;
    clause_id: string;
    payload_json: string;
  }> = [];

  if (nextLevel !== existing.default_min_level) {
    const clauses = await kbRepository.listAllActiveClausesByDocument(caller.tenant_id, body.kb_id, docId);
    const inheritedClauses = clauses.filter((clause) => clause.inherits_default === 1);
    const nextClauseRecords = inheritedClauses.map((clause) =>
      kbRepository.toClauseRecord({
        tenant_id: clause.tenant_id,
        kb_id: clause.kb_id,
        doc_id: clause.doc_id,
        clause_id: clause.clause_id,
        field_path: clause.field_path,
        content_text: clause.content_text,
        min_level: nextLevel,
        min_rank: levelToRank(nextLevel),
        order_index: clause.order_index,
        tags: kbRepository.parseTags(clause.tags_json),
        content_hash: clause.content_hash,
        vector_status: 'pending',
        vector_error: '',
        status: clause.status,
        version: clause.version + 1,
        inherits_default: 1,
        is_deleted: clause.is_deleted,
        created_at: clause.created_at,
        updated_at: now,
      })
    );
    if (nextClauseRecords.length > 0) {
      await kbRepository.insertClauseVersions(nextClauseRecords);
      nextClauseRecords.forEach((row) => {
        jobsToCreate.push({
          job_id: newId('job'),
          job_type: 'upsert',
          tenant_id: row.tenant_id,
          kb_id: row.kb_id,
          doc_id: row.doc_id,
          clause_id: row.clause_id,
          payload_json: buildClauseJobPayload({
            reason: 'default_level_changed',
            doc_version: nextDoc.version,
            clause_version: row.version,
          }),
        });
      });
    }
  }

  const jobs = await kbRepository.createJobs(jobsToCreate);
  await writeAudit(caller, {
    action: 'document.patch',
    resource_type: 'document',
    resource_id: `${body.kb_id}/${docId}`,
    result: 'success',
    details: {
      default_level_changed: nextLevel !== existing.default_min_level,
      job_count: jobs.length,
    },
  });

  return {
    statusCode: 202,
    data: {
      document: toDocumentResponse(nextDoc),
      job_ids: jobs.map((item) => item.job_id),
    },
  };
}

export async function deleteDocument(caller: CallerContext, kbId: string, docId: string) {
  ensureWritableContext(caller);
  const existing = await kbRepository.getDocumentById(caller.tenant_id, kbId, docId);
  if (!existing || existing.is_deleted === 1) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
  ensureDocumentVisibleOr404(caller, existing.default_min_rank);
  ensureCanWriteLevel(caller, existing.default_min_level);

  const now = nowIso();
  const deletedDoc: DocumentRecord = {
    ...existing,
    status: 'inactive',
    is_deleted: 1,
    version: existing.version + 1,
    updated_by: caller.caller_id,
    updated_at: now,
  };
  await kbRepository.insertDocumentVersion(deletedDoc);

  const activeClauses = await kbRepository.listAllActiveClausesByDocument(caller.tenant_id, kbId, docId);
  const deletedClauseRows = activeClauses.map((clause) =>
    kbRepository.toClauseRecord({
      tenant_id: clause.tenant_id,
      kb_id: clause.kb_id,
      doc_id: clause.doc_id,
      clause_id: clause.clause_id,
      field_path: clause.field_path,
      content_text: clause.content_text,
      min_level: clause.min_level,
      min_rank: clause.min_rank,
      order_index: clause.order_index,
      tags: kbRepository.parseTags(clause.tags_json),
      content_hash: clause.content_hash,
      vector_status: 'deleted',
      vector_error: '',
      status: 'inactive',
      version: clause.version + 1,
      inherits_default: clause.inherits_default,
      is_deleted: 1,
      created_at: clause.created_at,
      updated_at: now,
    })
  );
  if (deletedClauseRows.length > 0) {
    await kbRepository.insertClauseVersions(deletedClauseRows);
  }

  const jobs = await kbRepository.createJobs(
    deletedClauseRows.map((row) => ({
      job_id: newId('job'),
      job_type: 'delete',
      tenant_id: row.tenant_id,
      kb_id: row.kb_id,
      doc_id: row.doc_id,
      clause_id: row.clause_id,
      payload_json: buildClauseJobPayload({
        reason: 'document_deleted',
        doc_version: deletedDoc.version,
        clause_version: row.version,
      }),
    }))
  );

  await writeAudit(caller, {
    action: 'document.delete',
    resource_type: 'document',
    resource_id: `${kbId}/${docId}`,
    result: 'success',
    details: {
      clause_count: deletedClauseRows.length,
      job_count: jobs.length,
    },
  });

  return {
    statusCode: 202,
    data: {
      deleted: true,
      job_ids: jobs.map((item) => item.job_id),
    },
  };
}

export async function batchUpsertClauses(caller: CallerContext, docId: string, payload: unknown) {
  const body = batchUpsertSchema.parse(payload);
  ensureWritableContext(caller);
  ensureClauseLimit(body.clauses);

  const document = await kbRepository.getDocumentById(caller.tenant_id, body.kb_id, docId);
  if (!document || document.is_deleted === 1) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
  ensureDocumentVisibleOr404(caller, document.default_min_rank);
  ensureCanWriteLevel(caller, document.default_min_level);

  const now = nowIso();
  const upsertRows = [];
  for (let i = 0; i < body.clauses.length; i += 1) {
    const clause = body.clauses[i];
    const clauseId = clause.clause_id ?? newId('clause');
    const existing = clause.clause_id
      ? await kbRepository.getClauseById(caller.tenant_id, body.kb_id, docId, clauseId)
      : null;
    if (existing && existing.min_rank > caller.caller_rank) {
      throw new ApiError(404, 'CLAUSE_NOT_FOUND', 'Clause not found');
    }
    upsertRows.push(
      buildClauseRecord({
        caller,
        kb_id: body.kb_id,
        doc_id: docId,
        clause: {
          ...clause,
          clause_id: clauseId,
        },
        order_index: clause.order_index ?? existing?.order_index ?? i + 1,
        default_min_level: document.default_min_level,
        version: existing ? existing.version + 1 : 1,
        inherits_default: clause.min_level ? 0 : 1,
        created_at: existing?.created_at ?? now,
        updated_at: now,
        is_deleted: 0,
        vector_status: 'pending',
        status: 'active',
      })
    );
  }

  await kbRepository.insertClauseVersions(upsertRows);
  const jobs = await kbRepository.createJobs(
    upsertRows.map((row) => ({
      job_id: newId('job'),
      job_type: 'upsert',
      tenant_id: row.tenant_id,
      kb_id: row.kb_id,
      doc_id: row.doc_id,
      clause_id: row.clause_id,
      payload_json: buildClauseJobPayload({
        reason: 'batch_upsert',
        doc_version: document.version,
        clause_version: row.version,
      }),
    }))
  );

  await writeAudit(caller, {
    action: 'clause.batch_upsert',
    resource_type: 'document',
    resource_id: `${body.kb_id}/${docId}`,
    result: 'success',
    details: {
      clause_count: upsertRows.length,
      job_count: jobs.length,
    },
  });

  return {
    statusCode: 202,
    data: {
      clause_ids: upsertRows.map((item) => item.clause_id),
      job_ids: jobs.map((item) => item.job_id),
    },
  };
}

export async function deleteClause(caller: CallerContext, kbId: string, docId: string, clauseId: string) {
  ensureWritableContext(caller);
  const document = await kbRepository.getDocumentById(caller.tenant_id, kbId, docId);
  if (!document || document.is_deleted === 1) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
  ensureDocumentVisibleOr404(caller, document.default_min_rank);

  const clause = await kbRepository.getClauseById(caller.tenant_id, kbId, docId, clauseId);
  if (!clause || clause.is_deleted === 1 || clause.min_rank > caller.caller_rank) {
    throw new ApiError(404, 'CLAUSE_NOT_FOUND', 'Clause not found');
  }
  ensureCanWriteLevel(caller, clause.min_level);

  const deletedClause = kbRepository.toClauseRecord({
    tenant_id: clause.tenant_id,
    kb_id: clause.kb_id,
    doc_id: clause.doc_id,
    clause_id: clause.clause_id,
    field_path: clause.field_path,
    content_text: clause.content_text,
    min_level: clause.min_level,
    min_rank: clause.min_rank,
    order_index: clause.order_index,
    tags: kbRepository.parseTags(clause.tags_json),
    content_hash: clause.content_hash,
    vector_status: 'deleted',
    vector_error: '',
    status: 'inactive',
    version: clause.version + 1,
    inherits_default: clause.inherits_default,
    is_deleted: 1,
    created_at: clause.created_at,
    updated_at: nowIso(),
  });
  await kbRepository.insertClauseVersions([deletedClause]);

  const jobs = await kbRepository.createJobs([
    {
      job_id: newId('job'),
      job_type: 'delete',
      tenant_id: deletedClause.tenant_id,
      kb_id: deletedClause.kb_id,
      doc_id: deletedClause.doc_id,
      clause_id: deletedClause.clause_id,
      payload_json: buildClauseJobPayload({
        reason: 'clause_deleted',
        doc_version: document.version,
        clause_version: deletedClause.version,
      }),
    },
  ]);

  await writeAudit(caller, {
    action: 'clause.delete',
    resource_type: 'clause',
    resource_id: `${kbId}/${docId}/${clauseId}`,
    result: 'success',
  });

  return {
    statusCode: 202,
    data: {
      deleted: true,
      job_ids: jobs.map((item) => item.job_id),
    },
  };
}

export async function triggerReindex(caller: CallerContext, payload: unknown) {
  const body = reindexSchema.parse(payload);
  ensureWritableContext(caller);
  if (body.scope === 'all' && caller.caller_level !== 'group') {
    throw new ApiError(403, 'REINDEX_SCOPE_FORBIDDEN', 'Only group level can run scope=all');
  }
  if (body.scope === 'kb' && !body.kb_id) {
    throw new ApiError(400, 'MISSING_KB_ID', 'kb_id is required for scope=kb');
  }
  if (body.scope === 'document' && (!body.kb_id || !body.doc_id)) {
    throw new ApiError(400, 'MISSING_DOC_SCOPE', 'kb_id and doc_id are required for scope=document');
  }
  if (body.scope === 'clause' && (!body.kb_id || !body.doc_id || !body.clause_id)) {
    throw new ApiError(400, 'MISSING_CLAUSE_SCOPE', 'kb_id, doc_id and clause_id are required for scope=clause');
  }

  const clauses = await kbRepository.listClausesForScopeReindex(
    caller.tenant_id,
    body.scope === 'all' ? undefined : body.kb_id,
    body.scope === 'document' || body.scope === 'clause' ? body.doc_id : undefined,
    body.scope === 'clause' ? body.clause_id : undefined,
    caller.caller_rank
  );

  const jobs = await kbRepository.createJobs(
    clauses.map((clause) => ({
      job_id: newId('job'),
      job_type: 'upsert',
      tenant_id: clause.tenant_id,
      kb_id: clause.kb_id,
      doc_id: clause.doc_id,
      clause_id: clause.clause_id,
      payload_json: buildClauseJobPayload({
        reason: `reindex_${body.scope}`,
        doc_version: 0,
        clause_version: clause.version,
      }),
    }))
  );

  await writeAudit(caller, {
    action: 'reindex.trigger',
    resource_type: 'reindex',
    resource_id: body.scope,
    result: 'success',
    details: {
      scope: body.scope,
      selected_clauses: clauses.length,
      job_count: jobs.length,
    },
  });

  return {
    statusCode: 202,
    data: {
      scope: body.scope,
      selected_clauses: clauses.length,
      job_ids: jobs.map((item) => item.job_id),
    },
  };
}

export async function getJob(caller: CallerContext, jobId: string) {
  const job = await kbRepository.getJobLatest(jobId);
  if (!job || job.tenant_id !== caller.tenant_id) {
    throw new ApiError(404, 'JOB_NOT_FOUND', 'Job not found');
  }
  return {
    data: {
      job_id: job.job_id,
      job_type: job.job_type,
      status: job.status,
      retry_count: job.retry_count,
      next_run_at: job.next_run_at,
      last_error: job.last_error,
      updated_at: job.updated_at,
    },
  };
}

export async function listDocuments(caller: CallerContext, kbId: string, limit: number, offset: number) {
  const documents = await kbRepository.listVisibleDocuments(caller.tenant_id, kbId, caller.caller_rank, limit, offset);
  const total = await kbRepository.countVisibleDocuments(caller.tenant_id, kbId, caller.caller_rank);
  return {
    data: {
      items: documents.map(toDocumentResponse),
      total,
      limit,
      offset,
    },
  };
}

export async function getDocument(caller: CallerContext, kbId: string, docId: string, includeClauses: boolean) {
  const document = await kbRepository.getDocumentById(caller.tenant_id, kbId, docId);
  if (!document || document.is_deleted === 1) {
    throw new ApiError(404, 'DOCUMENT_NOT_FOUND', 'Document not found');
  }
  ensureDocumentVisibleOr404(caller, document.default_min_rank);

  const clauses = includeClauses
    ? await kbRepository.listClausesByDocument(caller.tenant_id, kbId, docId, caller.caller_rank)
    : [];

  return {
    data: {
      ...toDocumentResponse(document),
      clauses: clauses.map((clause) => ({
        clause_id: clause.clause_id,
        field_path: clause.field_path,
        content: clause.content_text,
        min_level: clause.min_level,
        tags: kbRepository.parseTags(clause.tags_json),
        order_index: clause.order_index,
        version: clause.version,
      })),
    },
  };
}

function mergeSearchResults(results: QdrantSearchResult[]): Array<{ doc_id: string; clause_id: string; score: number }> {
  const map = new Map<string, { doc_id: string; clause_id: string; score: number }>();
  results.forEach((item) => {
    const payload = item.payload;
    if (!payload) return;
    const key = `${payload.doc_id}::${payload.clause_id}`;
    const current = map.get(key);
    if (!current || item.score > current.score) {
      map.set(key, {
        doc_id: payload.doc_id,
        clause_id: payload.clause_id,
        score: item.score,
      });
    }
  });
  return Array.from(map.values()).sort((a, b) => b.score - a.score);
}

export async function retrieve(caller: CallerContext, payload: unknown) {
  const body = retrieveSchema.parse(payload);
  const topK = Math.min(Math.max(body.top_k ?? 8, 1), 50);
  const queryVector = await generateEmbedding(body.query);
  const vectorResults = await searchClauseVectors({
    tenant_id: caller.tenant_id,
    kb_id: body.kb_id,
    caller_rank: caller.caller_rank,
    vector: queryVector,
    limit: Math.max(topK, config.retrieveTopN),
    filters: body.filters,
  });
  const merged = mergeSearchResults(vectorResults);
  const vectorKeys = merged.map((item) => ({
    doc_id: item.doc_id,
    clause_id: item.clause_id,
  }));
  const clauseRows = await kbRepository.fetchClausesByKeys(
    caller.tenant_id,
    body.kb_id,
    caller.caller_rank,
    vectorKeys
  );

  const scoreByKey = new Map<string, number>();
  merged.forEach((item) => {
    scoreByKey.set(`${item.doc_id}::${item.clause_id}`, item.score);
  });

  const dedup = new Map<string, RetrieveItem>();
  clauseRows.forEach((row) => {
    const key = `${row.doc_id}::${row.clause_id}`;
    const score = scoreByKey.get(key) ?? 0;
    dedup.set(key, mapClauseResult(row, score, kbRepository.parseTags(row.tags_json)));
  });

  if (dedup.size < topK) {
    const lexicalTerms = splitKeywordQuery(body.query);
    const lexicalRows = await kbRepository.lexicalSearchClauses(
      caller.tenant_id,
      body.kb_id,
      caller.caller_rank,
      lexicalTerms,
      topK * 2
    );
    lexicalRows.forEach((row, idx) => {
      const key = `${row.doc_id}::${row.clause_id}`;
      if (dedup.has(key)) return;
      const score = Math.max(0.1, 0.35 - idx * 0.01);
      dedup.set(key, mapClauseResult(row, score, kbRepository.parseTags(row.tags_json)));
    });
  }

  const items = Array.from(dedup.values())
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);

  await writeAudit(caller, {
    action: 'retrieve.search',
    resource_type: 'kb',
    resource_id: body.kb_id,
    result: 'success',
    details: {
      top_k: topK,
      returned_items: items.length,
      query_len: body.query.length,
    },
  });

  return {
    data: {
      items,
    },
  };
}

export const schemas = {
  createDocumentSchema,
  patchDocumentSchema,
  batchUpsertSchema,
  reindexSchema,
  retrieveSchema,
  commitDocumentSchema,
  replaceDocumentSchema,
};
