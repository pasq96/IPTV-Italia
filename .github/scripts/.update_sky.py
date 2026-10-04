import json
import re
import sys
import urllib.request

TARGET_FILE = "iptvitaplus.m3u"

# Endpoint API ufficiali di backend usati dai player web di Sky
SKY_API_ENDPOINTS = {
    "TV8.HD.it": "https://video.sky.it/be/getLive?ch=tv8",
    "cielo.it": "https://video.sky.it/be/getLive?ch=cielo",
    "Sky.TG24.it": "https://videopp.sky.it/video/live/1"
}

# Fallback: URL diretti e pagine live
SKY_PAGES = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://tg24.sky.it/",
    "Origin": "https://tg24.sky.it"
}

def extract_any_m3u8(text):
    if not text:
        return None
    # Cerca qualsiasi URL https che finisca con .m3u8 o contenga token hdnts / akamai
    matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', text)
    for m in matches:
        clean_url = m.replace('&amp;', '&').replace('\\/', '/')
        if "akamaized.net" in clean_url or "skycdn-it" in clean_url or "hdnts" in clean_url:
            return clean_url
    if matches:
        return matches[0].replace('&amp;', '&').replace('\\/', '/')
    return None

def fetch_token_url(tvg_id):
    # TENTATIVO 1: Chiamata diretta all'API Video di Sky
    api_url = SKY_API_ENDPOINTS.get(tvg_id)
    if api_url:
        try:
            req = urllib.request.Request(api_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                print(f"[DEBUG] Risposta API {tvg_id} ({len(content)} byte): {content[:200]}...")
                
                url = extract_any_m3u8(content)
                if url:
                    return url
        except Exception as e:
            print(f"[DEBUG] API fallita per {tvg_id}: {e}", file=sys.stderr)

    # TENTATIVO 2: Scraping della pagina web e ricerca ricorsiva nei file JS di Next.js
    page_url = SKY_PAGES.get(tvg_id)
    if page_url:
        try:
            req = urllib.request.Request(page_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                
                # Cerca m3u8 direttamente nell'HTML
                url = extract_any_m3u8(html)
                if url:
                    return url
                
                # Cerca URL di file .js inclusi nella pagina che potrebbero contenere gli endpoint o token
                js_files = re.findall(r'src="(/_next/static/[^\s"\'<>]+\.js)"', html)
                base_domain = page_url.split('/')[0] + '//' + page_url.split('/')[2]
                
                for js_path in js_files[:5]:  # Controlla i primi 5 bundle JS
                    js_url = base_domain + js_path
                    try:
                        js_req = urllib.request.Request(js_url, headers=HEADERS)
                        with urllib.request.urlopen(js_req, timeout=5) as js_resp:
                            js_content = js_resp.read().decode('utf-8', errors='ignore')
                            url = extract_any_m3u8(js_content)
                            if url:
                                print(f"[DEBUG] Trovato URL m3u8 dentro il bundle JS: {js_path}")
                                return url
                    except Exception:
                        pass
        except Exception as e:
            print(f"[DEBUG] Scrape pagina fallito per {tvg_id}: {e}", file=sys.stderr)

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
                if tvg_id in SKY_API_ENDPOINTS:
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