import os
import json
import urllib.request
import urllib.error
import subprocess
import base64
import argparse

import anki_protect

def load_env(file_path):
    env = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    env[key] = value
    return env

def invoke(action, **params):
    request_payload = json.dumps({'action': action, 'params': params, 'version': 6}).encode('utf-8')
    try:
        response = urllib.request.urlopen(
            urllib.request.Request('http://localhost:8765', request_payload),
            timeout=60,
        )
        response_data = json.loads(response.read().decode('utf-8'))
        if response_data.get('error'):
            raise RuntimeError(response_data['error'])
        return response_data['result']
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"AnkiConnect request failed: {error}") from error

def get_word_data(word):
    """Fetches definition, example, and IPA with root fallback."""
    def fetch_api(w):
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{w}"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                return json.loads(response.read().decode())[0]
        except (OSError, json.JSONDecodeError, IndexError, KeyError):
            return None

    entry = fetch_api(word)
    
    ipa = ""
    if entry:
        ipa = entry.get("phonetic", "")
        if not ipa and entry.get("phonetics"):
            for p in entry["phonetics"]:
                if p.get("text"): ipa = p["text"]; break
    
    if not ipa:
        root = word
        if word.endswith("ed"): root = word[:-2]
        elif word.endswith("ing"): root = word[:-3]
        elif word.endswith("s"): root = word[:-1]
        if root != word:
            root_entry = fetch_api(root)
            if root_entry:
                ipa = root_entry.get("phonetic", "")
                if not ipa and root_entry.get("phonetics"):
                    for p in root_entry["phonetics"]:
                        if p.get("text"): ipa = p["text"]; break
    
    meaning, example = "", ""
    if entry and entry.get("meanings"):
        found = False
        for m in entry["meanings"]:
            for d in m["definitions"]:
                if not meaning: meaning = d.get("definition", "")
                if d.get("example"):
                    example = d.get("example", "")
                    found = True; break
            if found: break
    
    if example and word in example.lower():
        import re
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        example = pattern.sub(f"<b>{word}</b>", example)
        
    return {"ipa": ipa, "meaning": meaning, "example": example}

def get_image_url(word):
    env = load_env(".env")
    api_key = env.get("PEXELS_API_KEY")
    if not api_key: return None
    url = f"https://api.pexels.com/v1/search?query={word}&per_page=1"
    req = urllib.request.Request(url)
    req.add_header("Authorization", api_key)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            if data.get("photos"):
                return data["photos"][0]["src"]["medium"]
    except (OSError, json.JSONDecodeError, IndexError, KeyError):
        return None
    return None

def generate_audio_base64(text, filename_core):
    if not text: return None
    temp_aiff, output_mp3 = f"{filename_core}.aiff", f"{filename_core}.mp3"
    try:
        subprocess.run(["say", "-o", temp_aiff, text], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", temp_aiff, "-codec:a", "libmp3lame", "-qscale:a", "2", output_mp3], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with open(output_mp3, "rb") as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        return data
    except (OSError, subprocess.CalledProcessError):
        return None
    finally:
        if os.path.exists(temp_aiff): os.remove(temp_aiff)
        if os.path.exists(output_mp3): os.remove(output_mp3)

def find_note_id(word):
    query = f"\"Word:{word}\""
    result = invoke("findNotes", query=query)
    return result[0] if result else None

def get_note_fields(note_id):
    notes = invoke("notesInfo", notes=[note_id])
    if not notes:
        return None
    return {
        name: value.get("value", "")
        for name, value in notes[0].get("fields", {}).items()
    }

def main():
    parser = argparse.ArgumentParser(description="Anki Automation Tool")
    parser.add_argument("word", help="The word to process")
    parser.add_argument("--deck", default="My English Words", help="Target deck name")
    parser.add_argument("--model", default="4000 EEW", help="Anki note type name")
    parser.add_argument("--prefix", default="user_", help="Prefix for media files")
    args = parser.parse_args()

    word = args.word.strip().lower()
    print(f"🚀 Processing: {word}")

    note_id = find_note_id(word)
    is_update = False
    current_fields = {}
    if note_id:
        print(f"⚠️ '{word}' exists. (ID: {note_id})")
        if input("Update existing card? (y/n): ").lower() != 'y': return
        is_update = True
        current_fields = get_note_fields(note_id)
        if current_fields is None:
            print("❌ Could not read the existing card; nothing was changed.")
            return

    data = get_word_data(word)
    image_url = None if is_update else get_image_url(word)
    meaning, example, ipa = data['meaning'], data['example'], data['ipa']

    if not example and not is_update:
         print(f"⚠️ No example found.")
         example = input(f"Enter example for '{word}': ")

    if is_update:
        print(
            "\n--- Current card ---"
            f"\n1. Meaning: {current_fields.get('Meaning', '')}"
            f"\n2. Example: {current_fields.get('Example', '')}"
            f"\n3. IPA: {current_fields.get('IPA', '')}"
            "\n--- Fetched suggestions ---"
            f"\n1. Meaning: {meaning}"
            f"\n2. Example: {example}"
            f"\n3. IPA: {ipa}"
            "\n---------------------------"
        )
        user_m = input("New Meaning (leave empty to keep current): ")
        user_e = input("New Example (leave empty to keep current): ")
        user_i = input("New IPA (leave empty to keep current): ")
        meaning = user_m or current_fields.get("Meaning", "")
        example = user_e or current_fields.get("Example", "")
        ipa = user_i or current_fields.get("IPA", "")

    example_changed = not is_update or example != current_fields.get("Example", "")
    if example_changed and example and word in example.lower() and "<b>" not in example:
        import re
        example = re.compile(re.escape(word), re.IGNORECASE).sub(f"<b>{word}</b>", example)

    audio_requests = []
    if not is_update:
        audio_requests.append(("word", word, "tw"))
    if not is_update or meaning != current_fields.get("Meaning", ""):
        audio_requests.append(("meaning", meaning, "tm"))
    if not is_update or example != current_fields.get("Example", ""):
        spoken_example = example.replace("<b>", "").replace("</b>", "")
        audio_requests.append(("example", spoken_example, "te"))

    media_map = {}
    failed_audio = set()
    if audio_requests:
        print("🔊 Generating audio for changed text...")
    for key, text, filename_core in audio_requests:
        aud = generate_audio_base64(text, filename_core)
        if aud:
            fname = f"{args.prefix}{word}{'' if key=='word' else '_'+key}.mp3"
            invoke("storeMediaFile", filename=fname, data=aud)
            media_map[key] = fname
        else:
            failed_audio.add(key)

    if is_update:
        if "meaning" in failed_audio:
            meaning = current_fields.get("Meaning", "")
            print("⚠️ Meaning audio failed; meaning and sound were left unchanged.")
        if "example" in failed_audio:
            example = current_fields.get("Example", "")
            print("⚠️ Example audio failed; example and sound were left unchanged.")
        fields = {}
        for name, value in {"Meaning": meaning, "Example": example, "IPA": ipa}.items():
            if value != current_fields.get(name, ""):
                fields[name] = value
        sound_fields = {"word": "Sound", "meaning": "Sound_Meaning", "example": "Sound_Example"}
        for key, filename in media_map.items():
            fields[sound_fields[key]] = f"[sound:{filename}]"
        if not fields:
            print("✅ No changes entered; the existing card was left untouched.")
            return
        invoke("updateNoteFields", note={"id": note_id, "fields": fields})
        invoke("addTags", notes=[note_id], tags=anki_protect.LOCKED_TAG)
        print("✅ Updated card and tagged it 'locked' so bulk syncs preserve it.")
    else:
        fields = {
            "Word": word, "Meaning": meaning, "Example": example, "IPA": ipa,
            "Sound": f"[sound:{media_map.get('word','')}]" if "word" in media_map else "",
            "Sound_Meaning": f"[sound:{media_map.get('meaning','')}]" if "meaning" in media_map else "",
            "Sound_Example": f"[sound:{media_map.get('example','')}]" if "example" in media_map else ""
        }
        invoke("createDeck", deck=args.deck)
        note = {"deckName": args.deck, "modelName": args.model, "fields": fields, "options": {"allowDuplicate": False}, "tags": ["added_by_script"]}
        if image_url:
            note["picture"] = [{"url": image_url, "filename": f"{args.prefix}{word}.jpg", "fields": ["Image"]}]
        res = invoke("addNote", note=note)
        print(f"✅ Added to {args.deck}! (ID: {res})" if res else "❌ Failed")

if __name__ == "__main__":
    main()
