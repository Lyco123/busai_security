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

function readBool(name: string, defaultValue: boolean): boolean {
  const value = process.env[name];
  if (!value) return defaultValue;
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
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
  llmBaseUrl: readString('LLM_BASE_URL', readString('EMBEDDING_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')),
  llmApiKey: readString('LLM_API_KEY', readString('EMBEDDING_API_KEY', '')),
  queryRewriteModel: readString('QUERY_REWRITE_MODEL', 'qwen-plus'),
  rerankModel: readString('RERANK_MODEL', 'qwen-plus'),
  embedDim: readInt('EMBED_DIM', 1536),
  indexJobPollIntervalMs: readInt('INDEX_JOB_POLL_INTERVAL_MS', 5000),
  indexJobMaxRetry: readInt('INDEX_JOB_MAX_RETRY', 6),
  indexWorkerBatchSize: readInt('INDEX_WORKER_BATCH_SIZE', 10),
  indexWorkerConcurrency: readInt('INDEX_WORKER_CONCURRENCY', 2),
  retrieveTopN: readInt('RETRIEVE_TOP_N', 50),
  retrieveDenseRecallLimit: readInt('RETRIEVE_DENSE_RECALL_LIMIT', 30),
  retrieveLexicalRecallLimit: readInt('RETRIEVE_LEXICAL_RECALL_LIMIT', 40),
  retrieveCandidatePoolLimit: readInt('RETRIEVE_CANDIDATE_POOL_LIMIT', 40),
  retrieveRerankEnabled: readString('RETRIEVE_RERANK_ENABLED', 'true').toLowerCase() !== 'false',
  retrieveRewriteEnabled: readString('RETRIEVE_REWRITE_ENABLED', 'true').toLowerCase() !== 'false',
  requestTimeoutMs: readInt('REQUEST_TIMEOUT_MS', 20000),
  maxFileSizeBytes: readInt('MAX_FILE_SIZE_BYTES', 20 * 1024 * 1024),
  maxClausesPerDocument: readInt('MAX_CLAUSES_PER_DOCUMENT', 2000),
  previewTtlSeconds: readInt('PREVIEW_TTL_SECONDS', 3600),
  rawFileRoot: readString('RAW_FILE_ROOT', './data/kb-files'),
  rawPreviewRoot: readString('RAW_PREVIEW_ROOT', './data/kb-previews'),
  ocrEnabled: readBool('OCR_ENABLED', false),
  ocrBaseUrl: readString('OCR_BASE_URL', ''),
  ocrTimeoutMs: readInt('OCR_TIMEOUT_MS', 120000),
  ocrLanguage: readString('OCR_LANGUAGE', 'ch'),
  logLevel: readString('LOG_LEVEL', 'info'),
};
