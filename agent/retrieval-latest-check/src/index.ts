import Fastify from 'fastify';
import multipart from '@fastify/multipart';
import { ZodError } from 'zod';
import { config } from './config';
import { resolveCallerContext } from './auth';
import { ApiError } from './utils/errors';
import {
  batchUpsertClauses,
  commitDocument,
  createDocument,
  deleteClause,
  deleteDocument,
  getDocument,
  getDocumentFile,
  getJob,
  listDocuments,
  patchDocument,
  previewDocument,
  replaceDocument,
  retrieve,
  triggerReindex,
} from './services/kb-service';
import { ensureStorageRoots } from './services/file-storage';
import { ensureQdrantCollection } from './services/qdrant';

const app = Fastify({
  logger: {
    level: config.logLevel,
  },
});

app.setErrorHandler((error, _request, reply) => {
  if ((error as { code?: string }).code === 'FST_REQ_FILE_TOO_LARGE') {
    return reply.status(400).send({
      success: false,
      error: {
        code: 'FILE_TOO_LARGE',
        message: `File size exceeds limit ${config.maxFileSizeBytes} bytes`,
      },
    });
  }
  if (error instanceof ApiError) {
    return reply.status(error.statusCode).send({
      success: false,
      error: {
        code: error.code,
        message: error.message,
      },
    });
  }
  if (error instanceof ZodError) {
    return reply.status(400).send({
      success: false,
      error: {
        code: 'INVALID_PAYLOAD',
        message: error.issues.map((item) => item.message).join('; '),
      },
    });
  }
  app.log.error({ err: error }, 'Unhandled request error');
  return reply.status(500).send({
    success: false,
    error: {
      code: 'INTERNAL_ERROR',
      message: 'Internal server error',
    },
  });
});

app.register(multipart, {
  limits: {
    fileSize: config.maxFileSizeBytes,
    files: 1,
  },
});

function readMultipartField(
  fields: Record<string, any>,
  key: string
): string | undefined {
  const raw = fields[key];
  if (!raw) return undefined;
  const item = Array.isArray(raw) ? raw[0] : raw;
  if (!item) return undefined;
  const value = item.value;
  if (value === undefined || value === null) return undefined;
  const normalized = String(value).trim();
  return normalized || undefined;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function toSafeNonNegativeInt(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(0, Math.floor(value));
  }
  return fallback;
}

function normalizeListDocumentsData(
  data: unknown,
  fallbackLimit: number,
  fallbackOffset: number
): {
  items: unknown[];
  total: number;
  limit: number;
  offset: number;
} {
  const record = asRecord(data);
  const rawItems = record?.items;
  const items = Array.isArray(rawItems) ? rawItems : [];
  const total = toSafeNonNegativeInt(record?.total, items.length);
  const limit = toSafeNonNegativeInt(record?.limit, fallbackLimit);
  const offset = toSafeNonNegativeInt(record?.offset, fallbackOffset);
  return { items, total, limit, offset };
}

function normalizeRetrieveData(data: unknown): { items: unknown[] } {
  const record = asRecord(data);
  const rawItems = record?.items;
  return {
    items: Array.isArray(rawItems) ? rawItems : [],
  };
}

app.get('/health', async () => ({
  status: 'ok',
  timestamp: new Date().toISOString(),
}));

app.post('/v1/retrieve', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const result = await retrieve(caller, request.body);
  const data = normalizeRetrieveData(result.data);
  return reply.status(200).send({
    success: true,
    data,
  });
});

app.post('/v1/documents', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const result = await createDocument(caller, request.body);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.post('/v1/documents/preview', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const file = await request.file();
  if (!file) {
    throw new ApiError(400, 'MISSING_FILE', 'Multipart field file is required');
  }
  const content = await file.toBuffer();
  const kbId = readMultipartField(file.fields as Record<string, any>, 'kb_id') ?? config.defaultKbId;
  const title = readMultipartField(file.fields as Record<string, any>, 'title');
  const defaultMinLevelRaw =
    readMultipartField(file.fields as Record<string, any>, 'default_min_level') ?? 'driver';
  if (!['driver', 'fleet', 'company', 'group'].includes(defaultMinLevelRaw)) {
    throw new ApiError(400, 'INVALID_DEFAULT_LEVEL', 'default_min_level must be driver/fleet/company/group');
  }
  const splitOptionsRaw = readMultipartField(file.fields as Record<string, any>, 'split_options');
  let splitOptions: { min_clause_chars?: number; max_clause_chars?: number } | undefined;
  if (splitOptionsRaw) {
    try {
      splitOptions = JSON.parse(splitOptionsRaw) as { min_clause_chars?: number; max_clause_chars?: number };
    } catch {
      throw new ApiError(400, 'INVALID_SPLIT_OPTIONS', 'split_options must be valid JSON');
    }
  }

  const result = await previewDocument(caller, {
    kb_id: kbId,
    title,
    default_min_level: defaultMinLevelRaw as 'driver' | 'fleet' | 'company' | 'group',
    file_name: file.filename || title || 'upload',
    file_mime: file.mimetype || 'application/octet-stream',
    file_size: content.length,
    content,
    split_options: splitOptions,
  });
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.post('/v1/documents/commit', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const result = await commitDocument(caller, request.body);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.post('/v1/documents/:docId/replace', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { docId: string };
  const result = await replaceDocument(caller, params.docId, request.body);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.patch('/v1/documents/:docId', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { docId: string };
  const result = await patchDocument(caller, params.docId, request.body);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.delete('/v1/documents/:docId', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { docId: string };
  const query = request.query as { kb_id?: string };
  if (!query.kb_id) {
    throw new ApiError(400, 'MISSING_KB_ID', 'Query kb_id is required');
  }
  const result = await deleteDocument(caller, query.kb_id, params.docId);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.post('/v1/documents/:docId/clauses:batchUpsert', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { docId: string };
  const result = await batchUpsertClauses(caller, params.docId, request.body);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.delete('/v1/documents/:docId/clauses/:clauseId', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { docId: string; clauseId: string };
  const query = request.query as { kb_id?: string };
  if (!query.kb_id) {
    throw new ApiError(400, 'MISSING_KB_ID', 'Query kb_id is required');
  }
  const result = await deleteClause(caller, query.kb_id, params.docId, params.clauseId);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.post('/v1/reindex', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const result = await triggerReindex(caller, request.body);
  return reply.status(result.statusCode).send({
    success: true,
    data: result.data,
  });
});

app.get('/v1/jobs/:jobId', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { jobId: string };
  const result = await getJob(caller, params.jobId);
  return reply.status(200).send({
    success: true,
    ...result,
  });
});

app.get('/v1/documents', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const query = request.query as { kb_id?: string; limit?: string; offset?: string };
  if (!query.kb_id) {
    throw new ApiError(400, 'MISSING_KB_ID', 'Query kb_id is required');
  }
  const rawLimit = Number(query.limit ?? 20);
  const rawOffset = Number(query.offset ?? 0);
  const limit = Number.isFinite(rawLimit) ? Math.min(100, Math.max(1, Math.floor(rawLimit))) : 20;
  const offset = Number.isFinite(rawOffset) ? Math.max(0, Math.floor(rawOffset)) : 0;
  const result = await listDocuments(caller, query.kb_id, limit, offset);
  const data = normalizeListDocumentsData(result.data, limit, offset);
  return reply.status(200).send({
    success: true,
    data,
  });
});

app.get('/v1/documents/:docId', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { docId: string };
  const query = request.query as { kb_id?: string; include_clauses?: string };
  if (!query.kb_id) {
    throw new ApiError(400, 'MISSING_KB_ID', 'Query kb_id is required');
  }
  const includeClauses = query.include_clauses !== 'false';
  const result = await getDocument(caller, query.kb_id, params.docId, includeClauses);
  return reply.status(200).send({
    success: true,
    ...result,
  });
});

app.get('/v1/documents/:docId/file', async (request, reply) => {
  const caller = resolveCallerContext(request);
  const params = request.params as { docId: string };
  const query = request.query as { kb_id?: string };
  if (!query.kb_id) {
    throw new ApiError(400, 'MISSING_KB_ID', 'Query kb_id is required');
  }
  const result = await getDocumentFile(caller, query.kb_id, params.docId);
  reply.header('Content-Type', result.file_mime);
  reply.header('Content-Disposition', `attachment; filename="${encodeURIComponent(result.file_name)}"`);
  return reply.status(200).send(result.buffer);
});

async function bootstrap() {
  await ensureStorageRoots();
  await ensureQdrantCollection();
  await app.listen({
    port: config.kbApiPort,
    host: '0.0.0.0',
  });
  app.log.info(`KB API started on port ${config.kbApiPort}`);
}

bootstrap().catch((error) => {
  app.log.error({ err: error }, 'Failed to start KB API');
  process.exit(1);
});
