import re
import urllib.request
import sys

TARGET_FILE = "iptvitaplus.m3u"

SKY_TARGETS = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://skytg24.it/live"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def fetch_token_url(page_url):
    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            match = re.search(r'https://hlslive-web-gcdn-skycdn-it\.akamaized\.net/[^\s"\'<>]+', html)
            if match:
                return match.group(0).replace('&amp;', '&')
    except Exception as e:
        print(f"[ERR] {page_url}: {e}", file=sys.stderr)
    return None

def main():
    try:
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[ERR] File {TARGET_FILE} non trovato.", file=sys.stderr)
        sys.exit(1)

    updated = []
    i = 0
    total = len(lines)

    while i < total:
        line = lines[i]
        updated.append(line)
        
        if line.startswith("#EXTINF"):
            match = re.search(r'tvg-id="([^"]+)"', line)
            if match:
                tvg_id = match.group(1)
                if tvg_id in SKY_TARGETS:
                    new_url = fetch_token_url(SKY_TARGETS[tvg_id])
                    if new_url:
                        # Avanza mantenendo eventuali righe #EXTVLCOPT
                        while i + 1 < total and lines[i + 1].startswith("#"):
                            i += 1
                            updated.append(lines[i])
                        # Sostituisci l'URL vecchio
                        i += 1
                        updated.append(new_url + "\n")
                        print(f"[OK] {tvg_id}")
        i += 1

    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        f.writelines(updated)

if __name__ == "__main__":
    main()
