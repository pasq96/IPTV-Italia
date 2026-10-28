#!/usr/bin/env python3
"""Genera l'EPG unito usato da iptvitaplus.m3u.

Sorgenti:
  * epgitalia.tv  -> guida completa per la maggior parte dei canali italiani
  * open-epg.com  -> palinsesti Warner/Discovery e radio TV assenti in epgitalia

Il file prodotto (epg.xml.gz) contiene solo i canali presenti nella playlist,
con gli id riscritti sui tvg-id della playlist stessa, cosi' il player deve
caricare una sola sorgente EPG.
"""

from __future__ import annotations

import gzip
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

PRIMARY_URL = "https://www.epgitalia.tv/gzip"
SECONDARY_URL = "https://www.open-epg.com/files/italy9.xml.gz"
USER_AGENT = "IPTV-Italia-EPG-Builder/1.0 (+https://github.com/pasq96/IPTV-Italia)"

PLAYLIST = Path("iptvitaplus.m3u")
OUTPUT = Path("epg.xml.gz")
CACHE_DIR = Path(".epg-cache")

# tvg-id playlist -> id canale nella sorgente secondaria.
# Servono solo per i canali che epgitalia non copre (0 programmi).
OVERRIDES = {
    "NOVE": "Nove.it",
    "Real Time": "Real.Time.it",
    "DMAX": "DMAX.it",
    "Food Network": "Food.Network.it",
    "Giallo": "Giallo.TV.it",
    "HGTV HD": "HGTV.it",
    "Motor Trend": "Motor.Trend.it",
    "Discovery Channel": "Discovery.Channel.it",
    "RaiRadio2.it": "RaiRadio2.it",
    "R101TV.it": "R101tv.it",
    "Virgin Radio": "Virgin.Radio.it",
    "Radio Monte Carlo": "RMC.it",
    "SportitaliaSolocalcio.it": "Solocalcio.it.it",
}

CHANNEL_RE = re.compile(r'<channel\s+id="([^"]+)"')
PROGRAMME_RE = re.compile(r'<programme\b[^>]*\bchannel="([^"]+)"')
DISPLAY_RE = re.compile(r"<display-name[^>]*>([^<]*)</display-name>")
TVG_ID_RE = re.compile(r'tvg-id="([^"]*)"')


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).lower()
    value = re.sub(r"\.it$", "", value)
    value = value.replace("and", "")
    return re.sub(r"[^a-z0-9]", "", value)


def log(message: str) -> None:
    print(message, flush=True)


def download(url: str, filename: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    target = CACHE_DIR / filename
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    log(f"[download] {url}")
    with urllib.request.urlopen(request, timeout=180) as response, target.open("wb") as out:
        out.write(response.read())
    log(f"[download] {target} ({target.stat().st_size / 1024 / 1024:.1f} MB)")
    return target


def open_xml(path: Path):
    with path.open("rb") as handle:
        if handle.read(2) == b"\x1f\x8b":
            return gzip.open(path, "rt", encoding="utf-8-sig", errors="replace")
    return path.open("rt", encoding="utf-8-sig", errors="replace")


def playlist_ids(path: Path) -> list[str]:
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#EXTINF"):
            match = TVG_ID_RE.search(line)
            if match and match.group(1) and match.group(1) not in ids:
                ids.append(match.group(1))
    return ids


def index_source(path: Path) -> tuple[dict[str, int], dict[str, set[str]]]:
    """Restituisce (programmi per id, nomi alternativi per id)."""
    counts: dict[str, int] = {}
    names: dict[str, set[str]] = {}
    current: str | None = None
    pending: set[str] = set()

    for line in open_xml(path):
        stripped = line.lstrip()
        if stripped.startswith("<channel "):
            match = CHANNEL_RE.search(line)
            current = match.group(1) if match else None
            pending = set()
        elif stripped.startswith("<display-name") and current:
            match = DISPLAY_RE.search(line)
            if match:
                pending.add(match.group(1))
        elif stripped.startswith("</channel>") and current:
            names[current] = pending
            counts.setdefault(current, 0)
            current = None
            pending = set()
        elif stripped.startswith("<programme"):
            match = PROGRAMME_RE.search(line)
            if match:
                counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts, names


def collect(path: Path, wanted: dict[str, str]) -> tuple[list[str], list[str]]:
    """Estrae i blocchi <channel> e <programme> degli id richiesti.

    wanted: id sorgente -> id di output (tvg-id della playlist).
    """
    channels: list[str] = []
    programmes: list[str] = []

    channel_buffer: list[str] | None = None
    channel_source: str = ""
    programme_buffer: list[str] | None = None
    skipping_programme = False

    for line in open_xml(path):
        stripped = line.lstrip()

        if channel_buffer is not None:
            channel_buffer.append(line)
            if "</channel>" in line:
                block = "".join(channel_buffer).replace(
                    f'id="{channel_source}"', f'id="{wanted[channel_source]}"', 1
                )
                channels.append(block)
                channel_buffer = None
            continue

        if programme_buffer is not None:
            programme_buffer.append(line)
            if "</programme>" in line:
                first = programme_buffer[0].replace(
                    f'channel="{skipping_programme}"', f'channel="{wanted[skipping_programme]}"', 1
                )
                programmes.append(first + "".join(programme_buffer[1:]))
                programme_buffer = None
                skipping_programme = False
            continue

        if stripped.startswith("<channel "):
            match = CHANNEL_RE.search(line)
            source = match.group(1) if match else None
            if source and source in wanted:
                if "</channel>" in line:
                    channels.append(
                        line.replace(f'id="{source}"', f'id="{wanted[source]}"', 1)
                    )
                else:
                    channel_buffer = [line]
                    channel_source = source
            continue

        if stripped.startswith("<programme"):
            match = PROGRAMME_RE.search(line)
            source = match.group(1) if match else None
            if source and source in wanted:
                if "</programme>" in line:
                    programmes.append(
                        line.replace(f'channel="{source}"', f'channel="{wanted[source]}"', 1)
                    )
                else:
                    programme_buffer = [line]
                    skipping_programme = source
            continue

    return channels, programmes


def pick_secondary_id(tvg_id: str, counts: dict[str, int], names: dict[str, set[str]]) -> str | None:
    if tvg_id in OVERRIDES:
        candidate = OVERRIDES[tvg_id]
        return candidate if counts.get(candidate, 0) > 0 else None

    key = norm(tvg_id)
    if not key:
        return None
    candidates = []
    for channel_id, count in counts.items():
        if count <= 0:
            continue
        keys = {norm(channel_id)} | {norm(n) for n in names.get(channel_id, set())}
        if key in keys:
            candidates.append((count, channel_id))
    if not candidates:
        return None
    return max(candidates)[1]


def build() -> int:
    ids = playlist_ids(PLAYLIST)
    if not ids:
        log("[errore] nessun tvg-id trovato nella playlist")
        return 1
    log(f"[playlist] {len(ids)} tvg-id")

    primary_path = download(PRIMARY_URL, "epgitalia.xml.gz")
    try:
        secondary_path = download(SECONDARY_URL, "openepg-italy9.xml.gz")
    except Exception as exc:  # noqa: BLE001 - la sorgente secondaria e' opzionale
        log(f"[warn] sorgente secondaria non disponibile: {exc}")
        secondary_path = None

    primary_counts, primary_names = index_source(primary_path)
    log(f"[epgitalia] {sum(primary_counts.values())} programmi, {len(primary_counts)} canali")

    secondary_counts: dict[str, int] = {}
    secondary_names: dict[str, set[str]] = {}
    if secondary_path is not None:
        secondary_counts, secondary_names = index_source(secondary_path)
        log(
            f"[open-epg] {sum(secondary_counts.values())} programmi, "
            f"{len(secondary_counts)} canali"
        )

    primary_wanted: dict[str, str] = {}
    secondary_wanted: dict[str, str] = {}
    source_of: dict[str, str] = {}

    for tvg_id in ids:
        if primary_counts.get(tvg_id, 0) > 0:
            primary_wanted[tvg_id] = tvg_id
            source_of[tvg_id] = "epgitalia"
            continue
        if secondary_path is None:
            continue
        secondary_id = pick_secondary_id(tvg_id, secondary_counts, secondary_names)
        if secondary_id:
            secondary_wanted[secondary_id] = tvg_id
            source_of[tvg_id] = f"open-epg:{secondary_id}"

    channels: list[str] = []
    programmes: list[str] = []
    if primary_wanted:
        ch, pr = collect(primary_path, primary_wanted)
        channels.extend(ch)
        programmes.extend(pr)
    if secondary_wanted:
        ch, pr = collect(secondary_path, secondary_wanted)
        channels.extend(ch)
        programmes.extend(pr)

    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<tv generator-info-name="IPTV-Italia merged EPG" '
        'generator-info-url="https://github.com/pasq96/IPTV-Italia">\n'
    )
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as out:
        out.write(header)
        out.writelines(channels)
        out.writelines(programmes)
        out.write("</tv>\n")

    used = sorted(tvg_id for tvg_id in ids if tvg_id in source_of)
    missing = [tvg_id for tvg_id in ids if tvg_id not in source_of]

    log("")
    log(f"[output] {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB)")
    log(f"[output] {len(channels)} canali, {len(programmes)} programmi")
    log(f"[copertura] {len(used)}/{len(ids)} tvg-id con EPG")
    if missing:
        log(f"[senza EPG] {len(missing)}: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(build())
