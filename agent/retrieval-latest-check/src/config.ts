import dotenv from 'dotenv';

dotenv.config();

function readInt(name: string, defaultValue: number): number {
  const raw = process.env[name];
  if (!raw) return defaultValue;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid number for ${name}: ${raw}`);
  }
  return parsed;
}

function readString(name: string, fallback = ''): string {
  const value = process.env[name] ?? fallback;
  return value.trim();
}

export const config = {
  kbApiPort: readInt('KB_API_PORT', 8080),
  defaultKbId: readString('KB_DEFAULT_ID', 'regulations'),
  ckDsn: readString('CK_DSN', 'http://default:@localhost:8123'),
  qdrantUrl: readString('QDRANT_URL', 'http://localhost:6333'),
  qdrantCollection: readString('QDRANT_COLLECTION', 'kb_clauses_dense'),
  embeddingBaseUrl: readString('EMBEDDING_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
  embeddingApiKey: readString('EMBEDDING_API_KEY', ''),
  embeddingModel: readString('EMBEDDING_MODEL', readString('OPENAI_EMBEDDING_MODEL', 'text-embedding-v1')),
  embedDim: readInt('EMBED_DIM', 1536),
  indexJobPollIntervalMs: readInt('INDEX_JOB_POLL_INTERVAL_MS', 5000),
  indexJobMaxRetry: readInt('INDEX_JOB_MAX_RETRY', 6),
  indexWorkerBatchSize: readInt('INDEX_WORKER_BATCH_SIZE', 10),
  indexWorkerConcurrency: readInt('INDEX_WORKER_CONCURRENCY', 2),
  retrieveTopN: readInt('RETRIEVE_TOP_N', 50),
  requestTimeoutMs: readInt('REQUEST_TIMEOUT_MS', 20000),
  maxFileSizeBytes: readInt('MAX_FILE_SIZE_BYTES', 20 * 1024 * 1024),
  maxClausesPerDocument: readInt('MAX_CLAUSES_PER_DOCUMENT', 2000),
  previewTtlSeconds: readInt('PREVIEW_TTL_SECONDS', 3600),
  rawFileRoot: readString('RAW_FILE_ROOT', './data/kb-files'),
  rawPreviewRoot: readString('RAW_PREVIEW_ROOT', './data/kb-previews'),
  logLevel: readString('LOG_LEVEL', 'info'),
};
