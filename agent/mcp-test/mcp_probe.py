#!/usr/bin/env python3
"""Probe an MCP server over HTTP and validate basic initialization."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_PROTOCOL_VERSIONS = [
    "2025-03-26",
    "2024-11-05",
]

DEFAULT_VPN_CONNECTOR = r"C:\Program Files\OpenVPN Connect\ovpnconnector.exe"
DEFAULT_VPN_PROFILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "proxy", "zhduser.ovpn")
)
DEFAULT_VPN_LOG = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "ovpnconnector.log")
)


@dataclass
class ProbeResult:
    ok: bool
    status: int | None
    reason: str | None
    headers: dict[str, str]
    body_text: str
    json_body: Any | None
    error: str | None = None


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str


def run_command(args: list[str], timeout: float) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            ok=completed.returncode == 0,
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
    except Exception as exc:  # noqa: BLE001
        return CommandResult(
            ok=False,
            returncode=-1,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )


def service_is_present(service_name: str) -> bool:
    result = run_command(["sc.exe", "query", service_name], timeout=10)
    return result.ok


def configure_vpn_profile(connector: str, profile: str, log_path: str, timeout: float) -> tuple[bool, str]:
    profile_result = run_command(
        [connector, "set-config", "profile", profile],
        timeout=timeout,
    )
    if not profile_result.ok:
        return False, (
            f"failed to set VPN profile: {profile_result.stderr or profile_result.stdout or profile_result.returncode}"
        )

    log_result = run_command(
        [connector, "set-config", "log", log_path],
        timeout=timeout,
    )
    if not log_result.ok:
        return False, f"failed to set VPN log path: {log_result.stderr or log_result.stdout or log_result.returncode}"

    return True, "VPN connector profile configured"


def start_vpn(connector: str, timeout: float) -> tuple[bool, str]:
    result = run_command([connector, "start"], timeout=timeout)
    if result.ok:
        return True, result.stdout or "VPN start command sent"
    return False, result.stderr or result.stdout or f"connector exited with {result.returncode}"


def stop_vpn(connector: str, timeout: float) -> tuple[bool, str]:
    result = run_command([connector, "stop"], timeout=timeout)
    if result.ok:
        return True, result.stdout or "VPN stop command sent"
    return False, result.stderr or result.stdout or f"connector exited with {result.returncode}"


def tail_text_file(path: str, limit: int = 2000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read()
        if len(content) > limit:
            return content[-limit:]
        return content
    except OSError as exc:
        return f"unable to read log: {exc}"


def wait_for_tcp(host: str, port: int, timeout: float, interval: float) -> tuple[bool, str]:
    deadline = time.time() + timeout
    last_message = "timeout waiting for TCP connectivity"
    while time.time() < deadline:
        ok, message = tcp_check(host, port, interval)
        if ok:
            return True, message
        last_message = message
        time.sleep(interval)
    return False, last_message


def build_opener(proxy: str | None) -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str,
    timeout: float,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> ProbeResult:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        method=method,
        headers=headers or {},
    )

    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            body_text = raw.decode("utf-8", errors="replace")
            json_body = None
            if body_text:
                try:
                    json_body = json.loads(body_text)
                except json.JSONDecodeError:
                    json_body = None
            return ProbeResult(
                ok=True,
                status=resp.status,
                reason=resp.reason,
                headers=dict(resp.headers.items()),
                body_text=body_text,
                json_body=json_body,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        body_text = raw.decode("utf-8", errors="replace")
        json_body = None
        if body_text:
            try:
                json_body = json.loads(body_text)
            except json.JSONDecodeError:
                json_body = None
        return ProbeResult(
            ok=False,
            status=exc.code,
            reason=exc.reason,
            headers=dict(exc.headers.items()),
            body_text=body_text,
            json_body=json_body,
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(
            ok=False,
            status=None,
            reason=None,
            headers={},
            body_text="",
            json_body=None,
            error=f"{type(exc).__name__}: {exc}",
        )


def tcp_check(host: str, port: int, timeout: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "TCP connect succeeded"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def print_block(title: str, content: str) -> None:
    print(f"\n=== {title} ===")
    print(content)


def summarize_result(name: str, result: ProbeResult) -> None:
    status = result.status if result.status is not None else "n/a"
    reason = result.reason or result.error or "n/a"
    print(f"{name}: status={status}, reason={reason}")
    if result.headers:
        print("headers:")
        for key, value in sorted(result.headers.items()):
            print(f"  {key}: {value}")
    if result.body_text:
        preview = result.body_text
        if len(preview) > 1500:
            preview = preview[:1500] + "\n...<truncated>"
        print("body:")
        print(preview)
    elif result.error:
        print(f"error: {result.error}")


def initialize_sequence(
    opener: urllib.request.OpenerDirector,
    url: str,
    timeout: float,
    protocol_version: str,
    client_name: str,
    client_version: str,
    extra_headers: dict[str, str],
) -> tuple[bool, str]:
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "clientInfo": {
                "name": client_name,
                "version": client_version,
            },
        },
    }
    init_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": protocol_version,
    }
    init_headers.update(extra_headers)
    init_result = request(
        opener,
        url,
        method="POST",
        timeout=timeout,
        headers=init_headers,
        payload=init_payload,
    )
    summarize_result(f"initialize ({protocol_version})", init_result)
    if not init_result.ok or not isinstance(init_result.json_body, dict):
        return False, f"initialize failed for protocol {protocol_version}"

    result_payload = init_result.json_body.get("result")
    if not isinstance(result_payload, dict):
        return False, f"server returned non-success initialize payload for {protocol_version}"

    session_id = (
        init_result.headers.get("Mcp-Session-Id")
        or init_result.headers.get("MCP-Session-Id")
        or init_result.headers.get("mcp-session-id")
    )

    notif_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": protocol_version,
    }
    notif_headers.update(extra_headers)
    if session_id:
        notif_headers["MCP-Session-Id"] = session_id

    initialized_result = request(
        opener,
        url,
        method="POST",
        timeout=timeout,
        headers=notif_headers,
        payload={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
    )
    summarize_result("notifications/initialized", initialized_result)

    tools_result = request(
        opener,
        url,
        method="POST",
        timeout=timeout,
        headers=notif_headers,
        payload={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    )
    summarize_result("tools/list", tools_result)

    ok = tools_result.ok and isinstance(tools_result.json_body, dict)
    return ok, f"initialize succeeded with protocol {protocol_version}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe an MCP HTTP endpoint and verify initialize flow."
    )
    parser.add_argument(
        "--url",
        default="http://10.181.92.106:18081/mcp-servers/aisecurity",
        help="MCP server URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Optional HTTP/HTTPS proxy URL, for example http://127.0.0.1:7890.",
    )
    parser.add_argument(
        "--client-name",
        default="mcp-test-probe",
        help="Client name sent in initialize.",
    )
    parser.add_argument(
        "--client-version",
        default="0.1.0",
        help="Client version sent in initialize.",
    )
    parser.add_argument(
        "--protocol-version",
        action="append",
        dest="protocol_versions",
        help="Protocol version to try. Repeat to test multiple versions.",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Extra HTTP header in 'Name: Value' format. Repeatable.",
    )
    parser.add_argument(
        "--vpn-profile",
        default=None,
        help=f"OpenVPN profile path. Default: {DEFAULT_VPN_PROFILE}",
    )
    parser.add_argument(
        "--vpn-connector",
        default=DEFAULT_VPN_CONNECTOR,
        help=f"ovpnconnector.exe path. Default: {DEFAULT_VPN_CONNECTOR}",
    )
    parser.add_argument(
        "--vpn-log",
        default=DEFAULT_VPN_LOG,
        help=f"VPN connector log path. Default: {DEFAULT_VPN_LOG}",
    )
    parser.add_argument(
        "--connect-vpn",
        action="store_true",
        help="Start OpenVPN Connect via ovpnconnector before probing.",
    )
    parser.add_argument(
        "--disconnect-vpn",
        action="store_true",
        help="Stop OpenVPN Connect after probe finishes.",
    )
    parser.add_argument(
        "--vpn-wait",
        type=float,
        default=15.0,
        help="Seconds to wait for VPN connectivity after start.",
    )
    return parser.parse_args()


def parse_headers(raw_headers: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in raw_headers:
        if ":" not in item:
            raise ValueError(f"invalid header format: {item!r}")
        key, value = item.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"invalid header name: {item!r}")
        parsed[key] = value
    return parsed


def main() -> int:
    args = parse_args()
    parsed = urllib.parse.urlparse(args.url)
    if not parsed.hostname or not parsed.port:
        print("URL must include hostname and port, for example http://host:18081/path", file=sys.stderr)
        return 2

    opener = build_opener(args.proxy)
    protocol_versions = args.protocol_versions or DEFAULT_PROTOCOL_VERSIONS
    vpn_profile = os.path.abspath(args.vpn_profile) if args.vpn_profile else DEFAULT_VPN_PROFILE
    vpn_log = os.path.abspath(args.vpn_log)
    try:
        extra_headers = parse_headers(args.header)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Target URL: {args.url}")
    print(f"Proxy: {args.proxy or 'disabled'}")
    print(f"Timeout: {args.timeout}s")
    if extra_headers:
        print(f"Extra headers: {', '.join(sorted(extra_headers))}")
    if args.connect_vpn:
        print(f"VPN profile: {vpn_profile}")
        print(f"VPN connector: {args.vpn_connector}")

    disconnect_requested = args.disconnect_vpn
    exit_code = 1

    try:
        if args.connect_vpn:
            if not os.path.exists(args.vpn_connector):
                print_block("VPN", f"connector not found: {args.vpn_connector}")
                return 2
            if not os.path.exists(vpn_profile):
                print_block("VPN", f"profile not found: {vpn_profile}")
                return 2
            if not service_is_present("agent_ovpnconnect"):
                print_block(
                    "VPN",
                    "OpenVPN service 'agent_ovpnconnect' is missing. Install OpenVPN Connect and initialize it once as administrator.",
                )
                return 2

            ok, message = configure_vpn_profile(args.vpn_connector, vpn_profile, vpn_log, args.timeout)
            print_block("VPN Config", message)
            if not ok:
                return 1

            ok, message = start_vpn(args.vpn_connector, args.timeout)
            print_block("VPN Start", message)
            if not ok:
                print_block("VPN Log", tail_text_file(vpn_log))
                return 1

            wait_ok, wait_message = wait_for_tcp(
                parsed.hostname,
                parsed.port,
                args.vpn_wait,
                min(2.0, max(0.5, args.timeout / 4)),
            )
            print_block("VPN Wait", wait_message)
            if not wait_ok:
                print_block("VPN Log", tail_text_file(vpn_log))
                return 1

        tcp_ok, tcp_message = tcp_check(parsed.hostname, parsed.port, args.timeout)
        print_block("TCP Check", tcp_message)
        if not tcp_ok:
            return 1

        get_result = request(
            opener,
            args.url,
            method="GET",
            timeout=args.timeout,
            headers={
                "Accept": "application/json, text/event-stream",
                **extra_headers,
            },
        )
        summarize_result("GET probe", get_result)

        for version in protocol_versions:
            ok, message = initialize_sequence(
                opener,
                args.url,
                args.timeout,
                version,
                args.client_name,
                args.client_version,
                extra_headers,
            )
            print_block("Initialize Attempt", message)
            if ok:
                print("\nMCP initialization probe succeeded.")
                exit_code = 0
                return exit_code

        print("\nMCP initialization probe failed.")
        exit_code = 1
        return exit_code
    finally:
        if disconnect_requested and args.connect_vpn:
            ok, message = stop_vpn(args.vpn_connector, args.timeout)
            print_block("VPN Stop", message)
            if not ok:
                print_block("VPN Log", tail_text_file(vpn_log))


if __name__ == "__main__":
    raise SystemExit(main())
