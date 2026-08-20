# KB Permission and Ingestion

## Permission Model

KB permissions are evaluated on two axes:

- Caller level: the Agent Worker derives `X-Caller-Level` from `agent_users.kb_level`; if `kb_level` is not configured, admins default to `group` and normal users default to `driver`.
- Resource minimum level: documents use `default_min_level`; clauses use `min_level`, or inherit the document default when no explicit clause level is provided.

Rank order:

```text
driver < fleet < company < group
```

Business meaning:

| Level     | Meaning |
| --------- | ------- |
| `driver`  | Driver, frontline individual, or lowest visibility scope |
| `fleet`   | Fleet, route team, or grassroots management unit |
| `company` | Company, subsidiary, or professional company management user |
| `group`   | Group headquarters or platform-wide super-management scope |

Read rule: `caller_rank >= resource_min_rank`.

- Lists and retrieval silently filter resources above the caller level.
- Single-resource reads return `404` for resources that do not exist, are deleted, or are above the caller level.

Write rule: the caller must be at least `company` level and must not write a resource whose minimum level is above the caller level.

Required retrieval headers:

- `X-Tenant-Id`
- `X-Caller-Level`
- `X-Caller-Id`
- `X-Caller-Company-Id` when the Agent Worker has `company_id`; currently passed through but not used for authorization

Worker auth contains KB-related user fields such as `kb_level` and `company_id` in `agent/src/infra/auth/session-store.ts`; `agent/src/infra/kb-proxy.ts` injects them into Retrieval headers.

Current caller-level management is DB-only. There is no admin API or frontend for editing `agent_users.kb_level/company_id`; operators must update the database directly:

```sql
UPDATE agent_users
SET kb_level = 'company',
    company_id = 'company_xxx',
    updated_at = datetime('now')
WHERE id = 'user_xxx';
```

If an older deployment lacks the columns, add them before updating users:

```sql
ALTER TABLE agent_users ADD COLUMN kb_level TEXT;
ALTER TABLE agent_users ADD COLUMN company_id TEXT;
```

## Ingestion Flow

```text
preview
  -> parse file
  -> create preview record
  -> store temporary raw file

commit
  -> create document
  -> create clauses
  -> create upsert index jobs

replace
  -> tombstone old clauses
  -> create delete index jobs
  -> insert new clauses
  -> create upsert index jobs

worker
  -> consume jobs
  -> generate embeddings
  -> upsert/delete Qdrant points
  -> update vector status
```

## Supported Files

From current retrieval README:

- `txt`
- `md`
- `docx`
- `pdf` with extractable text
- scanned PDF when `OCR_ENABLED=true`

If OCR is disabled and a PDF has no text layer, the API can return `PDF_OCR_REQUIRED`.

## API Endpoints

For complete request and response contracts, see [知识库系统 API 接口文档](../operations/知识库系统API接口文档.md).

Retrieval service endpoints include:

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

## Source Documents

- `agent/retrieval/README.md`
- `agent/retrieval/sql/schema.sql`
- `agent/retrieval/src/models/contracts.ts`
- `agent/retrieval/src/services/kb-service.ts`
- `agent/retrieval/src/db/repository.ts`

## Gaps

- Citation display policy needs a shared frontend/backend contract.
- The current front end sends `min_level` for every clause during commit, so document-level permission changes only update clauses that were created without explicit `min_level`.
- There is no admin API or UI for managing `agent_users.kb_level/company_id`.
