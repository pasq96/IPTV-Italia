import json
import re
import sys
import urllib.request

TARGET_FILE = "iptvitaplus.m3u"

# Pagine delle dirette ufficiali
SKY_PAGES = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8"
}

def fetch_brightcove_stream(account_id, video_id, policy_key):
    """Interroga l'API di Playback Brightcove ufficiale di Sky."""
    api_url = f"https://edge.api.brightcove.com/playback/v1/accounts/{account_id}/videos/{video_id}"
    bc_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": f"application/json;pk={policy_key}",
        "Origin": "https://tg24.sky.it"
    }
    
    try:
        req = urllib.request.Request(api_url, headers=bc_headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
            # Esplora le sorgenti per trovare il manifest m3u8 Akamai con token hdnts
            for source in data.get("sources", []):
                src = source.get("src", "")
                if "akamaized.net" in src and "m3u8" in src:
                    return src
                elif "m3u8" in src:
                    return src
    except Exception as e:
        print(f"[DEBUG] Errore API Brightcove ({video_id}): {e}", file=sys.stderr)
    
    return None

def fetch_token_url(tvg_id):
    page_url = SKY_PAGES.get(tvg_id)
    if not page_url:
        return None

    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
            # 1. Prova prima l'estrazione diretta se Akamai è nell'HTML
            match = re.search(r'https://hlslive-web-gcdn-skycdn-it\.akamaized\.net/[^\s"\'<>]+', html)
            if match:
                return match.group(0).replace('&amp;', '&').replace('\\/', '/')

            # 2. Cerca parametri del player Brightcove nell'HTML (data-account, data-video-id, policyKey)
            account_match = re.search(r'data-account="(\d+)"', html) or re.search(r'"accountId":\s*"(\d+)"', html)
            video_match = re.search(r'data-video-id="(\d+)"', html) or re.search(r'"videoId":\s*"(\d+)"', html) or re.search(r'data-video-id="ref:([^"]+)"', html)
            policy_match = re.search(r'policyKey:\s*"([^"]+)"', html) or re.search(r'data-policy-key="([^"]+)"', html) or re.search(r'pk=([^"&]+)', html)

            if account_match and video_match:
                acc_id = account_match.group(1)
                vid_id = video_match.group(1)
                # Policy key standard usata dalle webapp Sky/Brightcove se non trovata inline
                p_key = policy_match.group(1) if policy_match else "BCpkADawqM0aT424eX9I_nNl3S6I3_eN2m2o7vX7U5u5s1v1"
                
                print(f"[DEBUG] Estratti parametri Brightcove per {tvg_id}: Account={acc_id}, Video={vid_id}")
                stream_url = fetch_brightcove_stream(acc_id, vid_id, p_key)
                if stream_url:
                    return stream_url

            # 3. Fallback: Cerca in eventuali script JS bundle integrati nella pagina
            js_links = re.findall(r'src="(/_next/static/[^\s"\'<>]+\.js)"', html)
            domain = "https://" + page_url.split('/')[2]
            
            for js_path in js_links[:3]:
                try:
                    js_req = urllib.request.Request(domain + js_path, headers=HEADERS)
                    with urllib.request.urlopen(js_req, timeout=5) as js_resp:
                        js_text = js_resp.read().decode('utf-8', errors='ignore')
                        
                        # Cerca chiavi policy o video-id nei bundle JS
                        if not policy_match:
                            pk_in_js = re.search(r'BCpk[A-Za-z0-9_-]+', js_text)
                            if pk_in_js and account_match and video_match:
                                stream_url = fetch_brightcove_stream(account_match.group(1), video_match.group(1), pk_in_js.group(0))
                                if stream_url:
                                    return stream_url
                except Exception:
                    pass

    except Exception as e:
        print(f"[ERR] Errore nel caricamento di {page_url}: {e}", file=sys.stderr)

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
                if tvg_id in SKY_PAGES:
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