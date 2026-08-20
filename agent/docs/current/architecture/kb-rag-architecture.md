# KB RAG Architecture

## Scope

KB/RAG consists of two parts:

- Edge integration inside the agent Worker.
- Standalone retrieval service under `agent/retrieval/`.

The retrieval service owns document ingestion, parsing, storage, vector indexing, lexical fallback, permissions, and retrieve APIs. The Worker owns proxying, auth context, and exposing KB retrieval as an agent tool.

## Components

```text
Front end KB pages
  -> /api/agent/kb/*
  -> Worker KB proxy
  -> retrieval API
  -> ClickHouse + Qdrant + raw file storage

Agent worker
  -> query_kb tool
  -> kb-query-tool
  -> retrieval API /v1/retrieve
  -> clauses returned to worker prompt and sources
```

Primary files:

- Worker proxy: `agent/src/infra/kb-proxy.ts`
- Worker query tool: `agent/src/infra/kb-query-tool.ts`
- Tool exposure: `agent/src/tools/provider.ts`
- Retrieval API: `agent/retrieval/src/index.ts`
- Retrieval service logic: `agent/retrieval/src/services/kb-service.ts`
- Retrieval repository: `agent/retrieval/src/db/repository.ts`
- Qdrant service: `agent/retrieval/src/services/qdrant.ts`
- Worker indexing: `agent/retrieval/src/services/job-worker.ts`

## Retrieval Service Capabilities

Implemented capabilities from `agent/retrieval/README.md`:

- File-level ingestion with `preview -> commit -> replace`.
- Raw file storage and download.
- Async vector indexing jobs.
- Qdrant ANN retrieval.
- ClickHouse lexical fallback.
- Worker process for embedding generation and vector upsert/delete.
- Field-level visibility filtering with rank order `driver < fleet < company < group`.
- OCR support for scanned PDFs when OCR is enabled.

## Storage

ClickHouse tables:

- `kb_documents`
- `kb_clauses`
- `kb_index_jobs`
- `kb_ingest_previews`
- `kb_audit_logs`

Vector storage:

- Qdrant collection, default `kb_clauses_dense`.

Raw files:

- Controlled by `RAW_FILE_ROOT` and `RAW_PREVIEW_ROOT` in retrieval service env.

## Edge Env

Worker-side KB env:

- `KB_API_BASE_URL`
- `KB_API_TIMEOUT_MS`
- `KB_DEFAULT_ID`
- `KB_TOOL_ENABLED`
- `KB_TENANT_ID`

Retrieval service env is documented in `agent/retrieval/README.md`.

## Historical Sources

- `agent/retrieval/README.md`
- `agent/docs/方案_RAG向量数据库落地实施_Qdrant.md`
- `agent/docs/rag-omni-verification-cases-20260412.md`
- `agent/retrieval/RAG上线复盘与踩坑实录.md`

## Gaps

- End-to-end policy for when each expert should use KB is still not expressed in one product-level document.
- KB source citation formatting in final answers is implementation-dependent and should be standardized.
- Some RAG historical docs have encoding issues in shell output.
