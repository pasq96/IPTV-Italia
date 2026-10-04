import re
import sys
from playwright.sync_api import sync_playwright

TARGET_FILE = "iptvitaplus.m3u"

SKY_PAGES = {
    "TV8.HD.it": "https://tv8.it/streaming",
    "cielo.it": "https://www.cielotv.it/streaming.html",
    "Sky.TG24.it": "https://tg24.sky.it/diretta"
}

def get_akamai_token_via_browser(page_url):
    found_url = None
    with sync_playwright() as p:
        # Avvia Chromium headless
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Intercetta tutte le richieste HTTP uscite dalla pagina
        def handle_request(request):
            nonlocal found_url
            url = request.url
            if "akamaized.net" in url and "master.m3u8" in url and "hdnts" in url:
                found_url = url

        page.on("request", handle_request)

        try:
            page.goto(page_url, timeout=25000, wait_until="domcontentloaded")
            # Attende fino a 8 secondi per permettere all'infrastruttura video di avviarsi
            page.wait_for_timeout(8000)
        except Exception as e:
            print(f"[ERR] Errore caricamento {page_url}: {e}", file=sys.stderr)
        finally:
            browser.close()

    return found_url

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
                    print(f"Sto estraendo il token per {tvg_id} via Browser...")
                    new_url = get_akamai_token_via_browser(SKY_PAGES[tvg_id])
                    
                    if new_url:
                        while i + 1 < total and lines[i + 1].startswith("#"):
                            i += 1
                            updated.append(lines[i])
                        i += 1
                        updated.append(new_url + "\n")
                        print(f"[OK] Token estratto con successo per {tvg_id}!")
                    else:
                        print(f"[SKIP] Impossibile intercettare lo stream per {tvg_id}.", file=sys.stderr)
        i += 1

    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        f.writelines(updated)

if __name__ == "__main__":
    main()