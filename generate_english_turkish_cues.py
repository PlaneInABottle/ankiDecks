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
GOOGLE_CACHE_PATH = Path("generated/english_4000/google_translate_cache.json")
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
GOOGLE_BATCH_SIZE = 80

SOURCE_SPECIFIC_TURKISH_OVERRIDES = {
    ("4000 Essential English Words::1.Book", "", "boat"): "tekne",
    ("4000 Essential English Words::1.Book", "", "capital"): "başkent",
    ("4000 Essential English Words::1.Book", "", "evil"): "kötü",
    ("4000 Essential English Words::1.Book", "", "laugh"): "gülüş",
    ("4000 Essential English Words::1.Book", "", "view"): "bakmak",
    ("4000 Essential English Words::1.Book", "", "avoid"): "kaçınmak",
    ("4000 Essential English Words::1.Book", "", "content"): "memnun",
    ("4000 Essential English Words::1.Book", "", "expect"): "beklemek",
    ("4000 Essential English Words::1.Book", "", "grade"): "not",
    ("4000 Essential English Words::1.Book", "", "secret"): "sır",
    ("4000 Essential English Words::1.Book", "", "ever"): "herhangi bir zaman",
    ("4000 Essential English Words::1.Book", "", "instead"): "yerine",
    ("4000 Essential English Words::1.Book", "", "football"): "amerikan futbolu",
    ("4000 Essential English Words::1.Book", "", "sense"): "sezmek",
    ("4000 Essential English Words::1.Book", "", "appeal"): "çekici gelmek",
    ("4000 Essential English Words::1.Book", "", "found"): "kurmak",
    ("4000 Essential English Words::1.Book", "", "direct"): "doğrudan",
    ("4000 Essential English Words::1.Book", "", "sheet"): "sayfa",
    ("4000 Essential English Words::1.Book", "", "across"): "karşısına",
    ("4000 Essential English Words::1.Book", "", "happen"): "denk gelmek",
    ("4000 Essential English Words::1.Book", "", "bother"): "zahmet etmek",
    ("4000 Essential English Words::1.Book", "", "fashionable"): "modaya uygun",
    ("4000 Essential English Words::Extra", "2_6", "boxers"): "boxer külot",
    ("4000 Essential English Words::Extra", "2_7", "cap"): "şapka",
    ("4000 Essential English Words::Extra", "2_40", "suit"): "takım elbise",
    ("4000 Essential English Words::Extra", "2_45", "tie"): "kravat",
    ("4000 Essential English Words::Extra", "3_52", "cricket"): "cırcır böceği",
    ("4000 Essential English Words::Extra", "3_75", "peanut"): "yer fıstığı",
    ("4000 Essential English Words::Extra", "3_77", "pistachio"): "antep fıstığı",
    ("4000 Essential English Words::Extra", "3_80", "beef"): "sığır eti",
    ("4000 Essential English Words::Extra", "3_116", "football"): "amerikan futbolu",
    ("4000 Essential English Words::Extra", "3_30", "seal"): "fok",
    ("4000 Essential English Words::Extra", "3_42", "mole"): "köstebek",
    ("4000 Essential English Words::Extra", "1_1_2", "temple"): "şakak",
    ("4000 Essential English Words::Extra", "1_1_17", "head"): "kafa",
    ("4000 Essential English Words::Extra", "1_1_22", "stomach"): "mide",
    ("4000 Essential English Words::Extra", "1_1_34", "palm"): "avuç içi",
    ("4000 Essential English Words::Extra", "1_1_40", "back"): "sırt",
    ("4000 Essential English Words::Extra", "1_1_41", "hip"): "kalça",
    ("4000 Essential English Words::Extra", "1_1_42", "bottom"): "kalça",
    ("4000 Essential English Words::Extra", "1_1_75", "navy"): "lacivert",
    ("4000 Essential English Words::3.Book", "", "found"): "kurmak",
    ("4000 Essential English Words::4.Book", "", "tie"): "bağlamak",
    ("4000 Essential English Words::4.Book", "", "found"): "dayandırmak",
}


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(" ".join(text.split()))


def strip_html_preserve_lines(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(text)


def normalize_turkish_cue(value: str) -> str:
    cue = strip_html(value)
    cue = re.sub(r"\s*\([^)]*\)\s*$", "", cue).strip()
    cue = cue.lower().replace("i̇", "i")
    return cue


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


def infer_pos(row: Dict[str, str]) -> str:
    meaning = strip_html(row.get("english_meaning", "")).lower()
    if meaning.startswith("to "):
        return "verb"
    if meaning.startswith(("a ", "an ", "the ")) and " is " in meaning[:80]:
        return "noun"
    if meaning.startswith(("if ", "when ", "something ", "someone ")):
        return "adjective"
    if " means " in meaning[:80]:
        return "adverb"
    return ""


def cue_source(row: Dict[str, str]) -> str:
    word = strip_html(row.get("english_word", ""))
    if not word:
        return ""
    if infer_pos(row) == "verb" and not word.lower().startswith("to "):
        return f"to {word}"
    if infer_pos(row) == "adjective":
        return f"to be {word}"
    return word


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
    translated = normalize_turkish_cue(payload.get("responseData", {}).get("translatedText", ""))
    cache[text] = translated
    time.sleep(delay)
    return translated


def translate_google(text: str, cache: Dict[str, str], delay: float = 0.03) -> str:
    text = strip_html(text)
    if not text:
        return ""
    if text in cache:
        return cache[text]
    params = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": "tr",
            "dt": "t",
            "q": text,
        }
    )
    request = urllib.request.Request(
        f"{GOOGLE_TRANSLATE_URL}?{params}",
        headers={"User-Agent": "anki-language-deck-builder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    translated = normalize_turkish_cue("".join(part[0] for part in payload[0] if part and part[0]))
    cache[text] = translated
    time.sleep(delay)
    return translated


def translate_google_batch(texts: List[str], cache: Dict[str, str], delay: float = 0.08) -> None:
    missing = []
    seen = set()
    for text in texts:
        text = strip_html(text)
        if not text or text in cache or text in seen:
            continue
        missing.append(text)
        seen.add(text)

    for offset in range(0, len(missing), GOOGLE_BATCH_SIZE):
        batch = missing[offset : offset + GOOGLE_BATCH_SIZE]
        params = urllib.parse.urlencode(
            {
                "client": "gtx",
                "sl": "en",
                "tl": "tr",
                "dt": "t",
                "q": "\n".join(batch),
            }
        )
        request = urllib.request.Request(
            f"{GOOGLE_TRANSLATE_URL}?{params}",
            headers={"User-Agent": "anki-language-deck-builder/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = strip_html_preserve_lines("".join(part[0] for part in payload[0] if part and part[0]))
        lines = [normalize_turkish_cue(line) for line in translated.splitlines()]
        if len(lines) != len(batch):
            for text in batch:
                translate_google(text, cache, delay=0)
        else:
            for text, line in zip(batch, lines):
                cache[text] = line
        time.sleep(delay)


def translate_cue(text: str, provider: str, cache: Dict[str, str]) -> str:
    if provider == "google":
        return translate_google(text, cache)
    if provider == "mymemory":
        return translate_mymemory(text, cache)
    raise ValueError(f"Unsupported provider: {provider}")


def prefetch_translations(texts: List[str], provider: str, cache: Dict[str, str]) -> None:
    if provider == "google":
        translate_google_batch(texts, cache)


def source_specific_override(row: Dict[str, str]) -> str:
    key = (
        row.get("deck", ""),
        row.get("card_number", ""),
        strip_html(row.get("english_word", "")).lower(),
    )
    return SOURCE_SPECIFIC_TURKISH_OVERRIDES.get(key, "")


def polish_cue_for_row(row: Dict[str, str], cue: str) -> str:
    cue = normalize_turkish_cue(cue)
    if infer_pos(row) == "adjective":
        cue = re.sub(r"\s+olmak$", "", cue).strip()
    return cue


def build_rows(
    source_rows: List[Dict[str, str]],
    existing: Dict[str, Dict[str, str]],
    cache: Dict[str, str],
    limit: int | None,
    output_path: Path | None = None,
    cache_path: Path | None = None,
    provider: str = "google",
    refresh: bool = False,
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    order_map = difficulty_order(source_rows)
    texts_to_translate = []
    for index, row in enumerate(source_rows, start=1):
        sid = source_id(row)
        order = order_map.get(sid, index)
        previous = existing.get(sid, {})
        if not refresh and previous.get("TurkishCue", "").strip():
            continue
        if limit is None or order <= limit:
            texts_to_translate.append(cue_source(row))
    prefetch_translations(texts_to_translate, provider, cache)
    if cache_path is not None:
        save_cache(cache_path, cache)

    for index, row in enumerate(source_rows, start=1):
        sid = source_id(row)
        order = order_map.get(sid, index)
        previous = existing.get(sid, {})
        source_text = cue_source(row)
        turkish_cue = "" if refresh else previous.get("TurkishCue", "").strip()
        status = "" if refresh else previous.get("Status", "").strip()
        if not turkish_cue:
            if limit is None or order <= limit:
                try:
                    turkish_cue = translate_cue(source_text, provider, cache)
                    status = f"draft_{provider}_word"
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
                "TurkishCue": source_specific_override(row) or polish_cue_for_row(row, turkish_cue),
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
    parser.add_argument("--cache", help="Translation cache path. Defaults to provider-specific cache.")
    parser.add_argument("--provider", choices=["google", "mymemory"], default="google")
    parser.add_argument("--refresh", action="store_true", help="Regenerate existing cues instead of preserving them.")
    parser.add_argument("--limit", type=int, help="Translate only the first N missing cues; keep later rows pending.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_rows = spanish_deck.parse_source_deck(args.source)
    output = Path(args.output)
    cache_path = Path(args.cache) if args.cache else (GOOGLE_CACHE_PATH if args.provider == "google" else CACHE_PATH)
    existing = load_existing(output)
    cache = load_cache(cache_path)
    rows = build_rows(
        source_rows,
        existing,
        cache,
        args.limit,
        output,
        cache_path,
        provider=args.provider,
        refresh=args.refresh,
    )
    write_rows(output, rows)
    save_cache(cache_path, cache)
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    print(json.dumps({"rows": len(rows), "status": counts, "output": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
