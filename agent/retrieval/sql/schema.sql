CREATE TABLE IF NOT EXISTS kb_documents (
  tenant_id String,
  kb_id String,
  doc_id String,
  title String,
  source_uri String,
  file_name String,
  file_mime String,
  file_size UInt64,
  file_hash String,
  file_storage_key String,
  default_min_level LowCardinality(String),
  default_min_rank UInt8,
  status LowCardinality(String),
  version UInt32,
  is_deleted UInt8,
  created_by String,
  updated_by String,
  created_at DateTime64(3, 'UTC'),
  updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id, kb_id, doc_id);

CREATE TABLE IF NOT EXISTS kb_clauses (
  tenant_id String,
  kb_id String,
  doc_id String,
  clause_id String,
  field_path String,
  content_text String,
  min_level LowCardinality(String),
  min_rank UInt8,
  order_index UInt32,
  tags_json String,
  content_hash String,
  vector_status LowCardinality(String),
  vector_error String,
  status LowCardinality(String),
  version UInt32,
  inherits_default UInt8,
  is_deleted UInt8,
  created_at DateTime64(3, 'UTC'),
  updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id, kb_id, doc_id, clause_id);

CREATE TABLE IF NOT EXISTS kb_index_jobs (
  job_id String,
  revision UInt32,
  job_type LowCardinality(String),
  tenant_id String,
  kb_id String,
  doc_id String,
  clause_id String,
  payload_json String,
  status LowCardinality(String),
  retry_count UInt16,
  next_run_at DateTime64(3, 'UTC'),
  last_error String,
  created_at DateTime64(3, 'UTC'),
  updated_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (job_id, revision);

CREATE TABLE IF NOT EXISTS kb_ingest_previews (
  preview_id String,
  tenant_id String,
  kb_id String,
  file_hash String,
  file_name String,
  file_mime String,
  file_size UInt64,
  temp_file_key String,
  preview_token_hash String,
  status LowCardinality(String),
  expires_at DateTime64(3, 'UTC'),
  created_at DateTime64(3, 'UTC'),
  updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id, preview_id);

CREATE TABLE IF NOT EXISTS kb_audit_logs (
  event_id String,
  tenant_id String,
  actor_level LowCardinality(String),
  actor_id String,
  action String,
  resource_type String,
  resource_id String,
  request_id String,
  result String,
  details_json String,
  created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (tenant_id, created_at, event_id);
