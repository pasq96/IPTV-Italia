import asyncio
import json
import re
import urllib.request
import urllib.error
import sys

PLAYLIST_FILE = "iptvitaplus.m3u"
STATUS_FILE = "status.json"

SKY_PAGES = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

DEFAULT_UA = "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0) AppleWebKit/537.36 (KHTML, like Gecko)"

def fetch_fresh_sky_token(page_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    try:
        req = urllib.request.Request(page_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            match = re.search(r'https://hlslive-web-gcdn-skycdn-it\.akamaized\.net/[^\s"\'<>]+', html)
            if match:
                return match.group(0).replace('&amp;', '&').replace('\\/', '/')
    except Exception as e:
        print(f"[WARN] Impossibile recuperare token da {page_url}: {e}", file=sys.stderr)
    return None

def test_stream_url(url, user_agent=DEFAULT_UA, referrer=None):
    if "DA-INSERIRE.invalid" in url:
        return False, 0
    
    headers = {"User-Agent": user_agent}
    if referrer:
        headers["Referer"] = referrer

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status in (200, 206, 302), resp.status
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception:
        return False, 0

def parse_m3u(file_path):
    channels = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_channel = {}
    current_ua = DEFAULT_UA
    current_ref = None

    for line_idx, line in enumerate(lines):
        line_str = line.strip()
        if line_str.startswith("#EXTINF"):
            name_match = re.search(r',(.+)$', line_str)
            id_match = re.search(r'tvg-id="([^"]+)"', line_str)
            ch_no_match = re.search(r'tvg-chno="([^"]+)"', line_str)
            
            current_channel = {
                "name": name_match.group(1) if name_match else "Sconosciuto",
                "tvg_id": id_match.group(1) if id_match else "",
                "tvg_chno": ch_no_match.group(1) if ch_no_match else "",
                "line_idx": line_idx
            }
        elif line_str.startswith("#EXTVLCOPT:http-user-agent="):
            current_ua = line_str.split("=", 1)[1]
        elif line_str.startswith("#EXTVLCOPT:http-referrer="):
            current_ref = line_str.split("=", 1)[1]
        elif line_str and not line_str.startswith("#"):
            if current_channel:
                current_channel["url"] = line_str
                current_channel["user_agent"] = current_ua
                current_channel["referrer"] = current_ref
                channels.append(current_channel)
                current_channel = {}
                current_ua = DEFAULT_UA
                current_ref = None

    return channels, lines

def main():
    print("Parsing della playlist m3u...")
    channels, raw_lines = parse_m3u(PLAYLIST_FILE)
    
    status_report = []
    updated_playlist = False

    print(f"Verifica di {len(channels)} canali in corso...")

    for ch in channels:
        tvg_id = ch["tvg_id"]
        url = ch["url"]
        
        # Test iniziale dello stream
        is_online, status_code = test_stream_url(url, ch["user_agent"], ch["referrer"])
        
        # Se un canale Sky è offline o sceduto (403), tenta il refresh
        if not is_online and tvg_id in SKY_PAGES:
            print(f"[ATTENZIONE] Canale {ch['name']} ({tvg_id}) offline [{status_code}]. Tentro il recupero del nuovo token...")
            fresh_url = fetch_fresh_sky_token(SKY_PAGES[tvg_id])
            if fresh_url:
                is_online, status_code = test_stream_url(fresh_url, ch["user_agent"], ch["referrer"])
                if is_online:
                    print(f"[OK] Nuovo token generato con successo per {ch['name']}")
                    ch["url"] = fresh_url
                    # Trova la linea dell'URL nel file M3U e aggiornala
                    for i in range(ch["line_idx"] + 1, len(raw_lines)):
                        if raw_lines[i].strip() == url:
                            raw_lines[i] = fresh_url + "\n"
                            updated_playlist = True
                            break

        print(f"[{'ONLINE' if is_online else 'OFFLINE'}] {ch['tvg_chno']} - {ch['name']} ({status_code})")
        status_report.append({
            "chno": ch["tvg_chno"],
            "id": tvg_id,
            "name": ch["name"],
            "online": is_online,
            "status_code": status_code
        })

    # Salva la playlist aggiornata se ci sono state modifiche sui token
    if updated_playlist:
        with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
            f.writelines(raw_lines)
        print("[SALVATO] Playlist iptvitaplus.m3u aggiornata con i nuovi token.")

    # Scrivi lo stato nel file JSON
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_report, f, indent=2, ensure_ascii=False)
    print(f"[SALVATO] Report dello stato dei canali scritto in {STATUS_FILE}.")

if __name__ == "__main__":
    main()
