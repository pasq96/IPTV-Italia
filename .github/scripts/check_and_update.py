import json
import re
import ssl
import sys
import urllib.error
import urllib.request

PLAYLIST_FILE = "iptvitaplus.m3u"
STATUS_FILE = "status.json"

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Connection": "keep-alive"
}

def get_headers_for_channel(url, custom_ua=None, custom_ref=None):
    headers = HEADERS_BASE.copy()
    url_lower = url.lower()

    if "mediaset" in url_lower or "hbbtv.mediaset.it" in url_lower or "live3" in url_lower:
        headers["Referer"] = "https://mediasetinfinity.mediaset.it/"
        headers["Origin"] = "https://mediasetinfinity.mediaset.it"
    elif "rai.it" in url_lower or "raiplay" in url_lower or "monterosa" in url_lower:
        headers["Referer"] = "https://www.raiplay.it/"
        headers["Origin"] = "https://www.raiplay.it"
    elif "discovery" in url_lower or "dmax" in url_lower or "realtime" in url_lower:
        headers["Referer"] = "https://www.discoveryplus.com/"
    elif "cloudfront" in url_lower or "la7" in url_lower:
        headers["User-Agent"] = "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0)"

    if custom_ua:
        headers["User-Agent"] = custom_ua
    if custom_ref:
        headers["Referer"] = custom_ref

    return headers

def test_stream_url(url, user_agent=None, referrer=None, channel_name=""):
    if not url or "DA-INSERIRE.invalid" in url:
        return False, 404

    # Headers per bypass WAF Akamai/Cloudflare su GitHub Actions
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0 (Linux; U; HbbTV/1.7.1; SmartTV; CE-HTML/1.0)",
        "Accept": "*/*",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
        "Origin": "https://www.raiplay.it" if "rai" in url.lower() else "https://mediasetinfinity.mediaset.it",
        "Referer": referrer or ("https://www.raiplay.it/" if "rai" in url.lower() else "https://mediasetinfinity.mediaset.it/")
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor()
    )

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with opener.open(req, timeout=10) as resp:
            status = resp.getcode()
            return status in (200, 206, 302), status
    except urllib.error.HTTPError as e:
        # Se riceve 403 (tipico blocco IP GitHub Actions), riprova simulando client HbbTV generico
        if e.code == 403:
            headers["User-Agent"] = "HbbTV/1.5.1 (+ETH+SmartTV; LGE; WebOS;)"
            try:
                req_retry = urllib.request.Request(url, headers=headers, method="GET")
                with opener.open(req_retry, timeout=10) as resp_retry:
                    return resp_retry.getcode() in (200, 206, 302), resp_retry.getcode()
            except Exception:
                pass
        return False, e.code
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

    print(f"Verifica avanzata di {len(channels)} canali in corso...")

    for ch in channels:
        is_online, status_code = test_stream_url(
            ch["url"], 
            ch["user_agent"], 
            ch["referrer"], 
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