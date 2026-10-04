import json
import re
import sys
import urllib.request

TARGET_FILE = "iptvitaplus.m3u"

# Endpoint delle pagine live ufficiali
SKY_TARGETS = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

# Header realistici da browser desktop
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def extract_akamai_url(text):
    """Cerca l'URL Akamai master.m3u8 contenente il token hdnts."""
    if not text:
        return None
    # Pattern 1: URL Akamai standard con token hdnts
    match = re.search(r'https://hlslive-web-gcdn-skycdn-it\.akamaized\.net/[^\s"\'<>]+', text)
    if match:
        url = match.group(0).replace('&amp;', '&').replace('\\/', '/')
        return url
    return None

def fetch_from_brightcove(account_id, video_id, bc_policy):
    """Fallback per estrarre lo stream direttamente da Brightcove Playback API."""
    try:
        url = f"https://edge.api.brightcove.com/playback/v1/accounts/{account_id}/videos/{video_id}"
        req = urllib.request.Request(url, headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept": f"application/json;pk={bc_policy}"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for source in data.get("sources", []):
                src_url = source.get("src", "")
                if "akamaized.net" in src_url and "m3u8" in src_url:
                    return src_url
    except Exception as e:
        print(f"[DEBUG] Brightcove API err: {e}", file=sys.stderr)
    return None

def fetch_token_url(tvg_id):
    page_url = SKY_TARGETS.get(tvg_id)
    if not page_url:
        return None

    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

            # 1. Cerca il link Akamai diretto nell'HTML
            found_url = extract_akamai_url(html)
            if found_url:
                return found_url

            # 2. Cerca nel blocco JSON __NEXT_DATA__ di Next.js
            next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
            if next_data_match:
                json_str = next_data_match.group(1)
                found_url = extract_akamai_url(json_str)
                if found_url:
                    return found_url

            # 3. Cerca parametri Brightcove embed (video-id, account-id)
            account_match = re.search(r'data-account="(\d+)"', html)
            video_match = re.search(r'data-video-id="(\d+)"', html)
            policy_match = re.search(r'data-player="([^"]+)"', html)
            
            if account_match and video_match:
                acc_id = account_match.group(1)
                vid_id = video_match.group(1)
                policy = policy_match.group(1) if policy_match else ""
                found_url = fetch_from_brightcove(acc_id, vid_id, policy)
                if found_url:
                    return found_url

    except Exception as e:
        print(f"[ERR] Fallita richiesta a {page_url}: {e}", file=sys.stderr)

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
                    new_url = fetch_token_url(tvg_id)
                    if new_url:
                        # Salta le righe con tag direttiva (#EXTVLCOPT ecc.) mantenendole
                        while i + 1 < total and lines[i + 1].startswith("#"):
                            i += 1
                            updated.append(lines[i])
                        # Sostituisce l'URL vecchio con quello nuovo
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