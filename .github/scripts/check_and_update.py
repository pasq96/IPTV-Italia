import json
import re
import subprocess
import sys

PLAYLIST_FILE = "iptvitaplus.m3u"
STATUS_FILE = "status.json"

def test_stream_url(url, user_agent=None, referrer=None, channel_name=""):
    # Gestione esplicita dei placeholder
    if not url or "DA-INSERIRE.invalid" in url:
        return False, 404

    # Costruzione comando ffprobe
    command = [
        "ffprobe",
        "-hide_banner",
        "-loglevel", "error",
        "-timeout", "8000000"  # Timeout di 8 secondi in microsecondi
    ]

    # Aggiunta dell'User-Agent personalizzato se presente
    ua = user_agent or "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0)"
    command.extend(["-user_agent", ua])

    # Aggiunta degli header personalizzati (es. Referer)
    url_lower = url.lower()
    if referrer:
        command.extend(["-headers", f"Referer: {referrer}\r\n"])
    elif "rai" in url_lower:
        command.extend(["-headers", "Referer: https://www.raiplay.it/\r\n"])
    elif "mediaset" in url_lower:
        command.extend(["-headers", "Referer: https://mediasetinfinity.mediaset.it/\r\n"])

    command.extend(["-i", url])

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        
        if result.returncode == 0:
            return True, 200
        else:
            stderr_str = result.stderr.decode("utf-8", errors="ignore")
            if "403 Forbidden" in stderr_str:
                return False, 403
            elif "404 Not Found" in stderr_str:
                return False, 404
            return False, 503
    except subprocess.TimeoutExpired:
        return False, 504
    except Exception:
        return False, 503

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

    print(f"Verifica avanzata di {len(channels)} canali con ffprobe in corso...")

    for ch in channels:
        is_online, status_code = test_stream_url(
            ch["url"], 
            ch.get("user_agent"), 
            ch.get("referrer"), 
            ch["name"]
        )

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