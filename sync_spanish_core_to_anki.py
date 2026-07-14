import argparse
import base64
import csv
import json
import subprocess
import time
import urllib.request
from pathlib import Path


import anki_protect


MODEL_NAME = "Spanish Core Learning"
LEGACY_FINGERPRINT_NAMESPACE = "spanish_core"
IMPORT_PATH = Path("generated/spanish_core/spanish_core_learning.tsv")
FIELDS = [
    "SourceID",
    "DeckPath",
    "Level",
    "Topic",
    "CardType",
    "PromptMode",
    "Front",
    "Answer",
    "TypeAnswer",
    "Back",
    "Formula",
    "Examples",
    "Audio",
    "AudioURL",
    "AudioContributor",
    "AudioLicense",
    "AudioID",
    "Source",
    "Attribution",
    "Tags",
]
MODEL_FIELDS = [*FIELDS, anki_protect.FINGERPRINT_FIELD]
CONTENT_FIELDS = anki_protect.content_fields(FIELDS)

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
  max-width: 720px;
  margin: 0 auto;
  padding: 18px 14px;
}
.front {
  font-size: 26px;
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
.topic-label {
  color: #d4a564;
  font-size: 18px;
  font-weight: 600;
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
.wrong-spanish {
  color: #e85d56;
  text-decoration: line-through;
}
.source {
  color: #888078;
  font-size: 12px;
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
  <div class="front">{{Front}}</div>
  {{#TypeAnswer}}
    {{type:TypeAnswer}}
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
  <div class="section">
    <div class="label">Support note</div>
    <div class="detail">{{Back}}</div>
  </div>
  {{#Source}}
  <div class="source">{{Source}}<br>{{Attribution}}</div>
  {{/Source}}
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


def ensure_model(update_existing=False):
    model_names = invoke("modelNames")
    if MODEL_NAME not in model_names:
        invoke(
            "createModel",
            modelName=MODEL_NAME,
            inOrderFields=MODEL_FIELDS,
            css=CSS,
            cardTemplates=[
                {
                    "Name": "Spanish Core Card",
                    "Front": FRONT_TEMPLATE,
                    "Back": BACK_TEMPLATE,
                }
            ],
        )
        return
    existing_fields = invoke("modelFieldNames", modelName=MODEL_NAME)
    for field in MODEL_FIELDS:
        if field not in existing_fields:
            invoke("modelFieldAdd", modelName=MODEL_NAME, fieldName=field)
            existing_fields.append(field)
    if update_existing:
        invoke("updateModelTemplates", model={"name": MODEL_NAME, "templates": {"Spanish Core Card": {"Front": FRONT_TEMPLATE, "Back": BACK_TEMPLATE}}})
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
        fields = note.get("fields", {})
        source_id = fields.get("SourceID", {}).get("value", "")
        if source_id:
            existing[source_id] = note
    return existing


def strip_audio(row):
    audio = row.get("Audio", "")
    if audio:
        row["Front"] = row.get("Front", "").replace(f"{audio}<br><br>", "").replace(audio, "")
        row["Audio"] = ""


def store_audio(row):
    audio_url = row.get("AudioURL", "")
    audio = row.get("Audio", "")
    if not audio_url or not audio.startswith("[sound:"):
        return
    filename = audio.removeprefix("[sound:").removesuffix("]")
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "15", "--retry", "1", "-A", "Mozilla/5.0", audio_url],
            check=True,
            capture_output=True,
            timeout=20,
        )
        audio_data = result.stdout
        invoke("storeMediaFile", filename=filename, data=base64.b64encode(audio_data).decode("ascii"))
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Audio skipped for {row.get('SourceID')}: {error}")
        strip_audio(row)


def sync_media(rows):
    audio_rows = [row for row in rows if row.get("AudioURL")]
    existing_media = set(invoke("getMediaFilesNames", pattern="tatoeba_spa_*.mp3"))
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


def sync_rows(rows, store_media=True, force=False):
    created = 0
    updated = 0
    moved = 0
    skipped_locked = 0
    auto_locked = 0
    existing_notes = load_existing_notes()
    for deck_name in sorted({row["DeckPath"] for row in rows}):
        invoke("createDeck", deck=deck_name)
    for index, row in enumerate(rows, start=1):
        deck_name = row["DeckPath"]
        existing = existing_notes.get(row["SourceID"])
        source_fields = {field: row.get(field, "") for field in FIELDS}
        preserve_content = False
        if existing:
            note_id = existing["noteId"]
            tags = existing.get("tags", [])
            if not force and anki_protect.note_is_locked(tags):
                skipped_locked += 1
                preserve_content = True
            elif not force and anki_protect.note_has_untracked_edits(
                existing.get("fields", {}),
                source_fields,
                CONTENT_FIELDS,
                legacy_fingerprints=anki_protect.legacy_fingerprints(
                    LEGACY_FINGERPRINT_NAMESPACE, row["SourceID"]
                ),
            ):
                invoke("addTags", notes=[note_id], tags=anki_protect.LOCKED_TAG)
                auto_locked += 1
                preserve_content = True
        if store_media and not preserve_content:
            store_audio(row)
            source_fields = {field: row.get(field, "") for field in FIELDS}
        fields = anki_protect.source_fields_with_fingerprint(source_fields, CONTENT_FIELDS)
        if existing:
            if not preserve_content:
                invoke("updateNoteFields", note={"id": note_id, "fields": fields})
                updated += 1
            card_ids = invoke("findCards", query=f"nid:{note_id}")
            if card_ids:
                invoke("changeDeck", cards=card_ids, deck=deck_name)
                moved += len(card_ids)
        else:
            invoke(
                "addNote",
                note={
                    "deckName": deck_name,
                    "modelName": MODEL_NAME,
                    "fields": fields,
                    "options": {"allowDuplicate": False, "duplicateScope": "deck"},
                    "tags": row["Tags"].split(),
                },
            )
            created += 1
        if index % 100 == 0:
            print(f"Synced {index}/{len(rows)} rows...")
    return {
        "created": created,
        "updated": updated,
        "moved_cards": moved,
        "skipped_locked": skipped_locked,
        "auto_locked": auto_locked,
    }


def prune_stale_notes(valid_source_ids):
    note_ids = invoke("findNotes", query=f'note:"{MODEL_NAME}"')
    if not note_ids:
        return 0
    stale_note_ids = []
    for note in invoke("notesInfo", notes=note_ids):
        if anki_protect.note_is_locked(note.get("tags", [])):
            continue
        fields = note.get("fields", {})
        source_id = fields.get("SourceID", {}).get("value", "")
        if not source_id or source_id in valid_source_ids:
            continue
        stored = fields.get(anki_protect.FINGERPRINT_FIELD, {}).get("value", "")
        if not stored:
            continue
        if anki_protect.content_fingerprint(fields, CONTENT_FIELDS) != stored:
            invoke("addTags", notes=[note["noteId"]], tags=anki_protect.LOCKED_TAG)
            continue
        stale_note_ids.append(note["noteId"])
    if stale_note_ids:
        invoke("deleteNotes", notes=stale_note_ids)
    return len(stale_note_ids)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Sync Spanish Core Learning deck to Anki.")
    parser.add_argument("--path", default=str(IMPORT_PATH))
    parser.add_argument("--prune-stale", action="store_true", help="Delete Spanish Core Learning notes missing from the TSV.")
    parser.add_argument("--skip-media", action="store_true", help="Sync notes without storing audio media; sound tags stay on audio cards.")
    parser.add_argument("--media-only", action="store_true", help="Only store audio media from the TSV.")
    parser.add_argument("--update-model", action="store_true", help="Replace the existing note template and CSS.")
    parser.add_argument("--force", action="store_true", help="Overwrite notes even if tagged locked (manual edits).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    invoke("version")
    ensure_model(update_existing=args.update_model)
    rows = load_rows(args.path)
    if args.media_only:
        print(json.dumps({"media": sync_media(rows)}, ensure_ascii=False, indent=2))
        return 0
    result = sync_rows(rows, store_media=not args.skip_media, force=args.force)
    pruned = prune_stale_notes({row["SourceID"] for row in rows}) if args.prune_stale else 0
    print(
        json.dumps(
            {
                "synced": result,
                "pruned_stale_notes": pruned,
                "rows": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
