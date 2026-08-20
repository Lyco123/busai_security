#!/usr/bin/env python3
"""
Audit the aisecurity MCP server's tools and produce a plug-in report:
  - Full list of tools with name, description, required params
  - Clarity assessment for each tool (is it clear enough for an LLM agent?)
  - How to wire each tool into the agent's MCPToolProvider / LocalToolProvider
"""

from __future__ import annotations

import json
import textwrap
import urllib.error
import urllib.request
from typing import Any

URL = "https://buso-rpformcp.canocache.com:443/mcp-servers/aisecurity"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-03-26",
    "User-Agent": "Mozilla/5.0 (compatible; mcp-tool-audit/0.1)",
}
TIMEOUT = 10.0

# Heuristics for clarity assessment
MIN_DESC_WORDS = 6          # description too short if below this
MIN_PARAM_DESC_WORDS = 3    # param description too short if below this


def post(payload: dict[str, Any]) -> Any:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read()
        return json.loads(body) if body.strip() else {}


def word_count(text: str) -> int:
    return len(text.split()) if text else 0


def assess_tool(tool: dict[str, Any]) -> list[str]:
    """Return a list of clarity issues (empty = all good)."""
    issues = []
    desc = tool.get("description", "")
    if word_count(desc) < MIN_DESC_WORDS:
        issues.append(f"description too short ({word_count(desc)} words)")

    schema = tool.get("inputSchema", {})
    props: dict[str, Any] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])

    if not props:
        issues.append("no parameters defined")

    for pname, pdef in props.items():
        pdesc = pdef.get("description", "")
        if word_count(pdesc) < MIN_PARAM_DESC_WORDS:
            issues.append(f"param '{pname}' description too short ({word_count(pdesc)} words)")
        if not pdef.get("type"):
            issues.append(f"param '{pname}' has no type")

    return issues


def format_schema_short(schema: dict[str, Any]) -> str:
    props: dict[str, Any] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])
    parts = []
    for pname, pdef in props.items():
        ptype = pdef.get("type", "?")
        req_mark = "*" if pname in required else ""
        parts.append(f"{pname}{req_mark}:{ptype}")
    return "  params: " + (", ".join(parts) if parts else "(none)")


def plug_in_snippet(tool: dict[str, Any]) -> str:
    name = tool["name"]
    schema = tool.get("inputSchema", {})
    required = schema.get("required", [])
    props = schema.get("properties", {})

    # Build a minimal args object for the snippet
    args_lines = []
    for p in required:
        ptype = props.get(p, {}).get("type", "string")
        if ptype == "integer":
            args_lines.append(f'    {p}: 1,')
        elif ptype == "boolean":
            args_lines.append(f'    {p}: false,')
        elif ptype == "array":
            args_lines.append(f'    {p}: [],')
        elif ptype == "object":
            args_lines.append(f'    {p}: {{}},')
        else:
            args_lines.append(f'    {p}: "...",')

    args_str = "\n".join(args_lines) if args_lines else "    // no required params"
    return textwrap.dedent(f"""\
        // In MCPToolProvider.callTool or ScopedToolProvider override:
        if (name === '{name}') {{
          // args shape (required fields marked):
          // {json.dumps({p: props.get(p,{}).get("type","?") for p in required})}
          return this.mcpCall('{name}', args);
        }}
    """)


def main() -> int:
    # initialize
    resp = post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mcp-tool-audit", "version": "0.1.0"},
        },
    })
    server_info = resp.get("result", {}).get("serverInfo", {})
    print(f"Server: {server_info.get('name')} v{server_info.get('version')}")
    print(f"Protocol: {resp.get('result', {}).get('protocolVersion')}\n")

    post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    resp = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools: list[dict[str, Any]] = resp.get("result", {}).get("tools", [])
    print(f"Total tools: {len(tools)}\n")
    print("=" * 100)

    clear_count = 0
    unclear_count = 0
    all_issues: list[tuple[str, list[str]]] = []

    for tool in tools:
        name = tool.get("name", "?")
        desc = tool.get("description", "(no description)")
        schema = tool.get("inputSchema", {})
        required = schema.get("required", [])
        issues = assess_tool(tool)

        clarity = "CLEAR" if not issues else "NEEDS WORK"
        if not issues:
            clear_count += 1
        else:
            unclear_count += 1
            all_issues.append((name, issues))

        print(f"[{clarity}] {name}")
        # wrap description
        for line in textwrap.wrap(desc, width=90, initial_indent="  desc: ", subsequent_indent="        "):
            print(line)
        print(format_schema_short(schema))
        if required:
            print(f"  required: {', '.join(required)}")
        if issues:
            for issue in issues:
                print(f"  ⚠  {issue}")
        print()

    print("=" * 100)
    print(f"\nClarity summary: {clear_count} clear, {unclear_count} need work\n")

    # ── Plug-in guide ──────────────────────────────────────────────────────────
    print("=" * 100)
    print("HOW TO PLUG INTO THE AGENT")
    print("=" * 100)
    print(textwrap.dedent("""
    The agent already has a commented-out MCPToolProvider skeleton in runtime.ts.
    To wire up this MCP server:

    1. Set env var MCP_SERVER_URL = "https://buso-rpformcp.canocache.com/mcp-servers/aisecurity"
       in wrangler.toml (as a [vars] entry) or in the Cloudflare dashboard.

    2. Uncomment MCPToolProvider in runtime.ts and fix the two fetch calls:
         POST /tools/list  → { jsonrpc:"2.0", id:1, method:"tools/list", params:{} }
         POST /tools/call  → { jsonrpc:"2.0", id:1, method:"tools/call",
                                params:{ name, arguments: args } }
       Add header: "User-Agent: Mozilla/5.0 (compatible; bus-agent/1.0)"

    3. In createToolProvider(env), switch:
         return new LocalToolProvider(env.DB);
       to:
         if (env.MCP_SERVER_URL) return new MCPToolProvider(env.MCP_SERVER_URL);
         return new LocalToolProvider(env.DB);

    4. Optionally wrap with ScopedToolProvider to limit which tools the LLM sees:
         return new ScopedToolProvider(
           new MCPToolProvider(env.MCP_SERVER_URL),
           {},
           new Set(['get_base_odsJituanBsBus_queryById', ...])
         );

    The agent's chat-service passes the tool list directly to OpenAI function-calling,
    so the MCP tool descriptions/inputSchema become the function definitions verbatim.
    """))

    # ── Per-tool call snippets ─────────────────────────────────────────────────
    print("=" * 100)
    print("CALL SNIPPETS (for MCPToolProvider.callTool switch-case)")
    print("=" * 100)
    for tool in tools[:10]:  # show first 10; full list is long
        print(plug_in_snippet(tool))
    if len(tools) > 10:
        print(f"... and {len(tools) - 10} more tools (same pattern)\n")

    # ── Issues summary ─────────────────────────────────────────────────────────
    if all_issues:
        print("=" * 100)
        print("TOOLS NEEDING DESCRIPTION IMPROVEMENTS (before feeding to LLM)")
        print("=" * 100)
        for tname, issues in all_issues:
            print(f"  {tname}:")
            for issue in issues:
                print(f"    - {issue}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
