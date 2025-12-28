# Anki Deck Automation Tools

This repository contains a suite of Python scripts designed to automate the creation and management of Anki flashcards, specifically tailored for the "4000 Essential English Words" format.

## 🚀 Features
- **Auto-Fetch**: Automatically retrieves definitions, example sentences, and IPA transcriptions from dictionary APIs.
- **Auto-Image**: Searches Pexels for relevant images and uploads them directly to Anki.
- **Auto-Audio**: Generates high-quality Text-to-Speech (TTS) for words and sentences using macOS built-in voices.
- **AnkiConnect Integration**: Pushes cards directly into Anki without manual importing.
- **Duplicate Prevention**: Checks both your local text files and Anki collection before adding new words.

## 🛠 Setup

### 1. Prerequisites
- **macOS**: Required for the `say` command (TTS).
- **Anki Desktop**: Must be running for the scripts to work.
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
The primary script. It will fetch data, generate media, and create/update the card in the `My English Words` deck.
```bash
python3 add_word_to_anki.py [word]
```
- If the word exists, it will ask if you want to **update** it (useful for fixing missing examples).
- If an example sentence is missing from the dictionary, it will prompt you to type one.

### Dynamic Add/Update Tool
A more flexible version that allows you to specify the deck and prefix via arguments.
```bash
python3 anki_tools.py [word] --deck "My English Words" --prefix "user_"
```
- `--deck`: Target deck name (defaults to "My English Words").
- `--model`: Note type name (defaults to "4000 EEW").
- `--prefix`: Prefix for media filenames (defaults to "user_").

### Check for Duplicates
Check if a word already exists in the original `4000 Essential English Words.txt` file.
```bash
python3 check_word.py [word]
```

### Manual Image Download
Download an image for a specific word to your Anki media folder.
```bash
python3 get_pexels_image.py [word]
```

## 🧪 Testing
Run the unit test suite to verify script logic:
```bash
python3 test_scripts.py
```

## 📁 File Structure
- `add_word_to_anki.py`: The main automation logic.
- `check_word.py`: Local duplicate checker.
- `get_pexels_image.py`: Standalone image downloader.
- `reorganize_decks.py`: Utility to move cards between decks.
- `4000 Essential English Words.txt`: The base vocabulary file.

## 🔄 Syncing to Phone
Once cards are added via the scripts:
1. Open Anki on your Mac.
2. Click **Sync** (top right).
3. Open Anki on your phone and click **Sync**.
4. All text, images, and audio will be downloaded to your device automatically.

---
*Note: This tool is intended for personal use to enhance vocabulary learning workflows.*
