import { afterEach, describe, expect, it, vi } from 'vitest';
import { kbRepository } from '../src/db/repository';
import { levelToRank } from '../src/models/access';
import { runOneWorkerTick } from '../src/services/job-worker';
import * as embeddingService from '../src/services/embedding';
import * as qdrantService from '../src/services/qdrant';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('job worker embedding context', () => {
  it('uses title and field path when generating embeddings', async () => {
    const job = {
      job_id: 'job-1',
      revision: 1,
      job_type: 'upsert' as const,
      tenant_id: 't1',
      kb_id: 'regulations',
      doc_id: 'doc-1',
      clause_id: 'clause-1',
      payload_json: '{}',
      status: 'pending' as const,
      retry_count: 0,
      next_run_at: '2026-01-01T00:00:00.000Z',
      last_error: '',
      created_at: '2026-01-01T00:00:00.000Z',
      updated_at: '2026-01-01T00:00:00.000Z',
    };

    vi.spyOn(kbRepository, 'listRunnableJobs').mockResolvedValue([job]);
    vi.spyOn(kbRepository, 'appendJobRevision').mockImplementation(async (base, patch) => ({
      ...base,
      revision: base.revision + 1,
      status: patch.status ?? base.status,
      retry_count: patch.retry_count ?? base.retry_count,
      next_run_at: patch.next_run_at ?? base.next_run_at,
      last_error: patch.last_error ?? base.last_error,
      payload_json: patch.payload_json ?? base.payload_json,
      updated_at: '2026-01-01T00:00:01.000Z',
    }));
    vi.spyOn(kbRepository, 'getClauseForIndexing').mockResolvedValue({
      tenant_id: 't1',
      kb_id: 'regulations',
      doc_id: 'doc-1',
      clause_id: 'clause-1',
      field_path: '第一章/第十二条/（一）',
      content_text: '正文内容',
      min_level: 'driver',
      min_rank: levelToRank('driver'),
      order_index: 1,
      tags_json: '[]',
      content_hash: 'hash',
      vector_status: 'pending',
      vector_error: '',
      status: 'active',
      version: 1,
      inherits_default: 1,
      is_deleted: 0,
      created_at: '2026-01-01T00:00:00.000Z',
      updated_at: '2026-01-01T00:00:00.000Z',
      title: '制度标题',
    });
    vi.spyOn(kbRepository, 'parseTags').mockReturnValue([]);
    vi.spyOn(kbRepository, 'duplicateClauseWithVectorState').mockResolvedValue();
    const embedSpy = vi.spyOn(embeddingService, 'generateEmbedding').mockResolvedValue([0.1, 0.2]);
    vi.spyOn(qdrantService, 'deleteClausePointsByKey').mockResolvedValue();
    vi.spyOn(qdrantService, 'upsertClausePoint').mockResolvedValue();

    const processed = await runOneWorkerTick();

    expect(processed).toBe(1);
    expect(embedSpy).toHaveBeenCalledWith(['制度标题', '第一章/第十二条/（一）', '正文内容'].join('\n'));
  });
});
