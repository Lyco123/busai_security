import { afterEach, describe, expect, it, vi } from 'vitest';
import { kbRepository } from '../src/db/repository';
import { levelToRank } from '../src/models/access';
import type { CallerContext, ClauseRecord, DocumentRecord } from '../src/models/contracts';
import { getDocument, retrieve } from '../src/services/kb-service';
import * as embeddingService from '../src/services/embedding';
import * as qdrantService from '../src/services/qdrant';
import * as rewriteService from '../src/services/query-rewrite';

function buildCaller(level: 'driver' | 'fleet' | 'company' | 'group' = 'group'): CallerContext {
  return {
    tenant_id: 't1',
    caller_level: level,
    caller_rank: levelToRank(level),
    caller_id: 'u1',
    request_id: 'req-1',
  };
}

function buildDocument(): DocumentRecord {
  return {
    tenant_id: 't1',
    kb_id: 'regulations',
    doc_id: 'doc-1',
    title: '制度标题',
    source_uri: '',
    file_name: 'demo.txt',
    file_mime: 'text/plain',
    file_size: 12,
    file_hash: 'hash',
    file_storage_key: 'key',
    default_min_level: 'driver',
    default_min_rank: levelToRank('driver'),
    status: 'active',
    version: 1,
    is_deleted: 0,
    created_by: 'u1',
    updated_by: 'u1',
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: '2026-01-01T00:00:00.000Z',
  };
}

function buildClause(fieldPath: string): ClauseRecord {
  return {
    tenant_id: 't1',
    kb_id: 'regulations',
    doc_id: 'doc-1',
    clause_id: 'clause-1',
    field_path: fieldPath,
    content_text: '正文内容',
    min_level: 'driver',
    min_rank: levelToRank('driver'),
    order_index: 1,
    tags_json: '[]',
    content_hash: 'hash',
    vector_status: 'ready',
    vector_error: '',
    status: 'active',
    version: 1,
    inherits_default: 1,
    is_deleted: 0,
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: '2026-01-01T00:00:00.000Z',
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('kb service heading path responses', () => {
  it('returns derived heading_path for document clauses', async () => {
    vi.spyOn(kbRepository, 'getDocumentById').mockResolvedValue(buildDocument());
    vi.spyOn(kbRepository, 'listClausesByDocument').mockResolvedValue([buildClause('第一章/第十二条/（一）')]);

    const result = await getDocument(buildCaller(), 'regulations', 'doc-1', true);

    expect(result.data.clauses).toHaveLength(1);
    expect(result.data.clauses[0].heading_path).toEqual(['第一章', '第十二条', '（一）']);
    expect(result.data.clauses[0].content).toBe('正文内容');
  });

  it('returns heading_path in retrieve results', async () => {
    vi.spyOn(kbRepository, 'searchVisibleDocumentsByTitle').mockResolvedValue([]);
    vi.spyOn(embeddingService, 'generateEmbedding').mockResolvedValue([0.1, 0.2]);
    vi.spyOn(qdrantService, 'searchClauseVectors').mockResolvedValue([
      {
        id: 'p1',
        score: 0.92,
        payload: {
          tenant_id: 't1',
          kb_id: 'regulations',
          doc_id: 'doc-1',
          clause_id: 'clause-1',
          field_path: '第一章/第十二条/（一）',
          min_level: 'driver',
          min_rank: levelToRank('driver'),
          doc_version: 1,
          clause_version: 1,
          is_deleted: false,
          status: 'active',
          tags: [],
          updated_at: '2026-01-01T00:00:00.000Z',
        },
      },
    ]);
    vi.spyOn(kbRepository, 'fetchClausesByKeys').mockResolvedValue([
      {
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
        source_uri: '',
        title: '制度标题',
        file_name: 'demo.txt',
        updated_at: '2026-01-01T00:00:00.000Z',
      },
    ]);
    vi.spyOn(kbRepository, 'lexicalSearchClauses').mockResolvedValue([]);
    vi.spyOn(kbRepository, 'insertAuditLog').mockResolvedValue();

    const result = await retrieve(buildCaller(), { kb_id: 'regulations', query: '适用范围', top_k: 5 });

    expect(result.data.items).toHaveLength(1);
    expect(result.data.items[0].heading_path).toEqual(['第一章', '第十二条', '（一）']);
    expect(result.data.items[0].field_path).toBe('第一章/第十二条/（一）');
  });

  it('uses document title fast path without dense embedding for title queries', async () => {
    const document = {
      ...buildDocument(),
      title: '穗巴士集〔2022〕84号 广州巴士集团有限公司关于印发服务投诉管理规定的通知（校对稿）',
      file_name: '穗巴士集〔2022〕84号 广州巴士集团有限公司关于印发服务投诉管理规定的通知（校对稿）.docx',
    };
    vi.spyOn(kbRepository, 'searchVisibleDocumentsByTitle').mockResolvedValue([document]);
    vi.spyOn(kbRepository, 'listClausesByDocument').mockResolvedValue([
      buildClause('第一章 总则/第一条'),
      { ...buildClause('第一章 总则/第二条'), clause_id: 'clause-2', order_index: 2 },
    ]);
    vi.spyOn(kbRepository, 'parseTags').mockReturnValue([]);
    vi.spyOn(kbRepository, 'insertAuditLog').mockResolvedValue();
    const embedSpy = vi.spyOn(embeddingService, 'generateEmbedding').mockResolvedValue([0.1, 0.2]);
    const rewriteSpy = vi.spyOn(rewriteService, 'rewriteRetrieveQuery');

    const result = await retrieve(buildCaller(), {
      kb_id: 'regulations',
      query: '穗巴士集〔2022〕84号 广州巴士集团有限公司关于印发服务投诉管理规定的通知',
      top_k: 2,
    });

    expect(result.data.items).toHaveLength(2);
    expect(result.data.items[0].metadata?.title).toBe(document.title);
    expect(result.data.items[0].field_path).toBe('第一章 总则/第一条');
    expect(embedSpy).not.toHaveBeenCalled();
    expect(rewriteSpy).not.toHaveBeenCalled();
  });
});
