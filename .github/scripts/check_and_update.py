import json
import re
import urllib.request
import urllib.error
import sys

PLAYLIST_FILE = "iptvitaplus.m3u"
STATUS_FILE = "status.json"

# Header predefiniti per bypassare i controlli CDN dei principali network italiani
NETWORK_HEADERS = {
    "mediaset": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://mediasetinfinity.mediaset.it/",
        "Origin": "https://mediasetinfinity.mediaset.it"
    },
    "rai": {
        "User-Agent": "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0) AppleWebKit/537.36 (KHTML, like Gecko)",
        "Referer": "https://www.raiplay.it/"
    },
    "discovery": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.discoveryplus.com/"
    },
    "default": {
        "User-Agent": "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
}

def get_headers_for_url(url, custom_ua=None, custom_ref=None):
    headers = {}
    url_lower = url.lower()

    if "mediaset" in url_lower or "hbbtv.mediaset.it" in url_lower:
        headers.update(NETWORK_HEADERS["mediaset"])
    elif "rai.it" in url_lower or "raiplay" in url_lower:
        headers.update(NETWORK_HEADERS["rai"])
    elif "discovery" in url_lower or "dmax" in url_lower or "realtime" in url_lower:
        headers.update(NETWORK_HEADERS["discovery"])
    else:
        headers.update(NETWORK_HEADERS["default"])

    # Se la playlist M3U ha una direttiva specifica (#EXTVLCOPT), sovrascrivi
    if custom_ua:
        headers["User-Agent"] = custom_ua
    if custom_ref:
        headers["Referer"] = custom_ref

    return headers

def test_stream_url(url, user_agent=None, referrer=None):
    if not url or "DA-INSERIRE.invalid" in url:
        return False, 0

    headers = get_headers_for_url(url, user_agent, referrer)

    try:
        # Inviamo una richiesta GET per verificare se la CDN risponde correttamente
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
    current_ua = None
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
                current_ua = None
                current_ref = None

    return channels, lines

def main():
    channels, raw_lines = parse_m3u(PLAYLIST_FILE)
    status_report = []

    print(f"Verifica di {len(channels)} canali con header di rete personalizzati...")

    for ch in channels:
        is_online, status_code = test_stream_url(ch["url"], ch["user_agent"], ch["referrer"])

        print(f"[{'ONLINE' if is_online else 'OFFLINE'}] Ch {ch['tvg_chno']} - {ch['name']} ({status_code})")
        status_report.append({
            "chno": ch["tvg_chno"],
            "id": ch["tvg_id"],
            "name": ch["name"],
            "online": is_online,
            "status_code": status_code
        })

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_report, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Report aggiornato salvato in {STATUS_FILE}")

if __name__ == "__main__":
    main()
