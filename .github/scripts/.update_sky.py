import re
import urllib.request
import sys

TARGET_FILE = "iptvitaplus.m3u"

# Mappa degli URL corretti delle dirette web ufficiali
SKY_TARGETS = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
}

def fetch_token_url(page_url):
    try:
        # Costruzione di un opener che segue i redirect HTTP
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        req = urllib.request.Request(page_url, headers=HEADERS)
        
        with opener.open(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
            # Cerca l'URL del master manifest con il token Akamai hdnts
            match = re.search(r'https://hlslive-web-gcdn-skycdn-it\.akamaized\.net/[^\s"\'<>]+', html)
            if match:
                return match.group(0).replace('&amp;', '&')
            else:
                print(f"[WARN] Nessun link Akamai trovato nella pagina {page_url}", file=sys.stderr)
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
                        # Mantiene eventuali direttive #EXTVLCOPT
                        while i + 1 < total and lines[i + 1].startswith("#"):
                            i += 1
                            updated.append(lines[i])
                        # Sostituisce l'URL vecchio con quello nuovo
                        i += 1
                        updated.append(new_url + "\n")
                        print(f"[OK] Token aggiornato per {tvg_id}")
                    else:
                        print(f"[SKIP] Impossibile aggiornare {tvg_id}, mantengo il vecchio URL.")
        i += 1

    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        f.writelines(updated)

if __name__ == "__main__":
    main()