# Agent Documentation Index

This directory is the current handoff documentation set for the agent system. It consolidates the older design notes, weekly reports, API notes, KB/RAG documentation, and the current TypeScript implementation.

The documentation is organized by three granularities and three layers:

- Granularities: overview, topic, implementation reference.
- Layers: architecture, mechanism, operation.

## Reading Paths

For a new engineer:

1. [System Overview](./01-system-overview.md)
2. [Main Execution Flows](./02-main-execution-flows.md)
3. [Runtime Architecture](./architecture/runtime-architecture.md)
4. [Router and Prompt Engineering](./mechanisms/router-and-prompt-engineering.md)
5. [Code Map](./reference/code-map.md)

For prompt/router work:

1. [Router and Prompt Engineering](./mechanisms/router-and-prompt-engineering.md)
2. [Prompt Inventory](./reference/prompt-inventory.md)
3. [Evaluation and Regression](./operations/evaluation-and-regression.md)

For KB/RAG work:

1. [KB RAG Architecture](./architecture/kb-rag-architecture.md)
2. [KB Permission and Ingestion](./reference/kb-permission-and-ingestion.md)
3. [知识库系统 API 接口文档](./operations/知识库系统API接口文档.md)
4. [Deployment and Environment](./operations/deployment-and-env.md)

For production support:

1. [API Reference and Integration](./operations/api-reference-and-integration.md)
2. [Runbook Debugging](./operations/runbook-debugging.md)
3. [Test Case Index](./operations/test-case-index.md)

## Document Map

### Overview

- [System Overview](./01-system-overview.md): current system shape, module boundary, and top-level document coverage.
- [Main Execution Flows](./02-main-execution-flows.md): chat, streaming, report, KB, rule, and probe flows.

### Architecture

- [Runtime Architecture](./architecture/runtime-architecture.md)
- [Expert System Architecture](./architecture/expert-system-architecture.md)
- [KB RAG Architecture](./architecture/kb-rag-architecture.md)
- [MCP Tooling Architecture](./architecture/mcp-tooling-architecture.md)

### Mechanisms

- [Router and Prompt Engineering](./mechanisms/router-and-prompt-engineering.md)
- [Context and Session Mechanism](./mechanisms/context-and-session-mechanism.md)
- [Report Generation Pipeline](./mechanisms/report-generation-pipeline.md)
- [Streaming and Output Protocol](./mechanisms/streaming-and-output-protocol.md)

### Operations

- [API Reference and Integration](./operations/api-reference-and-integration.md)
- [知识库系统 API 接口文档](./operations/知识库系统API接口文档.md)
- [Deployment and Environment](./operations/deployment-and-env.md)
- [Evaluation and Regression](./operations/evaluation-and-regression.md)
- [Runbook Debugging](./operations/runbook-debugging.md)
- [Test Case Index](./operations/test-case-index.md)

### Reference

- [Code Map](./reference/code-map.md)
- [Prompt Inventory](./reference/prompt-inventory.md)
- [KB Permission and Ingestion](./reference/kb-permission-and-ingestion.md)
- [Legacy and Archive Index](./reference/legacy-and-archive-index.md)

## Source Notes

Important source documents are still kept in their original locations:

- `agent/docs/agent_devdoc.md`
- `agent/docs/runtime.md`
- `agent/docs/expert-runtime-service-design-20260418.md`
- `agent/docs/router-prompt-followups-20260416.md`
- `agent/retrieval/README.md`
- `agent/docs/weekly_reports/**`
- `agent/docs/manual/**`
- `agent/skills/**/SKILL.md`

Some older Chinese Markdown files show mojibake in the current shell environment. Treat those files as historical sources and prefer this `current/` directory for handoff.
