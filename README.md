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
The primary script. It will fetch data, generate media, and create/update the card in your **`My English Words`** deck.
```bash
python3 add_word_to_anki.py [word]
```
- If the word exists, it will ask if you want to **update** it (useful for fixing missing examples or IPA).
- If data is missing from the dictionary, it will prompt you for manual entry during the review phase.

### Dynamic Add/Update Tool
A more flexible version that allows you to specify the deck and prefix via arguments.
```bash
python3 anki_tools.py [word] --deck "My English Words" --prefix "user_"
```
- `--deck`: Target deck name (defaults to "My English Words").
- `--model`: Note type name (defaults to "4000 EEW").
- `--prefix`: Prefix for media filenames (defaults to "user_").

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
  - `english_spanish_basic.tsv` (Front, Back, Tags; back includes English translation, Spanish meaning/example, English mirrors, grammar metadata, original English source when available, optional notes, or `TODO: Spanish translation needed` when pending)

## 🧪 Testing
Run the unit test suite to verify script logic (uses mocks, no internet/Anki required):
```bash
python3 test_scripts.py
```

## 📁 File Structure
- `add_word_to_anki.py`: Standard automation logic.
- `anki_tools.py`: Fully dynamic CLI version.
- `check_word.py`: Synchronized duplicate checker.
- `grammar_levels.py`: Level-based English grammar seed generator.
- `spanish_deck.py`: Safe English-to-Spanish review/import generator.
- `get_pexels_image.py`: Standalone image downloader.
- `reorganize_decks.py`: Utility to move cards between decks.
- `4000 Essential English Words.txt`: Base vocabulary reference.

## 🔄 Syncing to Phone
Once cards are added via the scripts:
1. Open Anki on your Mac.
2. Click **Sync** (top right).
3. Open Anki on your phone and click **Sync**.
4. All text, images, and audio will be synchronized automatically.

---
*Note: This tool is intended for personal use to enhance vocabulary learning workflows.*
