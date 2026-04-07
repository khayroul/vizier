"""S4 Endpoint Testing Harness — cost logging + image saving."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS_FILE = Path("docs/decisions/s4_endpoint_results.json")
OUTPUT_DIR = Path("tests/s4/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_results() -> list[dict]:
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return []


def save_result(entry: dict) -> None:
    results = load_results()
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    results.append(entry)
    RESULTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"  logged: {entry['test']} | {entry['model']} | ${entry.get('cost_usd', '?')}")


def save_image(data: bytes, name: str) -> Path:
    path = OUTPUT_DIR / name
    path.write_bytes(data)
    print(f"  saved: {path} ({len(data)} bytes)")
    return path
