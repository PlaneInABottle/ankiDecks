"""Detect notes whose content was manually edited in Anki and tag them locked.

The sync scripts never overwrite notes tagged ``locked`` (see anki_protect).
Run this while Anki is open to auto-protect the cards you edited by hand.

Usage:
    python3 protect_manual_edits.py            # report only
    python3 protect_manual_edits.py --apply    # also tag the edits as locked
    python3 protect_manual_edits.py --apply --force   # re-tag everything
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import anki_protect
import sync_english_mastery_to_anki as mastery
import sync_spanish_core_to_anki as core
import sync_4000_production_to_anki as prod


SPANISH_CONTENT_FIELDS = [
    "Spanish",
    "PronunciationHint",
    "English",
    "SpanishMeaning",
    "SpanishExample",
    "EnglishMeaning",
    "EnglishExample",
    "Notes",
    "SpanishMeaningEnglish",
    "SpanishExampleEnglish",
    "SpanishArticle",
    "SpanishGender",
    "SpanishNumber",
    "SpanishPartOfSpeech",
    "SpanishForms",
]

# Genuinely hand-authored content fields. Generator-produced metadata
# (Level, Topic, CardType, PromptMode, Source, Attribution) is excluded so that
# drift between TSV regenerations does not cause false-positive locking.
MASTERY_CONTENT_FIELDS = ["Front", "Answer", "Back", "Formula", "Examples", "TypeAnswer", "SelfGrade"]
CORE_CONTENT_FIELDS = ["Front", "Answer", "Back", "Formula", "Examples", "TypeAnswer"]


def invoke(action: str, **params):
    payload = json.dumps({"action": action, "params": params, "version": 6}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:8765", payload, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("error"):
            return result["result"]
        if result["error"] != "collection is not available" or attempt == 2:
            raise RuntimeError(result["error"])
        time.sleep(2)
    raise RuntimeError("collection is not available")


def compare_model(script_module, path, content_fields):
    rows = script_module.load_rows(path)
    row_by_id = {row["SourceID"]: row for row in rows}
    note_ids = invoke("findNotes", query=f'note:"{script_module.MODEL_NAME}"')
    if not note_ids:
        return []
    notes = invoke("notesInfo", notes=note_ids)
    tagged = []
    for note in notes:
        source_id = note.get("fields", {}).get("SourceID", {}).get("value", "")
        row = row_by_id.get(source_id)
        if not row:
            continue
        edited = anki_protect.detect_content_edits(note.get("fields", {}), row, content_fields)
        if edited:
            tagged.append((note["noteId"], source_id, edited))
    return tagged


def compare_spanish_content(review_path: Path, source_rows):
    review_rows = prod.load_spanish_review_rows(review_path, source_rows)
    notes = prod.get_notes(f'note:"{prod.SPANISH_MODEL}"')
    tagged = []
    for note in notes:
        key = prod.source_id_from_spanish_note(note["fields"])
        row = review_rows.get(key)
        if not row:
            continue
        source_fields = {
            "Spanish": row.get("Spanish", ""),
            "PronunciationHint": row.get("Pronunciation Hint", ""),
            "English": row.get("English", ""),
            "SpanishMeaning": row.get("Spanish Meaning", ""),
            "SpanishExample": row.get("Spanish Example", ""),
            "EnglishMeaning": row.get("English Meaning", ""),
            "EnglishExample": row.get("English Example", ""),
            "Notes": row.get("Notes", ""),
            "SpanishMeaningEnglish": row.get("Spanish Meaning (English)", ""),
            "SpanishExampleEnglish": row.get("Spanish Example (English)", ""),
            "SpanishArticle": row.get("Spanish Article", ""),
            "SpanishGender": row.get("Spanish Gender", ""),
            "SpanishNumber": row.get("Spanish Number", ""),
            "SpanishPartOfSpeech": row.get("Spanish Part of Speech", ""),
            "SpanishForms": row.get("Spanish Forms", ""),
        }
        edited = anki_protect.detect_content_edits(note.get("fields", {}), source_fields, SPANISH_CONTENT_FIELDS)
        if edited:
            tagged.append((note["noteId"], key, edited))
    return tagged


def apply_tags(entries):
    if not entries:
        return 0
    note_ids = [entry[0] for entry in entries]
    for start in range(0, len(note_ids), 100):
        invoke("addTags", notes=note_ids[start:start + 100], tags=anki_protect.LOCKED_TAG)
    return len(note_ids)


def parse_args():
    parser = argparse.ArgumentParser(description="Detect and lock manually edited Anki notes.")
    parser.add_argument("--apply", action="store_true", help="Tag detected edits as locked (default: report only).")
    return parser.parse_args()


def main():
    args = parse_args()
    invoke("version")

    findings = []

    tagged_mastery = compare_model(mastery, mastery.IMPORT_PATH, MASTERY_CONTENT_FIELDS)
    findings.append((mastery.MODEL_NAME, tagged_mastery))

    tagged_core = compare_model(core, core.IMPORT_PATH, CORE_CONTENT_FIELDS)
    findings.append((core.MODEL_NAME, tagged_core))

    source_rows = prod.spanish_deck.parse_source_deck("4000 Essential English Words.txt")
    tagged_spanish = compare_spanish_content(prod.SPANISH_REVIEW_PATH, source_rows)
    findings.append((prod.SPANISH_MODEL, tagged_spanish))

    total = 0
    for model_name, entries in findings:
        print(f"\n=== {model_name}: {len(entries)} manually edited note(s) ===")
        for _, source_id, edited in entries:
            print(f"  - {source_id}: changed {', '.join(edited)}")
        total += len(entries)

    print(f"\nTotal manually edited notes detected: {total}")

    if args.apply and total:
        all_entries = [e for _, entries in findings for e in entries]
        count = apply_tags(all_entries)
        print(f"Tagged {count} note(s) with '{anki_protect.LOCKED_TAG}'. Sync scripts will skip them.")
    elif total:
        print("Run with --apply to tag these notes as locked.")


if __name__ == "__main__":
    main()
