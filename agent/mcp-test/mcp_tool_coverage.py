#!/usr/bin/env python3
"""
Call every tool listed by the MCP server with minimal stub arguments,
and report which ones succeed, which return errors, and which time out.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

URL = "https://buso-rpformcp.canocache.com:443/mcp-servers/aisecurity"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-03-26",
    "User-Agent": "Mozilla/5.0 (compatible; mcp-tool-coverage/0.1)",
}
TIMEOUT = 10.0


def post(payload: dict[str, Any]) -> tuple[int | None, Any, str | None]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body), None
            except json.JSONDecodeError:
                return resp.status, None, f"non-JSON body: {body[:200]}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, None, f"HTTP {exc.code}: {body[:300]}"
    except Exception as exc:  # noqa: BLE001
        return None, None, f"{type(exc).__name__}: {exc}"


def stub_args(schema: dict[str, Any]) -> dict[str, Any]:
    """Generate minimal stub arguments from a JSON schema."""
    props: dict[str, Any] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])
    # prefer required fields; fall back to all fields if none required
    targets = required if required else list(props.keys())[:3]
    args: dict[str, Any] = {}
    for key in targets:
        field = props.get(key, {})
        ftype = field.get("type", "string")
        if ftype == "integer":
            args[key] = 1
        elif ftype == "boolean":
            args[key] = False
        elif ftype == "array":
            args[key] = []
        elif ftype == "object":
            args[key] = {}
        else:
            args[key] = "test"
    return args


def main() -> int:
    # initialize
    status, body, err = post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mcp-tool-coverage", "version": "0.1.0"},
        },
    })
    if err or not body or "result" not in (body or {}):
        print(f"initialize failed: {err or body}")
        return 1
    print(f"initialize OK — server: {body['result'].get('serverInfo', {})}")

    # notifications/initialized
    post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    # tools/list
    status, body, err = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    if err or not body:
        print(f"tools/list failed: {err}")
        return 1

    tools: list[dict[str, Any]] = body.get("result", {}).get("tools", [])
    print(f"\nFound {len(tools)} tools. Calling each with stub args...\n")
    print(f"{'TOOL':<55} {'STATUS':<10} OUTCOME")
    print("-" * 100)

    ok_count = err_count = timeout_count = 0

    for i, tool in enumerate(tools):
        name: str = tool.get("name", f"tool_{i}")
        schema: dict[str, Any] = tool.get("inputSchema", {})
        args = stub_args(schema)

        status, body, err = post({
            "jsonrpc": "2.0",
            "id": i + 10,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        })

        if err and "timed out" in err.lower():
            outcome = "TIMEOUT"
            timeout_count += 1
        elif err:
            outcome = f"ERR  {err[:60]}"
            err_count += 1
        elif body and "error" in body:
            rpc_err = body["error"]
            msg = rpc_err.get("message", "") if isinstance(rpc_err, dict) else str(rpc_err)
            outcome = f"RPC_ERR  {msg[:60]}"
            err_count += 1
        elif body and "result" in body:
            result = body["result"]
            # check for isError flag in MCP tool result
            if isinstance(result, dict) and result.get("isError"):
                content = result.get("content", [{}])
                txt = content[0].get("text", "") if content else ""
                outcome = f"TOOL_ERR  {txt[:60]}"
                err_count += 1
            else:
                outcome = "OK"
                ok_count += 1
        else:
            outcome = f"UNKNOWN  status={status}"
            err_count += 1

        status_str = str(status) if status else "n/a"
        print(f"{name:<55} {status_str:<10} {outcome}")

    print("-" * 100)
    print(f"\nSummary: {ok_count} OK, {err_count} errors, {timeout_count} timeouts  (total {len(tools)})")
    return 0 if err_count == 0 and timeout_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
