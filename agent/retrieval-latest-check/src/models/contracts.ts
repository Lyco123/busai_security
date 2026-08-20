import type { AccessLevel } from './access';

export interface CallerContext {
  tenant_id: string;
  caller_level: AccessLevel;
  caller_rank: number;
  caller_id: string;
  caller_company_id?: string;
  request_id: string;
}

export interface ClauseInput {
  clause_id?: string;
  field_path: string;
  content: string;
  min_level?: AccessLevel;
  tags?: string[];
  order_index?: number;
}

export interface RetrieveRequest {
  kb_id: string;
  query: string;
  top_k?: number;
  filters?: {
    doc_ids?: string[];
    field_paths?: string[];
    tags?: string[];
  };
}

export interface RetrieveItem {
  doc_id: string;
  clause_id: string;
  field_path: string;
  content: string;
  score: number;
  min_level: AccessLevel;
  metadata: {
    title: string;
    source_uri: string;
    tags: string[];
    file_name: string;
    order_index: number;
  };
}

export interface RetrieveResponse {
  items: RetrieveItem[];
}

export interface DocumentRecord {
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  title: string;
  source_uri: string;
  file_name: string;
  file_mime: string;
  file_size: number;
  file_hash: string;
  file_storage_key: string;
  default_min_level: AccessLevel;
  default_min_rank: number;
  status: string;
  version: number;
  is_deleted: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface ClauseRecord {
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
  vector_status: 'pending' | 'ready' | 'failed' | 'deleted';
  vector_error: string;
  status: string;
  version: number;
  inherits_default: number;
  is_deleted: number;
  created_at: string;
  updated_at: string;
}

export interface IndexJobRecord {
  job_id: string;
  job_type: 'upsert' | 'delete' | 'rebuild';
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
  payload_json: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  retry_count: number;
  revision: number;
  next_run_at: string;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface AuditLogRecord {
  event_id: string;
  tenant_id: string;
  actor_level: AccessLevel;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  request_id: string;
  result: string;
  details_json: string;
  created_at: string;
}

export interface IngestPreviewRecord {
  preview_id: string;
  tenant_id: string;
  kb_id: string;
  file_hash: string;
  file_name: string;
  file_mime: string;
  file_size: number;
  temp_file_key: string;
  preview_token_hash: string;
  status: 'pending' | 'committed' | 'expired';
  expires_at: string;
  created_at: string;
  updated_at: string;
}
