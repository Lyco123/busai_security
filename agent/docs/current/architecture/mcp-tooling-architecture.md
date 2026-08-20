# MCP Tooling Architecture

## Purpose

MCP is the external tool/data capability layer. The agent can list and call MCP tools through the Worker, while local tools and KB tools remain available through the same ToolProvider abstraction.

## Current Shape

```text
Worker Runner
  -> ToolProvider
  -> local tools
  -> query_kb
  -> MCP list/call helpers
  -> external MCP server
```

Primary files:

- `agent/src/tools/provider.ts`
- `agent/src/shared/mcp.ts`
- `agent/src/shared/mcp-field-semantics.ts`
- `agent/src/shared/*-profile-mcp.ts`
- `agent/src/domains/chat/router-tools.ts`
- `agent/src/domains/chat/router-tool-validation.ts`

## ToolProvider Boundary

`ToolProvider` is the runtime boundary for tool listing and execution. It can expose:

- built-in data/query tools
- rule tools
- KB retrieval tool
- MCP tools
- scoped tool subsets

Router tools and worker tools are separate concepts:

- Router tools decide which worker path to take.
- Worker tools are used by the selected worker to fetch data or perform side effects.

## MCP Documentation Sources

Key source documents:

- `agent/docs/MCP服务设计文档20260601.md`
- `agent/docs/MCP能力三分法与现状改造方案.md`
- `agent/docs/mcp-tool-description-guide.md`
- `agent/docs/mcp-usable-samples-20260601.md`
- `agent/docs/mcp-aisecurity-tools-description-review-20260605.md`
- `agent/docs/mcp_tools_交接模板.md`

## Current Risks

- Tool descriptions strongly affect router and worker behavior. Updates should be tested through routing and answer-quality regression cases.
- MCP field semantics are distributed across shared helpers and tool descriptions.
- Some report paths still use structured report source helpers instead of purely dynamic MCP calls.

## Gaps

- No single generated catalog currently lists all MCP tools, field meanings, descriptions, and consuming skills.
- No formal compatibility contract exists for MCP schema changes across report workers.
