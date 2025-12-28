import os
import sys
import json
import urllib.request
import urllib.error

def load_env(file_path):
    env = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    env[key] = value
    return env

def download_image(word, media_folder):
    env = load_env(".env")
    api_key = env.get("PEXELS_API_KEY")
    
    if not api_key:
        print("Error: PEXELS_API_KEY not found in .env")
        return None

    query = word
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", api_key)
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36")

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        if not data.get("photos"):
            print(f"No direct results for '{word}', trying 'alphabet'...")
            url = f"https://api.pexels.com/v1/search?query=alphabet&per_page=1"
            req = urllib.request.Request(url)
            req.add_header("Authorization", api_key)
            req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())

        if data.get("photos"):
            photo_url = data["photos"][0]["src"]["medium"]
            image_name = f"{word}.jpg"
            image_path = os.path.join(media_folder, image_name)

            print(f"Downloading image from: {photo_url}")
            image_req = urllib.request.Request(photo_url)
            image_req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36")
            with urllib.request.urlopen(image_req) as response:
                with open(image_path, 'wb') as f:
                    f.write(response.read())
            
            print(f"✅ Saved image to: {image_path}")
            return image_name
        else:
            print("No images found.")
            return None
    except urllib.error.URLError as e:
        print(f"Network error: {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_pexels_image.py <word>")
        sys.exit(1)
    
    word = sys.argv[1]
    media_dir = os.path.expanduser("~/Library/Application Support/Anki2/User 1/collection.media")
    
    if not os.path.exists(media_dir):
        print(f"Creating media directory: {media_dir}")
        os.makedirs(media_dir, exist_ok=True)
        
    download_image(word, media_dir)