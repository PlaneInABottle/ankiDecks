import json
import urllib.request

def invoke(action, **params):
    request_payload = json.dumps({'action': action, 'params': params, 'version': 6}).encode('utf-8')
    try:
        response = urllib.request.urlopen(urllib.request.Request('http://localhost:8765', request_payload))
        return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error connecting to Anki: {e}")
        return None

def move_cards():
    source_deck = "4000 Essential English Words::7.UserAdded"
    target_deck = "4000 Essential English Words::7.Book"
    
    print(f"🔍 Searching for cards in: {source_deck}")
    
    # 1. Find all cards in the source deck
    query = f"deck:\"{source_deck}\""
    result = invoke("findCards", query=query)
    card_ids = result.get("result", [])
    
    if not card_ids:
        print("✅ No cards found in the source deck. Everything is already organized!")
        return

    print(f"📦 Found {len(card_ids)} cards. Moving to {target_deck}...")
    
    # 2. Ensure target deck exists
    invoke("createDeck", deck=target_deck)
    
    # 3. Move the cards
    move_result = invoke("changeDeck", cards=card_ids, deck=target_deck)
    
    if move_result and move_result.get("error") is None:
        print(f"🚀 Successfully moved {len(card_ids)} cards to {target_deck}!")
        # 4. Delete the empty source deck
        invoke("deleteDecks", decks=[source_deck], cardsToo=False)
        print(f"🗑️ Deleted empty deck: {source_deck}")
    else:
        print(f"❌ Failed to move cards: {move_result.get('error')}")

if __name__ == "__main__":
    move_cards()
