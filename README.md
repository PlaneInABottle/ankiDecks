# Anki Deck Automation Tools

This repository contains a suite of Python scripts designed to automate the creation and management of Anki flashcards, specifically tailored for the "4000 Essential English Words" format.

## 🚀 Features
- **Auto-Fetch**: Automatically retrieves definitions, example sentences, and IPA transcriptions from dictionary APIs.
- **Root Fallback**: Automatically checks root forms (e.g., "transliterate" for "transliterated") if data or IPA is missing for the specific word form.
- **Auto-Image**: Searches Pexels for relevant images and uploads them directly to Anki.
- **Auto-Audio**: Generates high-quality Text-to-Speech (TTS) for words, meanings, and examples using macOS built-in voices (`say`) and `ffmpeg`.
- **AnkiConnect Integration**: Pushes cards directly into Anki without manual importing.
- **Smart Duplicate Prevention**: Checks both your local `4000 Essential English Words.txt` and your live Anki collection (including the new `My English Words` deck) before adding words.
- **Auto-Formatting**: Automatically bolds the target word in example sentences to match your deck style.

## 🛠 Setup

### 1. Prerequisites
- **macOS**: Required for the `say` command (TTS).
- **Anki Desktop**: Must be running for the scripts to talk to your collection.
- **AnkiConnect Add-on**:
  - Open Anki -> Tools -> Add-ons -> Get Add-ons.
  - Enter code: `2055492159`.
  - Restart Anki.
- **FFmpeg**: Required for audio conversion.
  ```bash
  brew install ffmpeg
  ```

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
PEXELS_API_KEY=your_api_key_here
```

## 📖 Usage

### Add or Update a Word
This tool fetches data, generates media, and creates or explicitly updates a card. It defaults to **`My English Words`** and also accepts a custom deck, model, and media prefix.
```bash
python3 anki_tools.py [word] --deck "My English Words" --prefix "user_"
```
- `--deck`: Target deck name (defaults to "My English Words").
- `--model`: Note type name (defaults to "4000 EEW").
- `--prefix`: Prefix for media filenames (defaults to "user_").
- When a word already exists, blank update prompts keep the current live Anki values. Only entered fields are replaced, and an edited note is tagged `locked` automatically.

### Check for Duplicates
Reliably checks if a word exists in the original 4000 txt file OR your active Anki collection.
```bash
python3 check_word.py [word]
```

### Generate English Grammar Deck Seed
Create B2/C1/C2 choose-the-correct-form grammar TSV files for import into Anki (no Anki connection required):
```bash
python3 grammar_levels.py
python3 grammar_levels.py --output-dir generated_custom
python3 grammar_levels.py --summary
```
- Output:
  - `generated/english_grammar_basic.tsv` (choose cards with answer, grammar name, formula, reason, examples, and self-grade guidance)
  - `generated/english_grammar_cloze.tsv` (header-only placeholder; the deck intentionally avoids cloze guessing cards)
- You can import the basic file into the `Grammar Maintenance` note type in Anki.
- `--summary` prints per-level card counts and does not create files.

### Create Spanish Duplicate Decks
Create a duplicate workflow for learning the same 4000 English words in Spanish.
Reviewed entries stay safe; untranslated entries are clearly marked for later review.

```bash
python3 spanish_deck.py
python3 spanish_deck.py --glossary reviewed_es.csv
python3 spanish_deck.py --summary
python3 spanish_deck.py --limit 20
```

Defaults:
- Source: `4000 Essential English Words.txt`
- Glossary: optional CSV/TSV with headers `english,spanish,spanish_meaning,spanish_example,notes`
  - Backward-compatible: `english,spanish,spanish_example,notes` is still accepted
  - Optional durable fields are also accepted: `spanish_meaning_en`, `spanish_example_en`, `spanish_article`, `spanish_gender`, `spanish_number`, `spanish_part_of_speech`, `spanish_forms`
- Output directory: `generated/spanish`
- Files produced:
  - `english_spanish_review.tsv` (English/source context, Spanish, pronunciation, Spanish meaning/example, English mirrors of the Spanish fields, grammar metadata, notes, status, source identity, tags)

The durable reviewed source is `generated/spanish_reviewed_glossary_full.tsv`. Regenerate the active full review file with:

```bash
python3 spanish_deck.py \
  --glossary generated/spanish_reviewed_glossary_full.tsv \
  --output-dir generated/spanish_full
```

### Production Decks

Generate the Turkish cues and the structured Spanish/English decks before syncing:

```bash
python3 generate_english_turkish_cues.py
python3 spanish_core_learning.py
python3 english_mastery.py
```

The 4000-word production fronts include a short reviewed context cue with the answer and common inflections masked. Exact typing is retained for uniquely constrained prompts; duplicate Turkish/English cues with multiple valid answers are self-graded so correct synonyms are not marked wrong.

With Anki open, apply content and template updates safely:

```bash
python3 protect_manual_edits.py --apply
python3 sync_4000_production_to_anki.py --sync-spanish-content --update-models
python3 sync_spanish_core_to_anki.py --update-model
python3 sync_english_mastery_to_anki.py --update-model
```

These commands update existing note IDs in place. Do not add `--force` unless intentionally replacing protected manual edits.

### Protect Manual Edits
Bulk sync scripts automatically preserve manual edits. Each synced note records a hidden `SyncFingerprint`; if its live content later differs from the last script-written version, the next sync tags it `locked` and skips content updates. On the first fingerprint-aware sync, hashes in `generated/legacy_sync_fingerprints.json` recognize changed rows from the previous generated release without storing card text. Unrecognized differences are still locked instead of overwritten.

To audit or lock existing edits proactively while Anki is open:

```bash
python3 protect_manual_edits.py          # report only (dry run)
python3 protect_manual_edits.py --apply  # also tag detected edits as locked
```

Notes tagged `locked` are skipped by every sync script's content update and by stale-note pruning, so manual edits survive. New notes are still created and deck moves still happen. Stale pruning also refuses to delete legacy notes without a fingerprint. To intentionally overwrite locked or changed notes, pass `--force` to the relevant sync script.

Existing note templates and CSS are also preserved by default. Use `--update-model` on the English Mastery or Spanish Core sync, or `--update-models` on the 4000 production sync, only when you intentionally want to replace model presentation.

## 🧪 Testing
Run the unit test suite to verify script logic (uses mocks, no internet/Anki required):
```bash
python3 test_scripts.py
```

## 📁 File Structure
- `anki_tools.py`: Add or explicitly update individual vocabulary notes without replacing untouched live fields.
- `anki_protect.py`: Shared fingerprint and locked-tag protection used by all bulk syncs.
- `protect_manual_edits.py`: Report or proactively lock live notes that differ from their generated source.
- `check_word.py`: Synchronized duplicate checker.
- `grammar_levels.py`: Level-based English grammar seed generator.
- `spanish_deck.py`: Safe English-to-Spanish review/import generator.
- `get_pexels_image.py`: Standalone image downloader.
- `4000 Essential English Words.txt`: Base vocabulary reference.

## 🔄 Syncing to Phone
Once cards are added via the scripts:
1. Open Anki on your Mac.
2. Click **Sync** (top right).
3. Open Anki on your phone and click **Sync**.
4. All text, images, and audio will be synchronized automatically.

---
*Note: This tool is intended for personal use to enhance vocabulary learning workflows.*
