import json
import re
import subprocess
import sys
import urllib.request

TARGET_FILE = "iptvitaplus.m3u"

SKY_TARGETS = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
}

def extract_akamai_url(text):
    if not text:
        return None
    match = re.search(r'https://hlslive-web-gcdn-skycdn-it\.akamaized\.net/[^\s"\'<>]+', text)
    if match:
        url = match.group(0).replace('&amp;', '&').replace('\\/', '/')
        return url
    return None

def fetch_with_curl(url):
    """Fallback usando cURL per bypassare i blocchi HTTP/TLS di urllib sui runner GitHub."""
    try:
        cmd = [
            "curl", "-sL",
            "-A", HEADERS["User-Agent"],
            "-H", f"Accept: {HEADERS['Accept']}",
            "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.stdout
    except Exception as e:
        print(f"[DEBUG] cURL error per {url}: {e}", file=sys.stderr)
        return ""

def fetch_token_url(tvg_id):
    page_url = SKY_TARGETS.get(tvg_id)
    if not page_url:
        return None

    html = ""
    # Tentativo 1: urllib
    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            print(f"[DEBUG] urllib success per {tvg_id} (length: {len(html)})")
    except Exception as e:
        print(f"[DEBUG] urllib fallito per {tvg_id}: {e}. Provo fallback con cURL...", file=sys.stderr)

    # Tentativo 2: cURL (se urllib ha fallito o ha restituito pagina vuota/corta)
    if len(html) < 1000:
        html = fetch_with_curl(page_url)
        print(f"[DEBUG] cURL response per {tvg_id} (length: {len(html)})")

    if not html:
        print(f"[ERR] Nessun contenuto ricevuto da {page_url}", file=sys.stderr)
        return None

    # Estrazione 1: Regex diretta su Akamai
    found_url = extract_akamai_url(html)
    if found_url:
        return found_url

    # Estrazione 2: Cerca nel blocco JSON __NEXT_DATA__
    next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if next_data:
        print(f"[DEBUG] Trovato __NEXT_DATA__ per {tvg_id}")
        found_url = extract_akamai_url(next_data.group(1))
        if found_url:
            return found_url

    # Estrazione 3: Cerca URL m3u8 generici con token
    generic_m3u8 = re.search(r'https://[^\s"\'<>]+\.m3u8\?[^\s"\'<>]+hdnts[^\s"\'<>]+', html)
    if generic_m3u8:
        print(f"[DEBUG] Trovato m3u8 generico per {tvg_id}")
        return generic_m3u8.group(0).replace('&amp;', '&').replace('\\/', '/')

    print(f"[WARN] Nessun pattern Akamai/m3u8 trovato in {page_url}", file=sys.stderr)
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
                    print(f"\n--- Inizio estrazione per: {tvg_id} ---")
                    new_url = fetch_token_url(tvg_id)
                    if new_url:
                        while i + 1 < total and lines[i + 1].startswith("#"):
                            i += 1
                            updated.append(lines[i])
                        i += 1
                        updated.append(new_url + "\n")
                        print(f"[OK] Token aggiornato per {tvg_id}")
                    else:
                        print(f"[SKIP] Impossibile aggiornare {tvg_id}, mantengo il vecchio URL.", file=sys.stderr)
        i += 1

    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        f.writelines(updated)

if __name__ == "__main__":
    main()