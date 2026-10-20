"""Local CDS Hooks endpoint for the 54 draft agents.

Epic will not call this process. It shows the contract:

    GET  /cds-services
    POST /cds-services/{id}

Start it only with --insecure-dev. Production needs TLS and verification of
the JWT Epic sends, using Epic's JWKS. This script does not do that.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cards import by_id, discovery, draft_card


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/cds-services":
            self._send(200, discovery())
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        prefix = "/cds-services/"
        if not self.path.startswith(prefix):
            self._send(404, {"error": "not found"})
            return
        agent_id = self.path[len(prefix) :].strip("/")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "request body is not JSON"})
            return
        agent = by_id(agent_id)
        if agent is None:
            self._send(404, {"error": f"unknown service {agent_id}"})
            return
        self._send(200, draft_card(agent))

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--insecure-dev", action="store_true")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    if not args.insecure_dev:
        raise SystemExit("Refusing to listen. Pass --insecure-dev. This server does not verify Epic's JWT.")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"CDS Hooks draft listening on http://127.0.0.1:{args.port}/cds-services")
    server.serve_forever()


if __name__ == "__main__":
    main()
