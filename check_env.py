"""Environment sanity check for this repo (stdlib only).

Usage:
    python3 check_env.py
    python3 check_env.py --strict   # fail on missing optional deps too
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import urllib.request


REQUIRED_PYTHON = (3, 10)
ANKI_CONNECT_URL = "http://127.0.0.1:8765"


def check_python() -> tuple[bool, str]:
    ok = sys.version_info[:2] >= REQUIRED_PYTHON
    return ok, f"python {sys.version.split()[0]} (>=3.10 gerekli)"


def check_ffmpeg() -> tuple[bool, str]:
    ok = shutil.which("ffmpeg") is not None
    return ok, "ffmpeg " + ("bulundu" if ok else "bulunamadı (brew/apt ile kur)")


def check_tts() -> tuple[bool, str]:
    if shutil.which("say") is not None:
        return True, "TTS: macOS `say` bulundu"
    for alt in ("espeak-ng", "espeak", "piper"):
        if shutil.which(alt) is not None:
            return True, f"TTS: `{alt}` bulundu (say yok, fallback kullanılacak)"
    return False, "TTS bulunamadı (say/espeak-ng yok; --no-audio ile çalışılabilir)"


def check_env_file() -> tuple[bool, str]:
    if os.path.exists(".env.example"):
        return True, ".env.example mevcut"
    return False, ".env.example eksik"


def check_pexels_key() -> tuple[bool, str]:
    key = ""
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as handle:
            for line in handle:
                if line.strip().startswith("PEXELS_API_KEY="):
                    key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    if key:
        return True, "PEXELS_API_KEY ayarlı (görsel indirilebilir)"
    return False, "PEXELS_API_KEY yok (.env'ye ekle; görsel olmadan da çalışır)"


def check_ankiconnect() -> tuple[bool, str]:
    try:
        payload = b'{"action":"version","version":6}'
        req = urllib.request.Request("http://127.0.0.1:8765", data=payload)
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return True, "AnkiConnect erişilebilir (Anki açık)"
    except Exception:
        pass
    return False, "AnkiConnect yok (Anki kapalı olabilir; sadece sync için gerekli)"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Ortam kontrolü")
    parser.add_argument("--strict", action="store_true", help="Opsiyonel eksiklerde de non-zero dön")
    args = parser.parse_args(argv)

    required = [("python", *check_python()), ("ffmpeg", *check_ffmpeg())]
    optional = [
        ("tts", *check_tts()),
        ("env-example", *check_env_file()),
        ("pexels", *check_pexels_key()),
        ("ankiconnect", *check_ankiconnect()),
    ]

    failed_required = False
    print("required:")
    for name, ok, msg in required:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}: {msg}")
        if not ok:
            failed_required = True

    print("optional:")
    failed_optional = False
    for name, ok, msg in optional:
        print(f"  [{'OK' if ok else '--'}] {name}: {msg}")
        if not ok:
            failed_optional = True

    if failed_required:
        return 1
    if args.strict and failed_optional:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
