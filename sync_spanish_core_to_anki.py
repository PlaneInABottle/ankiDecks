import argparse
import base64
import csv
import json
import subprocess
import time
import urllib.request
from pathlib import Path


MODEL_NAME = "Spanish Core Learning"
IMPORT_PATH = Path("generated/spanish_core/spanish_core_learning.tsv")
OLD_DECKS = [
    "Spanish Grammar",
    "Spanish Grammar::A0 Survival",
    "Spanish Grammar::A1.1 Foundations",
    "Spanish Grammar::A1.2 Core Sentences",
    "Spanish Grammar::A2.1 Daily Past",
    "Spanish Grammar::A2.2 Natural Spanish",
]

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

CSS = """
.card {
  background: #f7f0df;
  color: #24211c;
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
.meta {
  color: #6d6252;
  font-size: 13px;
  letter-spacing: 0;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.front {
  font-size: 26px;
  font-weight: 650;
  margin: 14px 0;
}
.topic-label {
  color: #7a4f20;
  font-size: 18px;
  font-weight: 600;
}
.answer {
  color: #1d5f52;
  font-size: 30px;
  font-weight: 700;
  margin: 14px 0;
}
.section {
  border-top: 1px solid rgba(36, 33, 28, 0.18);
  margin-top: 14px;
  padding-top: 12px;
}
.label {
  color: #7a4f20;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 5px;
}
.detail {
  font-size: 19px;
}
.examples {
  color: #373128;
  font-size: 18px;
}
.wrong-spanish {
  color: #9c2f24;
  text-decoration: line-through;
}
.english-mirror {
  color: #5e574d;
  font-size: 18px;
  font-weight: 500;
}
.type-note {
  color: #6d6252;
  font-size: 14px;
  margin-top: 8px;
}
.source {
  color: #7b7164;
  font-size: 12px;
  margin-top: 14px;
}
input {
  max-width: 92%;
}
"""

FRONT_TEMPLATE = """
<div class="wrap">
  <div class="meta">{{Level}} · {{CardType}}</div>
  <div class="front">{{Front}}</div>
  {{#TypeAnswer}}
    <div class="type-note">Type the Spanish answer, then compare carefully.</div>
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
    <div class="label">Why</div>
    <div class="detail">{{Back}}</div>
  </div>
  <div class="section">
    <div class="label">Formula</div>
    <div class="detail">{{Formula}}</div>
  </div>
  <div class="section">
    <div class="label">Examples</div>
    <div class="examples">{{Examples}}</div>
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


def ensure_model():
    model_names = invoke("modelNames")
    if MODEL_NAME not in model_names:
        invoke(
            "createModel",
            modelName=MODEL_NAME,
            inOrderFields=FIELDS,
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
    for field in FIELDS:
        if field not in existing_fields:
            invoke("modelFieldAdd", modelName=MODEL_NAME, fieldName=field)
            existing_fields.append(field)
    invoke("updateModelTemplates", model={"name": MODEL_NAME, "templates": {"Spanish Core Card": {"Front": FRONT_TEMPLATE, "Back": BACK_TEMPLATE}}})
    invoke("updateModelStyling", model={"name": MODEL_NAME, "css": CSS})


def load_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    header = rows[2]
    return [dict(zip(header, row)) for row in rows[3:]]


def find_existing_note(source_id):
    note_ids = invoke("findNotes", query=f'"SourceID:{source_id}"')
    return note_ids[0] if note_ids else None


def load_existing_notes():
    note_ids = invoke("findNotes", query=f'note:"{MODEL_NAME}"')
    if not note_ids:
        return {}
    existing = {}
    for note in invoke("notesInfo", notes=note_ids):
        fields = note.get("fields", {})
        source_id = fields.get("SourceID", {}).get("value", "")
        if source_id:
            existing[source_id] = note["noteId"]
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


def sync_rows(rows, store_media=True):
    created = 0
    updated = 0
    moved = 0
    existing_notes = load_existing_notes()
    for deck_name in sorted({row["DeckPath"] for row in rows}):
        invoke("createDeck", deck=deck_name)
    for index, row in enumerate(rows, start=1):
        deck_name = row["DeckPath"]
        if store_media:
            store_audio(row)
        fields = {field: row.get(field, "") for field in FIELDS}
        note_id = existing_notes.get(row["SourceID"])
        if note_id:
            invoke("updateNoteFields", note={"id": note_id, "fields": fields})
            card_ids = invoke("findCards", query=f"nid:{note_id}")
            if card_ids:
                invoke("changeDeck", cards=card_ids, deck=deck_name)
                moved += len(card_ids)
            updated += 1
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
    return {"created": created, "updated": updated, "moved_cards": moved}


def prune_stale_notes(valid_source_ids):
    note_ids = invoke("findNotes", query=f'note:"{MODEL_NAME}"')
    if not note_ids:
        return 0
    stale_note_ids = []
    for note in invoke("notesInfo", notes=note_ids):
        fields = note.get("fields", {})
        source_id = fields.get("SourceID", {}).get("value", "")
        if source_id and source_id not in valid_source_ids:
            stale_note_ids.append(note["noteId"])
    if stale_note_ids:
        invoke("deleteNotes", notes=stale_note_ids)
    return len(stale_note_ids)


def prune_foreign_core_notes():
    card_ids = invoke("findCards", query=f'deck:"{MODEL_NAME}"')
    if not card_ids:
        return 0
    note_ids = sorted({card["note"] for card in invoke("cardsInfo", cards=card_ids)})
    stale_note_ids = [
        note["noteId"]
        for note in invoke("notesInfo", notes=note_ids)
        if note.get("modelName") != MODEL_NAME
    ]
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
    parser = argparse.ArgumentParser(description="Sync Spanish Core Learning deck to Anki.")
    parser.add_argument("--path", default=str(IMPORT_PATH))
    parser.add_argument("--delete-old-spanish-grammar", action="store_true")
    parser.add_argument("--prune-stale", action="store_true", help="Delete Spanish Core Learning notes missing from the TSV.")
    parser.add_argument("--skip-media", action="store_true", help="Sync notes without storing audio media; sound tags stay on audio cards.")
    parser.add_argument("--media-only", action="store_true", help="Only store audio media from the TSV.")
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
    pruned_foreign = prune_foreign_core_notes() if args.prune_stale else 0
    deleted = delete_old_decks() if args.delete_old_spanish_grammar else []
    print(
        json.dumps(
            {
                "synced": result,
                "pruned_stale_notes": pruned,
                "pruned_foreign_core_notes": pruned_foreign,
                "deleted_decks": deleted,
                "rows": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
