# Test Server Recovery Notes

Date: `2026-03-25`

This note records the recovery path used to bring the KB retrieval stack back to a working state on a test server that used:

- external ClickHouse on the same host
- `docker-compose.server.yml`
- older ClickHouse schema already present in `default`
- ClickHouse server version older than the version assumed by local full-stack compose

## Symptoms

Observed in order:

1. `kb-api` health endpoint returned `200`, but KB reads failed
2. `kb-worker` kept restarting
3. ClickHouse authentication failed
4. after fixing auth, worker failed with `Table ai_security.kb_index_jobs does not exist`
5. after fixing DB selection, retrieval failed with ClickHouse SQL syntax errors around `FINAL` joins
6. after fixing query shape, retrieval failed because old KB tables were missing columns such as `order_index`
7. after fixing schema, retrieval returned success with empty `items`

## Root Causes

1. Wrong deployment mode:
   `docker-compose.yml` was used against a host that already had ClickHouse listening on `8123`
2. Wrong ClickHouse DSN:
   external ClickHouse required HTTP DSN on port `8123`, not native port `9000`
3. Environment reload misunderstanding:
   `docker compose restart` does not reload `env_file`
4. Wrong database selection:
   legacy KB tables already existed in `default`, not `ai_security`
5. ClickHouse compatibility:
   older ClickHouse rejected the original `FROM kb_clauses FINAL c INNER JOIN kb_documents FINAL d` syntax
6. Legacy schema drift:
   `CREATE TABLE IF NOT EXISTS` did not add missing columns to old tables
7. Old ClickHouse `DateTime64` parsing:
   JSONEachRow inserts using ISO UTC strings such as `2026-03-25T15:28:23.954Z` failed on preview/job inserts

## Working Deployment Pattern

Use external ClickHouse mode:

```bash
docker compose -f docker-compose.server.yml up -d --build --force-recreate
```

Use ClickHouse HTTP DSN:

```env
CK_DSN=http://default:<url-encoded-password>@host.docker.internal:8123
```

Example:

```env
CK_DSN=http://default:Zhongda%4084@host.docker.internal:8123
```

## Recovery Checklist

1. Confirm containers:

```bash
docker compose -f docker-compose.server.yml ps
```

2. Confirm env inside containers after recreating:

```bash
docker exec -it kb-api /bin/sh -lc 'printenv | grep -E "^EMBEDDING_|^CK_DSN|^QDRANT_URL"'
docker exec -it kb-worker /bin/sh -lc 'printenv | grep -E "^EMBEDDING_|^CK_DSN|^QDRANT_URL"'
```

3. Confirm ClickHouse connectivity:

```bash
curl -u 'default:<password>' -s 'http://127.0.0.1:8123/?query=SELECT%201'
```

4. Run schema init:

```bash
docker exec -it kb-api node dist/init-schema.js
```

5. Confirm schema:

```bash
curl -u 'default:<password>' -s 'http://127.0.0.1:8123/?query=DESCRIBE%20TABLE%20default.kb_clauses'
curl -u 'default:<password>' -s 'http://127.0.0.1:8123/?query=DESCRIBE%20TABLE%20default.kb_documents'
```

6. Verify retrieval:

```bash
curl -s -X POST http://127.0.0.1:8080/v1/retrieve \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-Id: bus-test' \
  -H 'X-Caller-Level: group' \
  -H 'X-Caller-Id: tester' \
  -d '{"kb_id":"regulations","query":"事故上报","top_k":3}'
```

Expected healthy behavior:

- no `INTERNAL_ERROR`
- empty `items` is acceptable if no KB data has been imported yet

## Code Changes Introduced

This recovery resulted in two permanent hardening changes:

1. `src/db/repository.ts`
   retrieval joins now wrap `FINAL` reads in subqueries with explicit column lists for better compatibility with older ClickHouse versions
2. `src/init-schema.ts` + repository schema helpers
   schema init now also runs additive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` compatibility migrations for legacy KB tables
3. `src/db/clickhouse.ts`
   insert payloads now normalize ISO UTC timestamps into ClickHouse-friendly `DateTime64` strings before `JSONEachRow` writes

## Remaining Non-Blocking Warning

Qdrant emitted a client/server compatibility warning during startup. It did not block API and worker startup in this recovery, but versions should still be aligned later.
