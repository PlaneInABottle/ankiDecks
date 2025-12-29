import sys
import os
import json
import urllib.request

def invoke(action, **params):
    """Talks to AnkiConnect."""
    request_payload = json.dumps({'action': action, 'params': params, 'version': 6}).encode('utf-8')
    try:
        response = urllib.request.urlopen(urllib.request.Request('http://localhost:8765', request_payload), timeout=2)
        response_data = json.loads(response.read().decode('utf-8'))
        return response_data.get('result')
    except:
        return None

def load_file_vocabulary(file_path):
    """Loads words from the local text file."""
    if not os.path.exists(file_path):
        return set()
    vocab = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip(): continue
                parts = line.split('\t')
                # In the 4000 txt file, the word is usually column 3 (index 2) or 6 (index 5) depending on deck
                # We'll check common word columns
                for idx in [2, 5]:
                    if len(parts) > idx:
                        word = parts[idx].strip().lower().replace('"', '')
                        if word and not word.startswith('<'): # Ignore HTML
                            vocab.add(word)
    except: pass
    return vocab

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_word.py <word>")
        return

    search_word = " ".join(sys.argv[1:]).strip().lower()
    
    # 1. Check local file
    file_vocab = load_file_vocabulary("4000 Essential English Words.txt")
    in_file = search_word in file_vocab

    # 2. Check Anki collection (talks to Anki app)
    # This query searches for the word in the "Word" field across ALL decks
    anki_notes = invoke("findNotes", query=f"\"Word:{search_word}\"")
    in_anki = bool(anki_notes)

    if in_file or in_anki:
        location = []
        if in_file: location.append("4000 txt file")
        if in_anki: location.append("Anki collection (My English Words or other decks)")
        print(f"❌ '{search_word}' is ALREADY in: {', '.join(location)}.")
    else:
        # Check if Anki was reachable
        status = ""
        if invoke("version") is None:
            status = " (Note: Anki app was not open to check collection)"
        print(f"✅ '{search_word}' is NOT found{status}. Safe to add.")

if __name__ == "__main__":
    main()