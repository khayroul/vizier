"""Thin HTTP wrapper around select_design_systems() for the dashboard.

Exposes a single GET endpoint that the Refine dashboard calls
to preview design system scoring. This is NOT a production API —
it is a local development proxy that bridges the TypeScript frontend
to the Python scoring function.

Usage:
    python3.11 tools/design_selector_api.py
    # GET http://localhost:8080/design-systems?client_id=dmb&artifact_family=poster&top_k=3
"""
from __future__ import annotations

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from contracts.routing import select_design_systems

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


class DesignSelectorHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/design-systems":
            self._respond(404, {"error": "Not found"})
            return

        params = parse_qs(parsed.query)
        client_id = params.get("client_id", [None])[0]
        if not client_id:
            self._respond(400, {"error": "client_id is required"})
            return

        artifact_family = params.get("artifact_family", [None])[0]
        top_k = int(params.get("top_k", ["3"])[0])

        try:
            systems = select_design_systems(
                client_id=client_id,
                artifact_family=artifact_family or None,
                top_k=top_k,
            )
            self._respond(200, {"systems": systems})
        except FileNotFoundError as exc:
            self._respond(404, {"systems": [], "error": str(exc)})
        except Exception as exc:
            logger.exception("select_design_systems failed")
            self._respond(500, {"systems": [], "error": str(exc)})

    def _respond(self, status: int, body: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, fmt: str, *args: object) -> None:
        logger.info(fmt, *args)


def main() -> None:
    server = HTTPServer(("0.0.0.0", 8080), DesignSelectorHandler)
    logger.info("Design selector API listening on :8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
