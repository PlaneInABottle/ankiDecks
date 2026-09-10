"""Shared AnkiConnect client (stdlib only).

sync_english_mastery_to_anki.py ve sync_spanish_core_to_anki.py içindeki
`invoke` birebir aynıydı; sync_4000_production_to_anki.py'deki sürüm de
aynı retry mantığı + Content-Type header kullanıyor. Tek kanonik sürüm burada.

Mevcut sync dosyaları `from sync_core import invoke` ile ince alias tutar,
böylece testlerdeki `patch.object(sync_..._to_anki, "invoke", ...)` çalışmaya
devam eder.
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
