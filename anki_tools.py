import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
import base64
import argparse

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

def get_word_data(word):
    """Fetches definition, example, and IPA with root fallback."""
    def fetch_api(w):
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{w}"
        try:
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode())[0]
        except: return None

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
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data.get("photos"):
                return data["photos"][0]["src"]["medium"]
    except: return None
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
        if os.path.exists(temp_aiff): os.remove(temp_aiff)
        if os.path.exists(output_mp3): os.remove(output_mp3)
        return data
    except: return None

def find_note_id(word):
    query = f"\"Word:{word}\""
    result = invoke("findNotes", query=query)
    return result[0] if result else None

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
    if note_id:
        print(f"⚠️ '{word}' exists. (ID: {note_id})")
        if input("Update existing card? (y/n): ").lower() != 'y': return
        is_update = True

    data = get_word_data(word)
    image_url = get_image_url(word)
    meaning, example, ipa = data['meaning'], data['example'], data['ipa']

    if not example and not is_update:
         print(f"⚠️ No example found.")
         example = input(f"Enter example for '{word}': ")

    if is_update:
        print(f"\n--- Fetched ---\n1. Meaning: {meaning}\n2. Example: {example}\n3. IPA: {ipa}\n--------------")
        user_m = input("New Meaning (enter to keep): ")
        if user_m: meaning = user_m
        user_e = input("New Example (enter to keep): ")
        if user_e: example = user_e
        user_i = input("New IPA (enter to keep): ")
        if user_i: ipa = user_i

    if example and word in example.lower() and "<b>" not in example:
        import re
        example = re.compile(re.escape(word), re.IGNORECASE).sub(f"<b>{word}</b>", example)

    print("🔊 Generating audio...")
    w_aud = generate_audio_base64(word, "tw")
    m_aud = generate_audio_base64(meaning, "tm")
    e_aud = generate_audio_base64(example.replace("<b>", "").replace("</b>", ""), "te")

    media_map = {}
    for key, aud in [("word", w_aud), ("meaning", m_aud), ("example", e_aud)]:
        if aud:
            fname = f"{args.prefix}{word}{'' if key=='word' else '_'+key}.mp3"
            invoke("storeMediaFile", filename=fname, data=aud)
            media_map[key] = fname

    fields = {
        "Word": word, "Meaning": meaning, "Example": example, "IPA": ipa,
        "Sound": f"[sound:{media_map.get('word','')}]" if "word" in media_map else "",
        "Sound_Meaning": f"[sound:{media_map.get('meaning','')}]" if "meaning" in media_map else "",
        "Sound_Example": f"[sound:{media_map.get('example','')}]" if "example" in media_map else ""
    }

    if is_update:
        invoke("updateNoteFields", note={"id": note_id, "fields": fields})
        print(f"✅ Updated card!")
    else:
        invoke("createDeck", deck=args.deck)
        note = {"deckName": args.deck, "modelName": args.model, "fields": fields, "options": {"allowDuplicate": False}, "tags": ["added_by_script"]}
        if image_url:
            note["picture"] = [{"url": image_url, "filename": f"{args.prefix}{word}.jpg", "fields": ["Image"]}]
        res = invoke("addNote", note=note)
        print(f"✅ Added to {args.deck}! (ID: {res})" if res else "❌ Failed")

if __name__ == "__main__":
    main()
