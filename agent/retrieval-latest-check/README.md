# Vector KB Retrieval Service

## Current Status

This service is no longer just a clause CRUD prototype. The current implementation already includes:

- File-level knowledge base ingestion with `preview -> commit -> replace`
- Raw file storage and download
- Async vector indexing jobs
- Qdrant ANN retrieval with ClickHouse lexical fallback
- Worker process for embedding generation and vector upsert/delete
- Field-level visibility filtering with fixed rank order: `driver < fleet < company < group`

## API Endpoints

Current implemented endpoints:

- `POST /v1/retrieve`
- `POST /v1/documents`
- `POST /v1/documents/preview`
- `POST /v1/documents/commit`
- `POST /v1/documents/{docId}/replace`
- `PATCH /v1/documents/{docId}`
- `DELETE /v1/documents/{docId}?kb_id=...`
- `POST /v1/documents/{docId}/clauses:batchUpsert`
- `DELETE /v1/documents/{docId}/clauses/{clauseId}?kb_id=...`
- `POST /v1/reindex`
- `GET /v1/jobs/{jobId}`
- `GET /v1/documents?kb_id=...`
- `GET /v1/documents/{docId}?kb_id=...&include_clauses=true|false`
- `GET /v1/documents/{docId}/file?kb_id=...`

## Required Headers

- `X-Tenant-Id`
- `X-Caller-Level` (`driver|fleet|company|group`)
- `X-Caller-Id`
- `X-Caller-Company-Id` for company-level writes

## File Ingestion

Supported file types in `preview`:

- `txt`
- `md`
- `docx`
- `pdf` with extractable text layer

Current parser behavior:

- Prefer heading-based clause splitting
- Fallback to paragraph-based splitting when headings are weak
- Return `PDF_OCR_REQUIRED` for scanned PDFs without a text layer
- Enforce file size and per-document clause count limits

## Storage and Indexing

The current schema includes:

- `kb_documents`
- `kb_clauses`
- `kb_index_jobs`
- `kb_ingest_previews`
- `kb_audit_logs`

Write path summary:

1. `preview` parses the file and stores a temporary raw file
2. `commit` creates a new document, clauses, and `upsert` index jobs
3. `replace` tombstones old clauses, creates `delete` jobs, then inserts new clauses and `upsert` jobs
4. worker consumes jobs, generates embeddings, and updates Qdrant plus clause `vector_status`

## Retrieval Behavior

Retrieval currently uses:

- embedding search in Qdrant
- lexical fallback in ClickHouse
- silent access filtering based on caller rank and document/clause min level

## Quick Start

1. Copy env file:

```bash
cp .env.example .env
```

2. Install and build:

```bash
npm ci
npm run build
```

3. Init ClickHouse schema:

```bash
npm run init:schema
```

4. Start API:

```bash
npm run start
```

5. Start worker in another shell:

```bash
npm run start:worker
```

## Docker

```bash
docker compose up -d --build
```

Initialize schema after containers are up:

```bash
docker exec -it kb-api node dist/init-schema.js
```

## Server Deployment

Use `docker-compose.server.yml` if ClickHouse is already running outside this stack.

Set CK endpoint in `.env`:

```env
CK_DSN=http://default:@host.docker.internal:8123
```

Then start:

```bash
docker compose -f docker-compose.server.yml up -d --build
docker exec -it kb-api node dist/init-schema.js
```

Notes for external ClickHouse deployment:

- This service uses ClickHouse HTTP DSN, so use port `8123`, not native port `9000`
- If password contains special characters such as `@`, URL-encode them in `CK_DSN`
- `EMBEDDING_API_KEY` is required for retrieval and vector indexing
- `docker compose restart` does not reload `env_file`; after changing `.env`, use `up -d --force-recreate`
- `npm run init:schema` and `node dist/init-schema.js` now also apply compatibility `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` fixes for older KB tables
- A concrete recovery walkthrough is recorded in `TEST_SERVER_RECOVERY.md`

## Compatibility Notes

The current codebase includes two compatibility safeguards discovered during test-server recovery:

- retrieval SQL uses subquery aliases around `FINAL` joins so it can work against older external ClickHouse deployments
- schema initialization now upgrades legacy `kb_documents` and `kb_clauses` tables by adding missing columns such as `order_index` and file metadata
- ClickHouse inserts normalize ISO UTC timestamps like `2026-03-25T15:28:23.954Z` into `YYYY-MM-DD HH:MM:SS.mmm` so older external ClickHouse builds can parse `DateTime64` fields

If retrieval returns HTTP 500 on an older external ClickHouse:

1. verify `CK_DSN` points to HTTP port `8123`
2. verify `EMBEDDING_API_KEY` is present inside `kb-api` and `kb-worker`
3. run `docker exec -it kb-api node dist/init-schema.js`
4. confirm `DESCRIBE TABLE default.kb_clauses` contains `order_index`
5. confirm `DESCRIBE TABLE default.kb_documents` contains `file_name/file_mime/file_size/file_hash/file_storage_key`

## Example: Preview Document

```bash
curl -X POST http://127.0.0.1:8080/v1/documents/preview \
  -H "X-Tenant-Id: bus-prod" \
  -H "X-Caller-Level: company" \
  -H "X-Caller-Id: op-001" \
  -H "X-Caller-Company-Id: first-branch" \
  -F "kb_id=regulations" \
  -F "title=事故调查规范" \
  -F "default_min_level=company" \
  -F "file=@./docs/sample.md"
```

## Example: Commit Document

```bash
curl -X POST http://127.0.0.1:8080/v1/documents/commit \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: bus-prod" \
  -H "X-Caller-Level: company" \
  -H "X-Caller-Id: op-001" \
  -H "X-Caller-Company-Id: first-branch" \
  -d '{
    "preview_id": "preview_xxx",
    "preview_token": "preview_token_xxx",
    "payload": {
      "kb_id": "regulations",
      "title": "事故调查规范",
      "default_min_level": "company",
      "file_hash": "sha256_xxx",
      "clauses": [
        {
          "field_path": "section/1",
          "content": "事故发生后，应在规定时限内完成上报。",
          "tags": ["事故", "上报"]
        }
      ]
    }
  }'
```

## Example: Retrieve

```bash
curl -X POST http://127.0.0.1:8080/v1/retrieve \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: bus-prod" \
  -H "X-Caller-Level: fleet" \
  -H "X-Caller-Id: captain-001" \
  -d '{
    "kb_id": "regulations",
    "query": "事故发生后多久上报",
    "top_k": 5
  }'
```

## Edge Integration

If you only want to replace the retrieval backend in an existing edge pipeline:

- set `RAG_RETRIEVAL_URL=http://<kb-api-host>:8080/v1/retrieve`
- forward caller headers from edge to KB API
- keep prompt assembly and LLM invocation unchanged
