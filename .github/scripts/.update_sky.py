import json
import re
import sys
import urllib.request

TARGET_FILE = "iptvitaplus.m3u"

# API/Endpoint di configurazione dei player web ufficiali Sky
SKY_ENDPOINTS = {
    "TV8.HD.it": "https://tv8.it/api/getLiveStream",
    "cielo.it": "https://www.cielotv.it/api/getLiveStream",
    "Sky.TG24.it": "https://tg24.sky.it/api/getLiveStream"
}

# Pagine fallback se l'endpoint JSON principale richiede scraping avanzato
SKY_PAGES = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://tv8.it/"
}

def extract_akamai_url(text):
    """Cerca la presenza di un manifest Akamai con token hdnts."""
    match = re.search(r'https://hlslive-web-gcdn-skycdn-it\.akamaized\.net/[^\s"\'<>]+', text)
    if match:
        return match.group(0).replace('&amp;', '&').replace('\\/', '/')
    return None

def fetch_token_url(tvg_id):
    # Tentativo 1: Chiamata API diretta
    api_url = SKY_ENDPOINTS.get(tvg_id)
    if api_url:
        try:
            req = urllib.request.Request(api_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                
                # Prova a fare il parsing JSON
                try:
                    data = json.loads(content)
                    # Cerca ricorsivamente qualsiasi valore URL nel JSON
                    json_str = json.dumps(data)
                    found_url = extract_akamai_url(json_str)
                    if found_url:
                        return found_url
                except Exception:
                    pass

                # Se non è JSON o fallisce, cerca la regex nel body grezzo
                found_url = extract_akamai_url(content)
                if found_url:
                    return found_url
        except Exception:
            pass

    # Tentativo 2: Scrape della pagina web standard seguendo eventuali build Manifest di Next.js
    page_url = SKY_PAGES.get(tvg_id)
    if page_url:
        try:
            req = urllib.request.Request(page_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                
                # Estrai eventuali manifest o token Akamai embedded nei dati NEXT_DATA o JS inline
                found_url = extract_akamai_url(html)
                if found_url:
                    return found_url
        except Exception as e:
            print(f"[ERR] Fallito recupero per {tvg_id}: {e}", file=sys.stderr)

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
                if tvg_id in SKY_ENDPOINTS:
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
