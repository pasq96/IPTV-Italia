import concurrent.futures
import json
import re
import subprocess
import sys
import time
import urllib.request

PLAYLIST_FILE = "iptvitaplus.m3u"
STATUS_FILE = "status.json"
MAX_WORKERS = 8

def refresh_sky_token(channel_name):
    slug_map = {
        "TV8": "https://www.tv8.it/api/live",
        "Cielo": "https://www.cielotv.it/api/live",
        "Sky TG24": "https://skytg24.sky.it/api/live"
    }

    api_url = None
    for key, url in slug_map.items():
        if key.lower() in channel_name.lower():
            api_url = url
            break

    if not api_url:
        return None

    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.tv8.it/"
            }
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            return data.get("streaming_url") or data.get("hls_url") or data.get("url")
    except Exception:
        return None

def run_ffprobe_check(target_url, headers):
    command = [
        "ffprobe",
        "-hide_banner",
        "-loglevel", "error",
        "-probesize", "65536",
        "-analyzeduration", "1000000",
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-headers", headers,
        "-rw_timeout", "6000000",
        "-i", target_url
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=8
        )
        if result.returncode == 0:
            return True, 200

        stderr_str = result.stderr.decode("utf-8", errors="ignore")
        if "404 Not Found" in stderr_str or "Server returned 404" in stderr_str:
            return False, 404
        elif "403 Forbidden" in stderr_str or "Server returned 403" in stderr_str:
            return True, 200
        else:
            return False, 503
    except subprocess.TimeoutExpired:
        return True, 200
    except Exception:
        return False, 503

def test_stream_url(ch):
    url = ch["url"]
    channel_name = ch["name"]

    if not url or "DA-INSERIRE.invalid" in url:
        return ch, False, 404, url

    refreshed_url = refresh_sky_token(channel_name)
    target_url = refreshed_url if refreshed_url else url
    url_lower = target_url.lower()

    is_la7 = "la7" in url_lower or "cloudfront" in url_lower

    if is_la7:
        ua = "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0)"
        ref = "https://www.la7.it/"
    else:
        ua = ch.get("user_agent") or "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0) AppleWebKit/537.36"
        ref = ch.get("referrer") or ("https://www.raiplay.it/" if "rai" in url_lower else "https://mediasetinfinity.mediaset.it/")

    headers = f"User-Agent: {ua}\r\nReferer: {ref}\r\n"

    is_online, status_code = run_ffprobe_check(target_url, headers)

    if status_code == 503:
        time.sleep(0.5)
        is_online, status_code = run_ffprobe_check(target_url, headers)

    if status_code == 503 and is_la7:
        is_online, status_code = True, 200

    return ch, is_online, status_code, target_url

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
    m3u_updated = False

    print(f"Verifica parallela di {len(channels)} canali ({MAX_WORKERS} worker)...", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_stream_url, ch) for ch in channels]

        for future in futures:
            ch, is_online, status_code, active_url = future.result()

            # Controlla se l'URL attivo è diverso da quello originale nella playlist
            token_refreshed = (active_url != ch["url"] and is_online)

            if token_refreshed:
                status_label = "ONLINE + TOKEN REFRESHED"
                raw_lines[ch["line_idx"] + 1] = active_url + "\n"
                m3u_updated = True
            else:
                status_label = "ONLINE" if is_online else "OFFLINE"

            print(f"[{status_label}] Ch {ch['tvg_chno']} - {ch['name']} ({status_code})", flush=True)

            status_report.append({
                "chno": ch["tvg_chno"],
                "id": ch["tvg_id"],
                "name": ch["name"],
                "online": is_online,
                "status_code": status_code,
                "token_refreshed": token_refreshed
            })

    if m3u_updated:
        with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
            f.writelines(raw_lines)
        print(f"[OK] Playlist {PLAYLIST_FILE} aggiornata con i nuovi token dinamici.", flush=True)

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_report, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Report aggiornato salvato in {STATUS_FILE}", flush=True)

if __name__ == "__main__":
    main()