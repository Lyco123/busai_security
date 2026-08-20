import { QdrantClient } from '@qdrant/js-client-rest';
import { config } from '../config';
import type { AccessLevel } from '../models/access';

export interface QdrantClausePayload {
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
  field_path: string;
  min_level: AccessLevel;
  min_rank: number;
  doc_version: number;
  clause_version: number;
  is_deleted: boolean;
  status: string;
  tags: string[];
  updated_at: string;
}

export interface RetrieveFilterInput {
  doc_ids?: string[];
  field_paths?: string[];
  tags?: string[];
}

export interface QdrantSearchResult {
  id: string | number;
  score: number;
  payload?: QdrantClausePayload;
}

type Filter = Record<string, unknown>;

const client = new QdrantClient({
  url: config.qdrantUrl,
});

function mustMatch(key: string, value: string | number | boolean) {
  return { key, match: { value } };
}

function mustAny(key: string, values: string[]) {
  return { key, match: { any: values } };
}

export async function ensureQdrantCollection(): Promise<void> {
  const collections = await client.getCollections();
  const exists = collections.collections.some((item) => item.name === config.qdrantCollection);
  if (exists) return;
  await client.createCollection(config.qdrantCollection, {
    vectors: {
      size: config.embedDim,
      distance: 'Cosine',
    },
    hnsw_config: {
      m: 32,
      ef_construct: 256,
    },
  });
}

export function makePointId(params: {
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
  version: number;
}): string {
  return `${params.tenant_id}:${params.kb_id}:${params.doc_id}:${params.clause_id}:${params.version}`;
}

export async function deleteClausePointsByKey(input: {
  tenant_id: string;
  kb_id: string;
  doc_id: string;
  clause_id: string;
}): Promise<void> {
  const filter: Filter = {
    must: [
      mustMatch('tenant_id', input.tenant_id),
      mustMatch('kb_id', input.kb_id),
      mustMatch('doc_id', input.doc_id),
      mustMatch('clause_id', input.clause_id),
    ],
  };
  await client.delete(config.qdrantCollection, { wait: true, filter });
}

export async function upsertClausePoint(input: {
  point_id: string;
  vector: number[];
  payload: QdrantClausePayload;
}): Promise<void> {
  await client.upsert(config.qdrantCollection, {
    wait: true,
    points: [
      {
        id: input.point_id,
        vector: input.vector,
        payload: input.payload as unknown as Record<string, unknown>,
      },
    ],
  });
}

function buildRetrieveFilter(input: {
  tenant_id: string;
  kb_id: string;
  caller_rank: number;
  filters?: RetrieveFilterInput;
}): Filter {
  const must: Array<Record<string, unknown>> = [
    mustMatch('tenant_id', input.tenant_id),
    mustMatch('kb_id', input.kb_id),
    mustMatch('is_deleted', false),
    mustMatch('status', 'active'),
    { key: 'min_rank', range: { lte: input.caller_rank } },
  ];
  if (input.filters?.doc_ids && input.filters.doc_ids.length > 0) {
    must.push(mustAny('doc_id', input.filters.doc_ids));
  }
  if (input.filters?.field_paths && input.filters.field_paths.length > 0) {
    must.push(mustAny('field_path', input.filters.field_paths));
  }
  if (input.filters?.tags && input.filters.tags.length > 0) {
    must.push(mustAny('tags', input.filters.tags));
  }
  return { must };
}

export async function searchClauseVectors(input: {
  tenant_id: string;
  kb_id: string;
  caller_rank: number;
  vector: number[];
  limit: number;
  filters?: RetrieveFilterInput;
}): Promise<QdrantSearchResult[]> {
  const filter = buildRetrieveFilter(input);
  const response = await client.search(config.qdrantCollection, {
    vector: input.vector,
    with_payload: true,
    limit: input.limit,
    filter,
  });
  return response.map((row) => ({
    id: row.id,
    score: row.score,
    payload: row.payload as QdrantClausePayload | undefined,
  }));
}
