# Report Generation Pipeline

## Purpose

Structured report generation is stricter than consultation. It should produce a domain-specific report using validated data sources and normalized output.

## Supported Report Tools

- `generate_driver_report`
- `generate_vehicle_report`
- `generate_unit_report`
- `generate_route_report`
- `generate_station_report`
- `generate_accident_investigation_report`

## Flow

```text
router selects generate_*_report
  -> worker-runner loads structured skill
  -> structured report runtime config defines lookup and validation
  -> data source tools retrieve profile/report data
  -> worker model generates report
  -> normalizer checks required shape
  -> metadata/sources are attached
```

Primary files:

- `agent/src/domains/chat/structured-report-runtime.ts`
- `agent/src/domains/chat/structured-report-data-sources.ts`
- `agent/src/domains/chat/structured-report-normalizers.ts`
- `agent/src/domains/chat/structured-lookup.ts`
- `agent/src/domains/chat/*-report-normalizer*.ts`
- `agent/skills/structured/**/SKILL.md`
- `agent/docs/话术/**`

## Data Source Policy

The current code has shared source helpers for structured report paths. Historical work moved reports toward MCP/profile data sources and away from each report worker maintaining separate ad hoc source rules.

Report generation should:

- use the relevant domain profile data
- preserve missing data behavior
- avoid inventing unavailable metrics
- attach sources/metadata for traceability
- keep report-specific templates in structured skills or话术 documents

## Missing Data Handling

Structured report runtime config controls:

- missing data prompt
- no-data error
- format mismatch error
- retry limits
- whether returned payload matches the requested entity
- normalization and completeness checks

## Historical Sources

- `agent/docs/report-source-architecture-20260423.md`
- `agent/docs/report-pipeline-mcp-gap-audit-20260419.md`
- `agent/docs/weekly_reports/260408/md/agent开发周报260408.md`
- `agent/docs/话术/**`

## Gaps

- Formal report artifact generation and storage is not fully described in the current TypeScript path as a separate artifact service.
- Report templates and structured skills are still partly separate documentation surfaces.
- End-to-end source citation standards need one explicit output contract.
