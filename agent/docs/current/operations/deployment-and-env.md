# Deployment and Environment

## Worker Service

The agent Worker lives in `agent/`.

Common commands from `agent/package.json`:

```bash
npm run dev
npm run deploy
npm run check:text
```

The Worker is deployed with Wrangler and configured by `agent/wrangler.toml` plus environment/secrets.

## Retrieval Service

The KB retrieval service lives in `agent/retrieval/`.

Common flow:

```bash
npm ci
npm run build
npm run init:schema
npm run start
npm run start:worker
```

Docker flow is documented in `agent/retrieval/README.md`.

## Key Worker Env

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_ROUTER_MODEL`
- `OPENAI_WORKER_MODEL`
- `OPENAI_REPORT_BASE_URL`
- `OPENAI_REPORT_API_KEY`
- `OPENAI_REPORT_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `EMBEDDING_MODEL`
- `OPENAI_TITLE_MODEL`
- `OPENAI_STREAM_DIAGNOSTICS`
- `CORS_ALLOWED_ORIGINS`
- `KB_API_BASE_URL`
- `KB_API_TIMEOUT_MS`
- `KB_DEFAULT_ID`
- `KB_TOOL_ENABLED`
- `KB_TENANT_ID`
- `RULE_CONFIG_STATE_MACHINE_V2`
- `MCP_SERVER_URL`
- `CF_ACCESS_CLIENT_ID`
- `CF_ACCESS_CLIENT_SECRET`
- `MCP_ACCESS_TOKEN`

## Key Retrieval Env

See `agent/retrieval/README.md`. Important values include:

- ClickHouse DSN, using HTTP port `8123`.
- Qdrant URL/collection.
- embedding API key/model.
- raw file storage roots.
- OCR enablement.
- API port.

## Existing Source Documents

- `agent/docs/后端本地部署实操手册.md`
- `agent/docs/方案_后端服务本地部署.md`
- `agent/docs/本地模型替换_编排层改动与重部署清单-极简版.md`
- `agent/docs/模型服务需求-极简版.md`
- `agent/docs/方案_大模型本地部署_Qwen32B.md`
- `agent/retrieval/README.md`

## Gaps

- Env vars are not generated into documentation from source.
- Secret management policy is not documented here.
- Production topology diagrams are still missing.
