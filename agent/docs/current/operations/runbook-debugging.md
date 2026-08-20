# Runbook Debugging

## First Checks

1. Confirm which endpoint is failing: chat, stream, report summary, KB, research, rules, or sessions.
2. Check auth state with `/api/agent/auth/me`.
3. Check Worker health with `/api/agent/health`.
4. If streaming is involved, compare direct stream probe against full pipeline.
5. If KB is involved, test retrieval service directly before debugging prompts.

## Router Misrouting

Check in this order:

1. Router tool descriptions in `router-tools.ts`.
2. Router skill in `agent/skills/router/SKILL.md`.
3. Rule match injection in `router-prompts.ts`.
4. Pending clarification context.
5. Latest structured report context.
6. Dynamic tool allow list.
7. Entity lookup/normalization.

Related docs:

- `agent/docs/router-prompt-followups-20260416.md`
- `agent/docs/router-shortcut-removal-20260408.md`

## Streaming Problems

Use:

- direct stream probe to inspect upstream model chunking
- pipeline stream probe to inspect full agent behavior
- `OPENAI_STREAM_DIAGNOSTICS` for upstream chunk/event/delta logs

Related docs:

- `agent/docs/direct-stream-probe-20260513.md`
- `agent/docs/openai-stream-diagnostics-20260513.md`
- `agent/docs/streaming-protocol-frontend-adaptation-20260512.md`

## KB Problems

Check:

1. `KB_API_BASE_URL` in Worker.
2. `KB_TOOL_ENABLED`.
3. caller headers and auth-derived KB level.
4. retrieval API health.
5. ClickHouse DSN uses HTTP port `8123`.
6. embedding key exists in both API and worker containers.
7. schema compatibility via `npm run init:schema`.
8. Qdrant collection state.

Related docs:

- `agent/retrieval/README.md`
- `agent/retrieval/RAG上线复盘与踩坑实录.md`

## Report Problems

Check:

1. Router selected `generate_*_report`.
2. Requested entity resolved correctly.
3. Structured report data source returned a hit.
4. Missing data retry did not exceed limit.
5. Normalizer accepted the output.
6. Metadata and sources were attached.

Primary files:

- `structured-report-runtime.ts`
- `structured-report-data-sources.ts`
- `structured-report-normalizers.ts`
- `structured-lookup.ts`

## Rule Config Problems

Check:

- `RULE_CONFIG_STATE_MACHINE_V2`
- rule draft repository
- rule config service
- rule test service
- regression scripts

## Encoding Problems

Run:

```bash
npm run check:text
```

This runs encoding and mojibake checks from `agent/scripts`.
