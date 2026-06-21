import argparse
import base64
import csv
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import english_mastery


MODEL_NAME = "English Mastery"
IMPORT_PATH = Path("generated/english_mastery/english_mastery.tsv")
OLD_DECKS = [
    "English Grammar Maintenance",
    "English Natural Phrases",
]
FIELDS = english_mastery.FIELDS

CSS = """
.card {
  background: #1a1a1a;
  color: #e8e6e0;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  font-size: 22px;
  line-height: 1.45;
  text-align: center;
}
.wrap {
  max-width: 760px;
  margin: 0 auto;
  padding: 18px 14px;
}
.meta {
  color: #a8a09a;
  font-size: 13px;
  letter-spacing: 0;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.front {
  font-size: 25px;
  font-weight: 650;
  margin: 14px 0;
}
.front-instruction,
.front-label,
.front-cue {
  color: #a8a09a;
  font-size: 15px;
  font-weight: 550;
  line-height: 1.35;
}
.front-cue {
  display: inline-block;
  max-width: 92%;
}
.front-label {
  color: #d4a564;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.02em;
}
.answer {
  color: #5ec9a0;
  font-size: 30px;
  font-weight: 700;
  margin: 14px 0;
}
.section {
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  margin-top: 14px;
  padding-top: 12px;
}
.label {
  color: #d4a564;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 5px;
}
.detail {
  font-size: 19px;
}
.examples {
  color: #c8c0b8;
  font-size: 18px;
}
.type-note {
  color: #a8a09a;
  font-size: 14px;
  margin-top: 8px;
}
.source {
  color: #888078;
  font-size: 12px;
  margin-top: 14px;
}
.self-grade {
  color: #8f8880;
  font-size: 12px;
  line-height: 1.35;
  margin-top: 14px;
}
input {
  max-width: 92%;
  color: #e8e6e0;
  background: #2a2a2a;
}
"""

FRONT_TEMPLATE = """
<div class="wrap">
  <div class="meta">{{Level}} · {{CardType}}</div>
  <div class="front">{{Front}}</div>
  {{#TypeAnswer}}
    <div class="type-note">Type your answer, then compare carefully.</div>
    {{type:TypeAnswer}}
  {{/TypeAnswer}}
  {{^TypeAnswer}}
    <div class="type-note">Recall the answer and rule before showing the back.</div>
  {{/TypeAnswer}}
</div>
"""

BACK_TEMPLATE = """
<div class="wrap">
  {{FrontSide}}
  <div class="section">
    <div class="label">Answer</div>
    <div class="answer">{{Answer}}</div>
  </div>
  <div class="section">
    <div class="label">Why / Meaning</div>
    <div class="detail">{{Back}}</div>
  </div>
  {{#Formula}}
  <div class="section">
    <div class="label">Formula</div>
    <div class="detail">{{Formula}}</div>
  </div>
  {{/Formula}}
  {{#Examples}}
  <div class="section">
    <div class="label">Examples</div>
    <div class="examples">{{Examples}}</div>
  </div>
  {{/Examples}}
  {{#Source}}
  <div class="source">{{Source}}<br>{{Attribution}}</div>
  {{/Source}}
  {{#SelfGrade}}
  <div class="self-grade">{{SelfGrade}}</div>
  {{/SelfGrade}}
</div>
"""


def invoke(action, **params):
    payload = json.dumps({"action": action, "params": params, "version": 6}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:8765", payload)
    for attempt in range(3):
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("error"):
            return result["result"]
        if result["error"] != "collection is not available" or attempt == 2:
            raise RuntimeError(result["error"])
        time.sleep(2)
    raise RuntimeError("collection is not available")


def ensure_model():
    model_names = invoke("modelNames")
    if MODEL_NAME not in model_names:
        invoke(
            "createModel",
            modelName=MODEL_NAME,
            inOrderFields=FIELDS,
            css=CSS,
            cardTemplates=[{"Name": "English Mastery Card", "Front": FRONT_TEMPLATE, "Back": BACK_TEMPLATE}],
        )
        return
    existing_fields = invoke("modelFieldNames", modelName=MODEL_NAME)
    for field in FIELDS:
        if field not in existing_fields:
            invoke("modelFieldAdd", modelName=MODEL_NAME, fieldName=field)
            existing_fields.append(field)
    invoke("updateModelTemplates", model={"name": MODEL_NAME, "templates": {"English Mastery Card": {"Front": FRONT_TEMPLATE, "Back": BACK_TEMPLATE}}})
    invoke("updateModelStyling", model={"name": MODEL_NAME, "css": CSS})


def load_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    header = rows[2]
    return [dict(zip(header, row)) for row in rows[3:]]


def load_existing_notes():
    note_ids = invoke("findNotes", query=f'note:"{MODEL_NAME}"')
    if not note_ids:
        return {}
    existing = {}
    for note in invoke("notesInfo", notes=note_ids):
        source_id = note.get("fields", {}).get("SourceID", {}).get("value", "")
        if source_id:
            existing[source_id] = note["noteId"]
    return existing


def store_audio(row):
    audio_url = row.get("AudioURL", "")
    audio = row.get("Audio", "")
    if not audio_url or not audio.startswith("[sound:"):
        return
    filename = audio.removeprefix("[sound:").removesuffix("]")
    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", "15", "--retry", "1", "-A", "Mozilla/5.0", audio_url],
        check=True,
        capture_output=True,
        timeout=20,
    )
    invoke("storeMediaFile", filename=filename, data=base64.b64encode(result.stdout).decode("ascii"))


def sync_media(rows):
    audio_rows = [row for row in rows if row.get("AudioURL")]
    existing_media = set(invoke("getMediaFilesNames", pattern="tatoeba_eng_*.mp3"))
    stored = 0
    skipped = 0
    for index, row in enumerate(audio_rows, start=1):
        filename = row.get("Audio", "").removeprefix("[sound:").removesuffix("]")
        if filename in existing_media:
            skipped += 1
            continue
        store_audio(row)
        stored += 1
        if index % 25 == 0:
            print(f"Processed {index}/{len(audio_rows)} audio rows...", flush=True)
    return {"audio_rows": len(audio_rows), "stored": stored, "skipped_existing": skipped}


def sync_rows(rows, store_media=True):
    existing_notes = load_existing_notes()
    created = 0
    updated = 0
    moved = 0
    for deck_name in sorted({row["DeckPath"] for row in rows}):
        invoke("createDeck", deck=deck_name)
    for index, row in enumerate(rows, start=1):
        if store_media:
            store_audio(row)
        fields = {field: row.get(field, "") for field in FIELDS}
        note_id = existing_notes.get(row["SourceID"])
        if note_id:
            invoke("updateNoteFields", note={"id": note_id, "fields": fields})
            card_ids = invoke("findCards", query=f"nid:{note_id}")
            if card_ids:
                invoke("changeDeck", cards=card_ids, deck=row["DeckPath"])
                moved += len(card_ids)
            updated += 1
        else:
            invoke(
                "addNote",
                note={
                    "deckName": row["DeckPath"],
                    "modelName": MODEL_NAME,
                    "fields": fields,
                    "options": {"allowDuplicate": False, "duplicateScope": "deck"},
                    "tags": row["Tags"].split(),
                },
            )
            created += 1
        if index % 100 == 0:
            print(f"Synced {index}/{len(rows)} rows...", flush=True)
    return {"created": created, "updated": updated, "moved_cards": moved}


def prune_stale_notes(valid_source_ids):
    note_ids = invoke("findNotes", query=f'note:"{MODEL_NAME}"')
    stale_note_ids = []
    for note in invoke("notesInfo", notes=note_ids):
        source_id = note.get("fields", {}).get("SourceID", {}).get("value", "")
        if source_id and source_id not in valid_source_ids:
            stale_note_ids.append(note["noteId"])
    if stale_note_ids:
        invoke("deleteNotes", notes=stale_note_ids)
    return len(stale_note_ids)


def delete_old_decks():
    deck_names = set(invoke("deckNames"))
    existing = [deck for deck in OLD_DECKS if deck in deck_names]
    if existing:
        invoke("deleteDecks", decks=existing, cardsToo=True)
    return existing


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Sync English Mastery deck to Anki.")
    parser.add_argument("--path", default=str(IMPORT_PATH))
    parser.add_argument("--prune-stale", action="store_true")
    parser.add_argument("--delete-old-english-decks", action="store_true")
    parser.add_argument("--skip-media", action="store_true")
    parser.add_argument("--media-only", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    invoke("version")
    ensure_model()
    rows = load_rows(args.path)
    if args.media_only:
        print(json.dumps({"media": sync_media(rows)}, ensure_ascii=False, indent=2))
        return 0
    result = sync_rows(rows, store_media=not args.skip_media)
    pruned = prune_stale_notes({row["SourceID"] for row in rows}) if args.prune_stale else 0
    deleted = delete_old_decks() if args.delete_old_english_decks else []
    print(json.dumps({"synced": result, "pruned_stale_notes": pruned, "deleted_decks": deleted, "rows": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
