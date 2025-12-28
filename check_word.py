import sys
import os

def load_vocabulary(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return set()
    
    vocab = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    # Column 3 (index 2) is the word
                    word = parts[2].strip().lower().replace('"', '')
                    if word:
                        vocab.add(word)
    except Exception as e:
        print(f"Error reading file: {e}")
    return vocab

def main():
    deck_file = "4000 Essential English Words.txt"
    vocab = load_vocabulary(deck_file)
    
    if len(sys.argv) > 1:
        search_word = " ".join(sys.argv[1:]).strip().lower()
        if search_word in vocab:
            print(f"❌ '{search_word}' is ALREADY in the deck.")
        else:
            print(f"✅ '{search_word}' is NOT in the deck. Safe to add.")
    else:
        print("Usage: python check_word.py <word>")

if __name__ == "__main__":
    main()

