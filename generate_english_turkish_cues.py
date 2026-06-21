"""Generate Turkish cue data for English 4000 production cards."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

import spanish_deck


OUTPUT_PATH = Path("generated/english_4000/english_turkish_production.tsv")
CACHE_PATH = Path("generated/english_4000/mymemory_cache.json")
MYMEMORY_URL = "https://api.mymemory.translated.net/get"


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(" ".join(text.split()))


def source_id(row: Dict[str, str]) -> str:
    return "::".join(
        [
            row.get("deck", ""),
            row.get("card_number", ""),
            strip_html(row.get("english_word", "")).lower(),
        ]
    )


def source_sort_rank(deck: str) -> int:
    for index in range(1, 7):
        if deck.endswith(f"::{index}.Book"):
            return index
    if deck.endswith("::Extra"):
        return 7
    return 99


def source_card_number(value: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", value or "")]
    return tuple(numbers or [999999])


def difficulty_order(source_rows: List[Dict[str, str]]) -> Dict[str, int]:
    source_file_indexes = {id(row): index for index, row in enumerate(source_rows, start=1)}
    sorted_rows = sorted(
        source_rows,
        key=lambda row: (
            source_sort_rank(row.get("deck", "")),
            source_file_indexes.get(id(row), 999999),
            source_card_number(row.get("card_number", "")),
            strip_html(row.get("english_word", "")).lower(),
            strip_html(row.get("english_meaning", "")).lower(),
        ),
    )
    return {source_id(row): index for index, row in enumerate(sorted_rows, start=1)}


def cue_source(row: Dict[str, str]) -> str:
    meaning = strip_html(row.get("english_meaning", ""))
    return meaning or strip_html(row.get("english_word", ""))


def load_existing(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["SourceID"]: row for row in csv.DictReader(handle, delimiter="\t")}


def load_cache(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def translate_mymemory(text: str, cache: Dict[str, str], delay: float = 0.05) -> str:
    text = strip_html(text)
    if not text:
        return ""
    if text in cache:
        return cache[text]
    params = urllib.parse.urlencode({"q": text, "langpair": "en|tr"})
    request = urllib.request.Request(
        f"{MYMEMORY_URL}?{params}",
        headers={"User-Agent": "anki-language-deck-builder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    translated = strip_html(payload.get("responseData", {}).get("translatedText", ""))
    cache[text] = translated
    time.sleep(delay)
    return translated


def build_rows(
    source_rows: List[Dict[str, str]],
    existing: Dict[str, Dict[str, str]],
    cache: Dict[str, str],
    limit: int | None,
    output_path: Path | None = None,
    cache_path: Path | None = None,
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    order_map = difficulty_order(source_rows)
    for index, row in enumerate(source_rows, start=1):
        sid = source_id(row)
        order = order_map.get(sid, index)
        previous = existing.get(sid, {})
        source_text = cue_source(row)
        turkish_cue = previous.get("TurkishCue", "").strip()
        status = previous.get("Status", "").strip()
        if not turkish_cue:
            if limit is None or order <= limit:
                try:
                    turkish_cue = translate_mymemory(source_text, cache)
                    status = "draft_mymemory"
                except Exception as error:
                    turkish_cue = ""
                    status = f"error:{type(error).__name__}"
            else:
                status = "pending"
        rows.append(
            {
                "SourceID": sid,
                "Order": str(order),
                "SourceDeck": row.get("deck", ""),
                "SourceCard": row.get("card_number", ""),
                "English": strip_html(row.get("english_word", "")),
                "EnglishMeaning": strip_html(row.get("english_meaning", "")),
                "EnglishExample": strip_html(row.get("english_example", "")),
                "CueSource": source_text,
                "TurkishCue": turkish_cue,
                "Status": status,
            }
        )
        if index % 25 == 0:
            if cache_path is not None:
                save_cache(cache_path, cache)
            if output_path is not None:
                write_rows(output_path, rows)
    return rows


def write_rows(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "SourceID",
        "Order",
        "SourceDeck",
        "SourceCard",
        "English",
        "EnglishMeaning",
        "EnglishExample",
        "CueSource",
        "TurkishCue",
        "Status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Turkish cue TSV for English 4000 production cards.")
    parser.add_argument("--source", default="4000 Essential English Words.txt")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--cache", default=str(CACHE_PATH))
    parser.add_argument("--limit", type=int, help="Translate only the first N missing cues; keep later rows pending.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_rows = spanish_deck.parse_source_deck(args.source)
    output = Path(args.output)
    cache_path = Path(args.cache)
    existing = load_existing(output)
    cache = load_cache(cache_path)
    rows = build_rows(source_rows, existing, cache, args.limit, output, cache_path)
    write_rows(output, rows)
    save_cache(cache_path, cache)
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    print(json.dumps({"rows": len(rows), "status": counts, "output": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
