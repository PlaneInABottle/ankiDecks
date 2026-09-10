"""Download rolling Tatoeba exports used as generator inputs (stdlib only).

The 4 archives (~38MB) are NOT tracked in git anymore (see .gitignore).
Run this after a fresh clone, then run the generators as usual.

    python3 fetch_tatoeba.py
    python3 fetch_tatoeba.py --dir generated/sources/tatoeba --force

Sources (verified HTTP 200):
    https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2
    https://downloads.tatoeba.org/exports/per_language/spa/spa_sentences.tsv.bz2
    https://downloads.tatoeba.org/exports/per_language/spa/spa-eng_links.tsv.bz2
    https://downloads.tatoeba.org/exports/sentences_with_audio.tar.bz2

Note: exports are rolling snapshots, so a fresh download is NEWER than the
files previous runs used. Small derived selections
(selected_*_sentences.tsv, selected_spa_eng_pairs.tsv) stay tracked in git,
so day-to-day work is reproducible; re-run the generators after fetching
if you want the latest upstream sentences.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

BASE = "https://downloads.tatoeba.org/exports"
FILES = [
    "per_language/eng/eng_sentences.tsv.bz2",
    "per_language/spa/spa_sentences.tsv.bz2",
    "per_language/spa/spa-eng_links.tsv.bz2",
    "sentences_with_audio.tar.bz2",
]
LOCAL_NAMES = {
    "per_language/eng/eng_sentences.tsv.bz2": "eng_sentences.tsv.bz2",
    "per_language/spa/spa_sentences.tsv.bz2": "spa_sentences.tsv.bz2",
    "per_language/spa/spa-eng_links.tsv.bz2": "spa-eng_links.tsv.bz2",
    "sentences_with_audio.tar.bz2": "sentences_with_audio.tar.bz2",
}
DEFAULT_DIR = Path("generated/sources/tatoeba")


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "anki-decks-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as handle:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
    os.replace(tmp, dest)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download Tatoeba source archives.")
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="Target directory")
    parser.add_argument("--force", action="store_true", help="Re-download existing files")
    args = parser.parse_args(argv)

    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)
    failed = 0
    for remote in FILES:
        dest = target / LOCAL_NAMES[remote]
        if dest.exists() and not args.force:
            print(f"skip (exists): {dest}")
            continue
        url = f"{BASE}/{remote}"
        print(f"fetch: {url} -> {dest}")
        try:
            download(url, dest)
            print(f"  ok: {dest.stat().st_size / 1e6:.1f} MB")
        except Exception as exc:  # noqa: BLE001 - report and continue with rest
            print(f"  FAIL: {exc}", file=sys.stderr)
            failed += 1
    if failed:
        print(f"{failed} download(s) failed", file=sys.stderr)
        return 1
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
