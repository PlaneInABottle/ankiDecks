"""Detect notes whose content was manually edited in Anki and tag them locked.

The sync scripts never overwrite notes tagged ``locked`` (see anki_protect).
Run this while Anki is open to auto-protect the cards you edited by hand.

Usage:
    python3 protect_manual_edits.py            # report only
    python3 protect_manual_edits.py --apply    # also tag the edits as locked
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


MASTERY_CONTENT_FIELDS = anki_protect.content_fields(mastery.FIELDS)
CORE_CONTENT_FIELDS = anki_protect.content_fields(core.FIELDS)


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


def compare_model(script_module, path, content_fields, legacy_namespace):
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
        fields = note.get("fields", {})
        if anki_protect.note_has_untracked_edits(
            fields,
            row,
            content_fields,
            legacy_fingerprints=anki_protect.legacy_fingerprints(legacy_namespace, source_id),
        ):
            edited = anki_protect.detect_content_edits(fields, row, content_fields)
            if not edited:
                edited = ["tracked content fingerprint"]
            tagged.append(
                (note["noteId"], source_id, edited, anki_protect.note_is_locked(note.get("tags", [])))
            )
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
        source_fields = prod.spanish_content_fields(row)
        fields = note.get("fields", {})
        if anki_protect.note_has_untracked_edits(
            fields,
            source_fields,
            prod.SPANISH_CONTENT_FIELDS,
            legacy_fingerprints=anki_protect.legacy_fingerprints(
                prod.SPANISH_CONTENT_LEGACY_NAMESPACE,
                key,
            ),
        ):
            edited = anki_protect.detect_content_edits(fields, source_fields, prod.SPANISH_CONTENT_FIELDS)
            if not edited:
                edited = ["tracked content fingerprint"]
            tagged.append(
                (note["noteId"], key, edited, anki_protect.note_is_locked(note.get("tags", [])))
            )
    return tagged


def apply_tags(entries):
    note_ids = [entry[0] for entry in entries if not entry[3]]
    if not note_ids:
        return 0
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

    tagged_mastery = compare_model(
        mastery,
        mastery.IMPORT_PATH,
        MASTERY_CONTENT_FIELDS,
        mastery.LEGACY_FINGERPRINT_NAMESPACE,
    )
    findings.append((mastery.MODEL_NAME, tagged_mastery))

    tagged_core = compare_model(
        core,
        core.IMPORT_PATH,
        CORE_CONTENT_FIELDS,
        core.LEGACY_FINGERPRINT_NAMESPACE,
    )
    findings.append((core.MODEL_NAME, tagged_core))

    source_rows = prod.spanish_deck.parse_source_deck("4000 Essential English Words.txt")
    tagged_spanish = compare_spanish_content(prod.SPANISH_REVIEW_PATH, source_rows)
    findings.append((prod.SPANISH_MODEL, tagged_spanish))

    total = 0
    unprotected = 0
    for model_name, entries in findings:
        print(f"\n=== {model_name}: {len(entries)} differing note(s) ===")
        for _, source_id, edited, already_locked in entries:
            status = " [already locked]" if already_locked else " [needs protection]"
            print(f"  - {source_id}: changed {', '.join(edited)}{status}")
            unprotected += 0 if already_locked else 1
        total += len(entries)

    print(f"\nTotal differing notes detected: {total}; unprotected: {unprotected}")

    if args.apply and unprotected:
        all_entries = [e for _, entries in findings for e in entries]
        count = apply_tags(all_entries)
        print(f"Tagged {count} note(s) with '{anki_protect.LOCKED_TAG}'. Sync scripts will skip them.")
    elif unprotected:
        print("Run with --apply to tag these notes as locked.")
    elif total:
        print("All differing notes are already protected.")


if __name__ == "__main__":
    main()
