"""Shared AnkiConnect client (stdlib only).

Single canonical `invoke` with retry logic + Content-Type header, used by the
sync scripts. Tests patch `invoke` on the sync modules via
`patch.object(sync_..._to_anki, "invoke", ...)`; the sync files keep a thin
alias (`from sync_core import invoke`) so that keeps working.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

ANKI_CONNECT_URL = "http://127.0.0.1:8765"


def invoke(action: str, **params: Any) -> Any:
    payload = json.dumps({"action": action, "params": params, "version": 6}).encode("utf-8")
    request = urllib.request.Request(
        ANKI_CONNECT_URL, payload, headers={"Content-Type": "application/json"}
    )
    for attempt in range(3):
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("error"):
            return result["result"]
        if result["error"] != "collection is not available" or attempt == 2:
            raise RuntimeError(result["error"])
        time.sleep(2)
    raise RuntimeError("collection is not available")


def invoke_multi(actions: list[dict], batch_size: int = 50) -> list:
    results: list = []
    for offset in range(0, len(actions), batch_size):
        batch = actions[offset : offset + batch_size]
        payload = json.dumps({"action": "multi", "params": {"actions": batch}, "version": 6}).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            ANKI_CONNECT_URL, payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("error"):
            raise RuntimeError(result["error"])
        for item in result["result"]:
            if isinstance(item, dict) and item.get("error"):
                raise RuntimeError(item["error"])
            if isinstance(item, dict) and "result" in item:
                results.append(item.get("result"))
            else:
                results.append(item)
    return results
