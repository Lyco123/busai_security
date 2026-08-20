# Legacy and Archive Index

## Purpose

This file separates current handoff documents from historical material. Historical docs remain useful for rationale, but current behavior should be checked against code and this `current/` directory.

## Legacy Design and AB Documents

Directory:

- `agent/docs/legacy/`

Notable files:

- `AB盲测重构方案.md`
- `Agent测试迭代方案-router-skill-ab.md`
- `kb-module-phase1-plan.md`
- `MCP服务设计文档20260403*.md`
- `MCP服务设计文档20260417.md`
- `router-ab-x.SKILL.md`
- `router-ab-y.SKILL.md`
- `车辆专家CoT开关AB测试方案.md`
- `车辆专家拆分AB测试方案.md`

## Weekly Reports

Directory:

- `agent/docs/weekly_reports/**`

Use weekly reports for change history and rationale. Do not use them as current API or architecture contracts.

High-value weeks:

- `260408`: runtime split, router shortcut removal, opening/closing, KB check package.
- `260422`: route expert, recall routing, OCR/RAG notes.
- `260513`: unit/incident experts, stream probes, report summary API.
- `260603`: latest weekly consolidation.

## Manual Records

Directory:

- `agent/docs/manual/**`

Manual records are test evidence, not architecture docs. Use them to reconstruct regression expectations.

## Probe Results

Directory:

- `agent/docs/probeResults/**`

Use for incident/debug evidence.

## RAG Samples

Directory:

- `agent/docs/RAG/**`

These are content samples for KB verification, not system design docs.

## Encoding Note

Some historical Markdown files display mojibake in PowerShell output. Before turning any historical file into an official current document, normalize encoding and run:

```bash
npm run check:text
```
