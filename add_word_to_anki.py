import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
import base64

# --- CONFIGURATION ---
DECK_NAME = "My English Words"
MODEL_NAME = "4000 EEW"
MEDIA_PREFIX = "user_"

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
        response = urllib.request.urlopen(urllib.request.Request('http://localhost:8765', request_payload))
        response_data = json.loads(response.read().decode('utf-8'))
        if response_data.get('error'):
            raise Exception(response_data['error'])
        return response_data['result']
    except Exception as e:
        print(f"AnkiConnect Error: {e}")
        return None

def get_word_data(word, is_update=False):
    """Fetches definition, example, and IPA from Free Dictionary API."""
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            entry = data[0]
            
            ipa = entry.get("phonetic", "")
            if not ipa and entry.get("phonetics"):
                for p in entry["phonetics"]:
                    if p.get("text"):
                        ipa = p["text"]
                        break
            
            meaning = ""
            example = ""
            if entry.get("meanings"):
                found = False
                for m in entry["meanings"]:
                    for d in m["definitions"]:
                        if not meaning: meaning = d.get("definition", "")
                        if d.get("example"):
                            example = d.get("example", "")
                            found = True
                            break
                    if found: break
            
            # Bold target word in example
            if example and word in example.lower():
                import re
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                example = pattern.sub(f"<b>{word}</b>", example)
                
            return {"ipa": ipa, "meaning": meaning, "example": example}
    except:
        return {"ipa": "", "meaning": "", "example": ""}

def generate_audio_base64(text, filename_core):
    if not text: return None
    temp_aiff = f"{filename_core}.aiff"
    output_mp3 = f"{filename_core}.mp3"
    try:
        # 1. macOS 'say' creates high-quality AIFF
        subprocess.run(["say", "-o", temp_aiff, text], check=True)
        # 2. ffmpeg converts to Anki-friendly MP3
        subprocess.run(["ffmpeg", "-y", "-i", temp_aiff, "-codec:a", "libmp3lame", "-qscale:a", "2", output_mp3], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        with open(output_mp3, "rb") as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        
        # Cleanup
        if os.path.exists(temp_aiff): os.remove(temp_aiff)
        if os.path.exists(output_mp3): os.remove(output_mp3)
        return data
    except Exception as e:
        print(f"Audio Error for '{text[:20]}...': {e}")
        return None

def get_image_url(word):
    env = load_env(".env")
    api_key = env.get("PEXELS_API_KEY")
    if not api_key: return None
    
    url = f"https://api.pexels.com/v1/search?query={word}&per_page=1"
    req = urllib.request.Request(url)
    req.add_header("Authorization", api_key)
    req.add_header("User-Agent", "Mozilla/5.0")
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data.get("photos"):
                return data["photos"][0]["src"]["medium"]
    except:
        return None
    return None

def find_note_id(word):
    """Finds the Anki note ID for a given word."""
    query = f"\"Word:{word}\""
    result = invoke("findNotes", query=query)
    return result[0] if result else None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 add_word_to_anki.py <word>")
        return

    word = sys.argv[1].strip().lower()
    print(f"🚀 Processing: {word}")

    note_id = find_note_id(word)
    is_update = False
    
    if note_id:
        print(f"⚠️ '{word}' already exists in Anki.")
        choice = input("Would you like to update the existing card? (y/n): ")
        if choice.lower() != 'y': return
        is_update = True

    # 1. Data Fetching
    data = get_word_data(word, is_update)
    image_url = get_image_url(word)
    
    meaning = data['meaning']
    example = data['example']
    ipa = data['ipa']

    if not example and not is_update:
         print(f"⚠️ No example found for '{word}' in dictionary.")
         example = input(f"Please enter an example sentence for '{word}': ")

    if is_update:
        print("\n--- Current Fetched Data ---")
        print(f"1. Meaning: {meaning}")
        print(f"2. Example: {example}")
        print(f"3. IPA: {ipa}")
        print("----------------------------")
        
        user_meaning = input(f"New Meaning (leave empty to keep fetched): ")
        if user_meaning: meaning = user_meaning
        user_example = input(f"New Example (leave empty to keep fetched): ")
        if user_example: example = user_example
        
        # Ensure bolding if user entered something
        if example and word in example.lower() and "<b>" not in example:
            import re
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            example = pattern.sub(f"<b>{word}</b>", example)

    print(f"\n📝 Final Word: {word}")
    print(f"📖 Meaning: {meaning}")
    print(f"📝 Example: {example}")
    print(f"🔊 IPA: {ipa}")

    # 2. Audio Generation
    print("🔊 Generating audio files...")
    word_audio = generate_audio_base64(word, "tmp_word")
    meaning_audio = generate_audio_base64(meaning, "tmp_meaning")
    example_audio = generate_audio_base64(example, "tmp_example")

    # 3. Store Media Files in Anki
    media_filenames = {}
    if word_audio:
        fname = f"{MEDIA_PREFIX}{word}.mp3"
        invoke("storeMediaFile", filename=fname, data=word_audio)
        media_filenames["word"] = fname
    
    if meaning_audio:
        fname = f"{MEDIA_PREFIX}{word}_meaning.mp3"
        invoke("storeMediaFile", filename=fname, data=meaning_audio)
        media_filenames["meaning"] = fname

    if example_audio:
        fname = f"{MEDIA_PREFIX}{word}_example.mp3"
        invoke("storeMediaFile", filename=fname, data=example_audio)
        media_filenames["example"] = fname

    # 4. Push to Anki
    if is_update:
        fields = {
            "Word": word,
            "Meaning": meaning,
            "Example": example,
            "IPA": ipa,
            "Sound": f"[sound:{media_filenames.get('word', '')}]" if "word" in media_filenames else "",
            "Sound_Meaning": f"[sound:{media_filenames.get('meaning', '')}]" if "meaning" in media_filenames else "",
            "Sound_Example": f"[sound:{media_filenames.get('example', '')}]" if "example" in media_filenames else ""
        }
        # In updates, we don't usually re-download image unless explicitly wanted, 
        # but for simplicity we'll stick to fields for now.
        result = invoke("updateNoteFields", note={"id": note_id, "fields": fields})
        print(f"✅ Card updated! (ID: {note_id})")
    else:
        # 5. Ensure Deck Exists
        invoke("createDeck", deck=DECK_NAME)

        note = {
            "deckName": DECK_NAME,
            "modelName": MODEL_NAME,
            "fields": {
                "Word": word,
                "Meaning": meaning,
                "Example": example,
                "IPA": ipa,
                "Sound": f"[sound:{media_filenames.get('word', '')}]" if "word" in media_filenames else "",
                "Sound_Meaning": f"[sound:{media_filenames.get('meaning', '')}]" if "meaning" in media_filenames else "",
                "Sound_Example": f"[sound:{media_filenames.get('example', '')}]" if "example" in media_filenames else ""
            },
            "options": {"allowDuplicate": False},
            "tags": ["added_by_ai_script"]
        }
        if image_url:
            note["picture"] = [{
                "url": image_url,
                "filename": f"{MEDIA_PREFIX}{word}.jpg",
                "fields": ["Image"]
            }]
        
        result = invoke("addNote", note=note)
        if result:
            print(f"✅ Card added to Anki! (ID: {result})")
        else:
            print(f"❌ Failed to add card.")

if __name__ == "__main__":
    main()
