#!/usr/bin/env python3
"""Minimal reverse proxy for exposing a private MCP HTTP endpoint."""

from __future__ import annotations

import argparse
import http.client
import socketserver
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}


def filter_headers(raw_headers: BaseHTTPRequestHandler) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in raw_headers.headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        headers[key] = value
    return headers


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        upstream: str,
        timeout: float,
    ) -> None:
        super().__init__(server_address, handler_class)
        parsed = urllib.parse.urlparse(upstream)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("upstream must start with http:// or https://")
        self.upstream = parsed
        self.timeout = timeout


class MCPProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def do_PUT(self) -> None:
        self._proxy()

    def do_PATCH(self) -> None:
        self._proxy()

    def do_DELETE(self) -> None:
        self._proxy()

    def do_OPTIONS(self) -> None:
        self._proxy()

    def do_HEAD(self) -> None:
        self._proxy()

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stdout.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def _proxy(self) -> None:
        server: ProxyServer = self.server  # type: ignore[assignment]
        upstream = server.upstream
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length > 0 else None

        path = self.path
        if upstream.path and upstream.path != "/":
            if path.startswith("/"):
                path = upstream.path.rstrip("/") + path
            else:
                path = upstream.path.rstrip("/") + "/" + path
        elif not path.startswith("/"):
            path = "/" + path

        target_host = upstream.hostname
        if target_host is None:
            self.send_error(500, "invalid upstream host")
            return

        connection_cls = http.client.HTTPSConnection if upstream.scheme == "https" else http.client.HTTPConnection
        connection = connection_cls(
            host=target_host,
            port=upstream.port,
            timeout=server.timeout,
        )

        headers = filter_headers(self)
        headers["Host"] = target_host if upstream.port is None else f"{target_host}:{upstream.port}"
        headers["X-Forwarded-For"] = self.client_address[0]
        headers["X-Forwarded-Proto"] = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"
        if "MCP-Protocol-Version" in self.headers:
            headers["MCP-Protocol-Version"] = self.headers["MCP-Protocol-Version"]

        try:
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()

            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() in HOP_BY_HOP_HEADERS:
                    continue
                self.send_header(key, value)
            self.end_headers()

            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception as exc:  # noqa: BLE001
            self.send_error(502, f"proxy error: {type(exc).__name__}: {exc}")
        finally:
            connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expose a private MCP endpoint through a simple reverse proxy.")
    parser.add_argument(
        "--listen-host",
        default="127.0.0.1",
        help="Local bind host. Use 127.0.0.1 when fronted by cloudflared.",
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=8788,
        help="Local bind port.",
    )
    parser.add_argument(
        "--upstream",
        default="http://10.181.92.106:18081",
        help="Private upstream base URL, without trailing slash preferred.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Upstream socket timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ProxyServer(
        (args.listen_host, args.listen_port),
        MCPProxyHandler,
        upstream=args.upstream.rstrip("/"),
        timeout=args.timeout,
    )
    print(f"Listening on http://{args.listen_host}:{args.listen_port}")
    print(f"Forwarding to {args.upstream.rstrip('/')}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
