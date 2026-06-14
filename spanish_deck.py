"""Generate a safe Spanish duplicate deck workflow for the 4000 list."""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


STATUS_REVIEWED = "reviewed"
STATUS_NEEDS_TRANSLATION = "needs_translation"


def normalize_word(value: str) -> str:
    """Normalize a vocab word for stable glossary matching."""
    return " ".join((value or "").strip().lower().split())


def normalize_context(value: str) -> str:
    """Normalize source context for duplicate word disambiguation."""
    return " ".join((value or "").strip().lower().split())


def context_key(english: str, english_meaning: str = "", english_example: str = "") -> str:
    """Build a glossary key that keeps duplicate English words with different senses separate."""
    return "\x1f".join(
        [
            "context",
            normalize_word(english),
            normalize_context(english_meaning),
            normalize_context(english_example),
        ]
    )


def normalize_header(value: str) -> str:
    """Normalize a header-like value for tolerant matching."""
    text = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _canonicalize_column_name(name: str) -> str:
    """Return canonical source-column names recognized by the parser."""
    key = normalize_header(name)
    aliases = {
        "guid": "guid",
        "notetype": "notetype",
        "note_type": "notetype",
        "deck": "deck",
        "card_number": "card_number",
        "card_number_1": "card_number",
        "image": "image",
        "word": "english_word",
        "english": "english_word",
        "english_word": "english_word",
        "front": "english_word",
        "phonetic": "phonetic",
        "sound": "sound",
        "ipa": "ipa",
        "meaning": "english_meaning",
        "english_meaning": "english_meaning",
        "example": "english_example",
        "english_example": "english_example",
    }
    return aliases.get(key, "")


def _slugify(value: str) -> str:
    """Build a stable lowercase slug for tags."""
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return slug.strip("_")


def _parse_header_directive(line: str, mapping: Dict[str, int]) -> None:
    """Parse header directives such as '#deck column:3' into column indexes."""
    text = line.strip()
    if not text.startswith("#"):
        return
    match = re.search(r"column:\s*(\d+)", text, flags=re.IGNORECASE)
    if not match:
        return
    index = int(match.group(1)) - 1
    name = text[1: match.start()].strip()
    canonical = _canonicalize_column_name(name)
    if canonical:
        mapping[canonical] = index


def _safe_field(row: Sequence[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return (row[index] or "").strip()


def _parse_known_4000_row(raw_row: Sequence[str]) -> Dict[str, str] | None:
    """Parse known 4000 EEW row layouts without trusting one shared word column."""
    notetype = _safe_field(raw_row, 1)
    if notetype == "4000 EEW":
        return {
            "guid": _safe_field(raw_row, 0),
            "notetype": notetype,
            "deck": _safe_field(raw_row, 2),
            "card_number": "",
            "image": _safe_field(raw_row, 4),
            "english_word": _safe_field(raw_row, 3),
            "phonetic": "",
            "sound": _safe_field(raw_row, 5),
            "ipa": _safe_field(raw_row, 10),
            "english_meaning": _safe_field(raw_row, 8),
            "english_example": _safe_field(raw_row, 9),
        }
    if notetype == "4000 EEW Extra":
        return {
            "guid": _safe_field(raw_row, 0),
            "notetype": notetype,
            "deck": _safe_field(raw_row, 2),
            "card_number": _safe_field(raw_row, 3),
            "image": _safe_field(raw_row, 4),
            "english_word": _safe_field(raw_row, 5),
            "phonetic": _safe_field(raw_row, 6),
            "sound": _safe_field(raw_row, 7),
            "ipa": _safe_field(raw_row, 8),
            "english_meaning": "",
            "english_example": "",
        }
    return None


def parse_source_deck(source_path: str) -> List[Dict[str, str]]:
    """Parse the source 4000 Essential English Words-style TSV deck."""
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(source_path)

    defaults = {
        "guid": 0,
        "notetype": 1,
        "deck": 2,
        "card_number": 3,
        "image": 4,
        "english_word": 5,
        "phonetic": 6,
        "sound": 7,
        "ipa": 8,
    }
    mapping: Dict[str, int] = {}
    rows: List[Dict[str, str]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for raw_row in reader:
            if not raw_row:
                continue
            if len(raw_row) == 1 and raw_row[0].lstrip().startswith("#"):
                _parse_header_directive(raw_row[0], mapping)
                continue
            if not any(field.strip() for field in raw_row):
                continue

            row = _parse_known_4000_row(raw_row)
            if row is None:
                row = {
                    "guid": _safe_field(raw_row, mapping.get("guid", defaults["guid"])),
                    "notetype": _safe_field(raw_row, mapping.get("notetype", defaults["notetype"])),
                    "deck": _safe_field(raw_row, mapping.get("deck", defaults["deck"])),
                    "card_number": _safe_field(raw_row, mapping.get("card_number", defaults["card_number"])),
                    "image": _safe_field(raw_row, mapping.get("image", defaults["image"])),
                    "english_word": _safe_field(raw_row, mapping.get("english_word", defaults["english_word"])),
                    "phonetic": _safe_field(raw_row, mapping.get("phonetic", defaults["phonetic"])),
                    "sound": _safe_field(raw_row, mapping.get("sound", defaults["sound"])),
                    "ipa": _safe_field(raw_row, mapping.get("ipa", defaults["ipa"])),
                    "english_meaning": _safe_field(raw_row, mapping.get("english_meaning", -1)),
                    "english_example": _safe_field(raw_row, mapping.get("english_example", -1)),
                }
            if not row["english_word"]:
                continue
            rows.append(row)
    return rows


def _pick_header_key(headers: Dict[str, str], *candidates: str) -> str:
    for candidate in candidates:
        norm = normalize_header(candidate)
        if norm in headers:
            return headers[norm]
        for key in headers:
            if key == norm:
                return headers[key]
    return ""


def load_glossary(glossary_path: str | None) -> Dict[str, Dict[str, str]]:
    """Load reviewed Spanish glossary entries.

    Modern glossaries can include original English meaning/example columns, allowing
    duplicate words with different senses to use different Spanish translations.
    Older word-only glossaries are still accepted as a fallback.
    """
    if not glossary_path:
        return {}
    path = Path(glossary_path)
    if not path.exists():
        raise FileNotFoundError(glossary_path)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters="\t,").delimiter
        except csv.Error:
            delimiter = "\t" if "\t" in sample else ","

        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            return {}

        headers = {normalize_header(name): name for name in reader.fieldnames}
        english_key = _pick_header_key(headers, "english", "english_word", "word")
        english_meaning_key = _pick_header_key(headers, "english_meaning", "meaning")
        english_example_key = _pick_header_key(headers, "english_example")
        spanish_key = _pick_header_key(headers, "spanish")
        spanish_meaning_key = _pick_header_key(headers, "spanish_meaning")
        example_key = _pick_header_key(headers, "spanish_example", "example")
        notes_key = _pick_header_key(headers, "notes")

        if not english_key or not spanish_key:
            return {}

        entries: List[Tuple[str, str, str, Dict[str, str]]] = []
        for row in reader:
            english = (row.get(english_key) or "").strip()
            if not english:
                continue
            entry = {
                "spanish": (row.get(spanish_key) or "").strip(),
                "spanish_meaning": (row.get(spanish_meaning_key) or "").strip() if spanish_meaning_key else "",
                "spanish_example": (row.get(example_key) or "").strip() if example_key else "",
                "notes": (row.get(notes_key) or "").strip() if notes_key else "",
            }
            english_meaning = (row.get(english_meaning_key) or "").strip() if english_meaning_key else ""
            english_example = (row.get(english_example_key) or "").strip() if english_example_key else ""
            entries.append((english, english_meaning, english_example, entry))

        glossary: Dict[str, Dict[str, str]] = {}
        word_counts = Counter(normalize_word(english) for english, _, _, _ in entries)
        has_context_columns = bool(english_meaning_key or english_example_key)

        for english, english_meaning, english_example, entry in entries:
            word_key = normalize_word(english)
            if has_context_columns:
                glossary[context_key(english, english_meaning, english_example)] = entry
                if word_counts[word_key] == 1:
                    glossary[word_key] = entry
            else:
                glossary[word_key] = entry
    return glossary


def find_glossary_entry(
    glossary: Dict[str, Dict[str, str]],
    source_row: Dict[str, str],
) -> Dict[str, str] | None:
    """Find a reviewed glossary row, preferring exact source context over word-only fallback."""
    english = source_row.get("english_word", "")
    exact_key = context_key(
        english,
        source_row.get("english_meaning", ""),
        source_row.get("english_example", ""),
    )
    return glossary.get(exact_key) or glossary.get(normalize_word(english))


def build_spanish_rows(
    source_rows: Sequence[Dict[str, str]],
    glossary: Dict[str, Dict[str, str]],
    limit: int | None = None,
) -> List[Dict[str, str]]:
    """Build merged English->Spanish rows with reviewed/pending status."""
    selected_rows = list(source_rows)
    if limit is not None and limit >= 0:
        selected_rows = selected_rows[:limit]

    output_rows: List[Dict[str, str]] = []
    for source_row in selected_rows:
        english = source_row.get("english_word", "").strip()
        glossary_row = find_glossary_entry(glossary, source_row)
        is_reviewed = bool(glossary_row)

        spanish = glossary_row.get("spanish", "").strip() if glossary_row else ""
        status = STATUS_REVIEWED if is_reviewed else STATUS_NEEDS_TRANSLATION
        source_deck = source_row.get("deck", "").strip()
        source_slug = _slugify(source_deck) or "source_unknown"
        tags = ["spanish", "from_4000_english", source_slug, status]

        output_rows.append(
            {
                "english": english,
                "spanish": spanish,
                "image": source_row.get("image", "").strip(),
                "english_meaning": source_row.get("english_meaning", "").strip(),
                "english_example": source_row.get("english_example", "").strip(),
                "spanish_meaning": glossary_row.get("spanish_meaning", "").strip() if glossary_row else "",
                "spanish_example": glossary_row.get("spanish_example", "").strip() if glossary_row else "",
                "notes": glossary_row.get("notes", "").strip() if glossary_row else "",
                "status": status,
                "source_deck": source_deck,
                "source_card": source_row.get("card_number", "").strip(),
                "tags": " ".join(tags),
            }
        )
    return output_rows


def _back_field_for_basic(record: Dict[str, str]) -> str:
    if record["status"] == STATUS_REVIEWED:
        parts = [f"English: {record['english']}"]
        if record["spanish_meaning"]:
            parts.append(f"Meaning: {record['spanish_meaning']}")
        if record["spanish_example"]:
            parts.append(f"Example: {record['spanish_example']}")
        source_parts = [
            value
            for value in (record.get("english_meaning", ""), record.get("english_example", ""))
            if value
        ]
        if source_parts:
            parts.append("English source:\n" + "\n".join(source_parts))
        if record["notes"]:
            parts.append(f"Notes: {record['notes']}")
        return "\n".join(parts)
    return "TODO: Spanish translation needed"


def _write_tsv(path: Path, header: List[str], rows: List[Sequence[str]], include_import_headers: bool = False) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        if include_import_headers:
            handle.write("#separator:tab\n")
            handle.write("#html:true\n")
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_spanish_files(
    source_rows: Sequence[Dict[str, str]],
    glossary: Dict[str, Dict[str, str]],
    output_dir: str = "generated/spanish",
    limit: int | None = None,
) -> Tuple[str, str]:
    """
    Write review and basic TSV files and return file paths.

    Returns:
        (review_path, basic_path)
    """
    merged = build_spanish_rows(source_rows, glossary, limit=limit)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    review_rows = [
        [
            row["english"],
            row["english_meaning"],
            row["english_example"],
            row["spanish"],
            row["spanish_meaning"],
            row["spanish_example"],
            row["notes"],
            row["status"],
            row["source_deck"],
            row["source_card"],
            row["tags"],
        ]
        for row in merged
    ]
    basic_rows = [
        ["\n".join(value for value in (row["image"], row["spanish"] or row["english"]) if value), _back_field_for_basic(row), row["tags"]]
        for row in merged
    ]

    review_path = output_path / "english_spanish_review.tsv"
    basic_path = output_path / "english_spanish_basic.tsv"

    _write_tsv(
        review_path,
        [
            "English",
            "English Meaning",
            "English Example",
            "Spanish",
            "Spanish Meaning",
            "Spanish Example",
            "Notes",
            "Status",
            "Source Deck",
            "Source Card",
            "Tags",
        ],
        review_rows,
    )
    _write_tsv(
        basic_path,
        ["Front", "Back", "Tags"],
        basic_rows,
        include_import_headers=True,
    )

    return str(review_path), str(basic_path)


def summarize_rows(rows: Sequence[Dict[str, str]]) -> Dict[str, int]:
    counts = Counter(row["status"] for row in rows)
    total = len(rows)
    pending = counts[STATUS_NEEDS_TRANSLATION]
    return {
        "total_cards": total,
        "reviewed_count": total - pending,
        "pending_count": pending,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Spanish duplicate deck files from 4000 Essential English Words."
    )
    parser.add_argument("--source", default="4000 Essential English Words.txt", help="Source TSV deck path")
    parser.add_argument("--glossary", help="Optional reviewed glossary CSV/TSV path")
    parser.add_argument("--output-dir", default="generated/spanish", help="Output directory")
    parser.add_argument("--limit", type=int, help="Process at most N cards")
    parser.add_argument("--summary", action="store_true", help="Print counts only; no files written")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source_rows = parse_source_deck(args.source)
    glossary = load_glossary(args.glossary)

    if args.summary:
        rows = build_spanish_rows(source_rows, glossary, limit=args.limit)
        summary = summarize_rows(rows)
        print(f"Total source cards: {summary['total_cards']}")
        print(f"Reviewed cards: {summary['reviewed_count']}")
        print(f"Pending cards: {summary['pending_count']}")
        return 0

    review_path, basic_path = write_spanish_files(
        source_rows,
        glossary,
        output_dir=args.output_dir,
        limit=args.limit,
    )

    print(f"Wrote review file: {os.path.abspath(review_path)}")
    print(f"Wrote basic import file: {os.path.abspath(basic_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
