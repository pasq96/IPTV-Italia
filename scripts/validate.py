#!/usr/bin/env python3
"""Valida playlist ed EPG senza modificare nulla.

Controlli sulla playlist:
  * header #EXTM3U, righe #EXTINF con URL, schema http(s)
  * tvg-chno duplicati, tvg-id mancanti o duplicati

Controlli sull'EPG (locale se presente, altrimenti asset della release):
  * gzip/XML validi, id canale duplicati
  * programmi orfani o riferiti a canali fuori playlist
  * copertura dei tvg-id e giorni disponibili

Esce con codice 1 se trova errori. Il riepilogo viene scritto anche nel
$GITHUB_STEP_SUMMARY, cosi' compare direttamente nella pagina del run.
"""

from __future__ import annotations

import gzip
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime
from pathlib import Path

PLAYLIST = Path("iptvitaplus.m3u")
OTHER_PLAYLISTS = [Path("ipradioita.m3u"), Path("iptvitapluto.m3u")]
LOCAL_EPG = Path("epg.xml.gz")
EPG_URL = "https://github.com/pasq96/IPTV-Italia/releases/download/epg/epg.xml.gz"
USER_AGENT = "IPTV-Italia-Validator/1.0"

MIN_COVERAGE = int(os.environ.get("MIN_COVERAGE", "60"))
MIN_DAYS = int(os.environ.get("MIN_DAYS", "3"))

TVG_ID_RE = re.compile(r'tvg-id="([^"]*)"')
TVG_CHNO_RE = re.compile(r'tvg-chno="([^"]*)"')

errors: list[str] = []
warnings: list[str] = []


def error(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def read_m3u(path: Path) -> list[dict[str, str]]:
    """Restituisce le entry della playlist e registra gli errori di sintassi."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    lines = path.read_text(encoding="utf-8").splitlines()

    if not lines or not lines[0].strip().startswith("#EXTM3U"):
        error(f"{path}: manca l'header #EXTM3U")

    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#EXTINF"):
            if current is not None:
                error(f"{path}:{number}: #EXTINF senza URL precedente")
            name = stripped.rsplit(",", 1)[-1].strip()
            id_match = TVG_ID_RE.search(stripped)
            chno_match = TVG_CHNO_RE.search(stripped)
            current = {
                "name": name,
                "id": id_match.group(1) if id_match else "",
                "chno": chno_match.group(1) if chno_match else "",
                "line": str(number),
            }
        elif stripped and not stripped.startswith("#"):
            if current is None:
                error(f"{path}:{number}: URL senza #EXTINF")
                continue
            if not re.match(r"^https?://", stripped):
                error(f"{path}:{number}: URL non http(s) ({current['name']})")
            current["url"] = stripped
            entries.append(current)
            current = None

    if current is not None:
        error(f"{path}: ultimo #EXTINF senza URL ({current['name']})")

    duplicate_chno = [c for c, n in Counter(e["chno"] for e in entries if e["chno"]).items() if n > 1]
    if duplicate_chno:
        error(f"{path}: tvg-chno duplicati: {', '.join(duplicate_chno)}")

    duplicate_ids = [i for i, n in Counter(e["id"] for e in entries if e["id"]).items() if n > 1]
    if duplicate_ids:
        warn(f"{path}: tvg-id condivisi da piu' canali: {', '.join(duplicate_ids)}")

    missing_ids = [e["name"] for e in entries if not e["id"]]
    if missing_ids and path == PLAYLIST:
        warn(f"{path}: canali senza tvg-id: {', '.join(missing_ids)}")
    return entries


def load_epg() -> tuple[bytes, str]:
    if LOCAL_EPG.exists():
        data, source = LOCAL_EPG.read_bytes(), "locale"
    else:
        request = urllib.request.Request(EPG_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response:
            data, source = response.read(), "release"
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data, source


def validate_epg(playlist_entries: list[dict[str, str]]) -> dict[str, object]:
    playlist_ids = {e["id"] for e in playlist_entries if e["id"]}
    try:
        data, source = load_epg()
    except (urllib.error.URLError, OSError) as exc:
        error(f"EPG non scaricabile da {EPG_URL}: {exc}")
        return {"source": "n/d", "channels": 0, "programmes": 0, "coverage": 0, "days": []}

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        error(f"EPG: XML non valido ({exc})")
        return {"source": source, "channels": 0, "programmes": 0, "coverage": 0, "days": []}

    if root.tag != "tv":
        error(f"EPG: radice inattesa <{root.tag}>")

    channel_ids = [channel.get("id", "") for channel in root.findall("channel")]
    duplicates = [c for c, n in Counter(channel_ids).items() if n > 1]
    if duplicates:
        error(f"EPG: id canale duplicati: {', '.join(duplicates)}")

    programme_ids = [p.get("channel", "") for p in root.findall("programme")]
    orphan = sorted(set(programme_ids) - set(channel_ids))
    if orphan:
        error(f"EPG: programmi riferiti a canali inesistenti: {', '.join(orphan)}")

    outside = sorted(set(channel_ids) - playlist_ids)
    if outside:
        error(f"EPG: canali non presenti nella playlist: {', '.join(outside)}")

    without_programmes = [c for c in channel_ids if c not in set(programme_ids)]
    if without_programmes:
        warn(f"EPG: canali senza programmi: {', '.join(without_programmes)}")

    days = sorted({p.get("start", "")[:8] for p in root.findall("programme") if p.get("start")})
    valid_days = []
    for day in days:
        try:
            valid_days.append(datetime.strptime(day, "%Y%m%d").date())
        except ValueError:
            error(f"EPG: data non valida '{day}'")

    today = date.today()
    if valid_days:
        if max(valid_days) < today:
            error("EPG: guida scaduta (nessun programma da oggi in poi)")
        elif (max(valid_days) - today).days < 1:
            warn("EPG: la guida copre meno di 2 giorni da oggi")
        if len(valid_days) < MIN_DAYS:
            error(f"EPG: solo {len(valid_days)} giorni di guida (minimo {MIN_DAYS})")
    else:
        error("EPG: nessun programma trovato")

    covered = playlist_ids & set(channel_ids)
    coverage = round(100 * len(covered) / len(playlist_ids)) if playlist_ids else 0
    if coverage < MIN_COVERAGE:
        error(f"EPG: copertura {coverage}% sotto la soglia minima {MIN_COVERAGE}%")

    missing = sorted(playlist_ids - set(channel_ids))
    return {
        "source": source,
        "channels": len(channel_ids),
        "programmes": len(programme_ids),
        "coverage": coverage,
        "covered": len(covered),
        "total": len(playlist_ids),
        "days": days,
        "missing": missing,
    }


def build_report(entries: list[dict[str, str]], epg: dict[str, object], others: dict[str, int]) -> str:
    lines = [
        "## Validazione playlist ed EPG",
        "",
        f"- **Playlist**: {len(entries)} canali, {len({e['id'] for e in entries if e['id']})} tvg-id",
        f"- **EPG** ({epg['source']}): {epg['channels']} canali, {epg['programmes']} programmi, "
        f"{len(epg['days'])} giorni"
        + (f" ({epg['days'][0]}\u2013{epg['days'][-1]})" if epg["days"] else ""),
        f"- **Copertura**: {epg.get('covered', 0)}/{epg.get('total', 0)} tvg-id ({epg['coverage']}%)",
    ]
    if others:
        lines.append("- **Altre playlist**: " + ", ".join(f"{k} ({v} canali)" for k, v in others.items()))
    lines.append("")
    if errors:
        lines.append(f"### ❌ Errori ({len(errors)})")
        lines.extend(f"- {e}" for e in errors)
        lines.append("")
    if warnings:
        lines.append(f"### ⚠️ Avvisi ({len(warnings)})")
        lines.extend(f"- {w}" for w in warnings)
        lines.append("")
    if not errors:
        lines.append("✅ Nessun errore bloccante.")
    return "\n".join(lines)


def main() -> int:
    entries = read_m3u(PLAYLIST)

    others: dict[str, int] = {}
    for path in OTHER_PLAYLISTS:
        if not path.exists():
            warn(f"{path}: file assente")
            continue
        others[path.name] = len(read_m3u(path))

    epg = validate_epg(entries)
    report = build_report(entries, epg, others)

    print(report)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(report + "\n")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
