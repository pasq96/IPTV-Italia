#!/usr/bin/env python3
"""Genera l'EPG unito usato da iptvitaplus.m3u.

Sorgenti:
  * epgitalia.tv  -> guida completa per la maggior parte dei canali italiani
  * open-epg.com  -> palinsesti Warner/Discovery, radio TV e canali minori
                     assenti in epgitalia (italy9, italy3, italy2)

Il file prodotto (epg.xml.gz) contiene solo i canali presenti nella playlist,
con gli id riscritti sui tvg-id della playlist stessa, cosi' il player deve
caricare una sola sorgente EPG.
"""

from __future__ import annotations

import gzip
import io
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

# Sorgenti primarie, in ordine di priorita'. Si usa la prima raggiungibile:
# epgitalia ha piu' volte cambiato/spento gli endpoint, quindi il fallback
# /guidexz evita che un 404 blocchi l'intera build.
PRIMARY_SOURCES = [
    ("epgitalia /gzip", "https://www.epgitalia.tv/gzip", "epgitalia.xml.gz"),
    ("epgitalia /guidexz", "https://www.epgitalia.tv/guidexz", "epgitalia.xml.7z"),
]

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT = 180

# Sorgenti di fallback, in ordine di priorita': la prima che ha programmi
# per un canale scoperto vince.
FALLBACK_SOURCES = [
    ("italy9", "https://www.open-epg.com/files/italy9.xml.gz", "openepg-italy9.xml.gz"),
    ("italy3", "https://www.open-epg.com/files/italy3.xml.gz", "openepg-italy3.xml.gz"),
    ("italy2", "https://www.open-epg.com/files/italy2.xml.gz", "openepg-italy2.xml.gz"),
]

USER_AGENT = "IPTV-Italia-EPG-Builder/1.0 (+https://github.com/pasq96/IPTV-Italia)"

PLAYLIST = Path("iptvitaplus.m3u")
OUTPUT = Path("epg.xml.gz")
CACHE_DIR = Path(".epg-cache")

# EPG_STRIP_DESC=1 rimuove le <desc> dei programmi: file molto piu' leggero.
STRIP_DESC = os.environ.get("EPG_STRIP_DESC", "").strip().lower() in {"1", "true", "yes", "on"}

# tvg-id playlist -> id canale nella sorgente di fallback.
# Servono solo per i canali che epgitalia non copre (0 programmi) e per
# evitare abbinamenti ambigui.
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
    # recuperati da italy3
    "QVC": "QVC.it",
    "DonnaTV.it": "DonnaTv.it",
    "Radio.105.it": "Radio 105.it",
    # recuperati da italy2
    "Rai4K.it": "Rai 4K.it",
    "RDSSocialTV.it": "Rds Social Tv.it",
    # Mediaset Italia: tre feed distinti, con tvg-id dedicati nella playlist
    "Mediaset.Italia.-.America.it": "Mediaset.Italia.-.America.it",
    "Mediaset.Italia.-.Australia.e.Asia.it": "Mediaset.Italia.-.Australia.e.Asia.it",
    "Mediaset.Italia.-.Europa.e.Africa.it": "Mediaset.Italia.-.Europa.e.Africa.it",
}

CHANNEL_RE = re.compile(r'<channel\s+id="([^"]+)"')
PROGRAMME_RE = re.compile(r'<programme\b[^>]*\bchannel="([^"]+)"')
DISPLAY_RE = re.compile(r"<display-name[^>]*>([^<]*)</display-name>")
TVG_ID_RE = re.compile(r'tvg-id="([^"]*)"')
DESC_RE = re.compile(r"<desc\b[^>]*>.*?</desc>\s*", re.S)


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
    last_error: Exception | None = None

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        suffix = f" (tentativo {attempt}/{DOWNLOAD_ATTEMPTS})" if attempt > 1 else ""
        log(f"[download] {url}{suffix}")
        try:
            with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response, target.open("wb") as out:
                shutil.copyfileobj(response, out)
            log(f"[download] {target} ({target.stat().st_size / 1024 / 1024:.1f} MB)")
            return target
        except Exception as exc:  # noqa: BLE001 - si ritenta solo su errori transitori
            last_error = exc
            target.unlink(missing_ok=True)
            permanent = (
                isinstance(exc, urllib.error.HTTPError)
                and 400 <= exc.code < 500
                and exc.code != 429
            )
            if permanent:
                log(f"[warn] download fallito: {exc} (errore definitivo, nessun retry)")
                break
            if attempt < DOWNLOAD_ATTEMPTS:
                delay = 2 ** (attempt - 1)
                log(f"[warn] download fallito: {exc}; nuovo tentativo tra {delay}s")
                time.sleep(delay)

    assert last_error is not None
    raise last_error


def download_primary() -> tuple[Path, str]:
    """Scarica la prima sorgente primaria disponibile (gzip -> guidexz)."""
    errors: list[str] = []
    for label, url, filename in PRIMARY_SOURCES:
        try:
            return download(url, filename), label
        except Exception as exc:  # noqa: BLE001 - si prova la sorgente successiva
            log(f"[warn] sorgente primaria {label} non disponibile: {exc}")
            errors.append(f"{label}: {exc}")
    raise RuntimeError("; ".join(errors))


def extract_7z(path: Path) -> Path:
    """Estrae un archivio 7z (usato da epgitalia /guidexz) e ritorna l'XML."""
    destination = CACHE_DIR / f"{path.name}.d"
    destination.mkdir(parents=True, exist_ok=True)
    xml_path = destination / "guide.xml"
    marker = destination / ".extracted"

    if xml_path.exists() and marker.exists() and marker.stat().st_mtime >= path.stat().st_mtime:
        return xml_path

    log(f"[estrai] {path} -> {destination}")
    try:
        import py7zr  # type: ignore[import-not-found]

        with py7zr.SevenZipFile(path, mode="r") as archive:
            archive.extract(path=destination)
    except ImportError:
        sevenzip = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
        if not sevenzip:
            raise RuntimeError(
                "archivio 7z da estrarre ma nessun estrattore disponibile "
                "(installare p7zip-full oppure 'pip install py7zr')"
            )
        result = subprocess.run(
            [sevenzip, "x", "-y", f"-o{destination}", str(path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"estrazione 7z fallita: {detail}")

    if not xml_path.exists():
        candidates = sorted(destination.rglob("*.xml"))
        if not candidates:
            raise RuntimeError(f"nessun file XML trovato in {path}")
        xml_path = candidates[0]

    marker.touch()
    return xml_path


def open_xml(path: Path):
    with path.open("rb") as handle:
        magic = handle.read(6)

    if magic[:2] == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8-sig", errors="replace")
    if magic == b"7z\xbc\xaf\x27\x1c":
        return extract_7z(path).open("rt", encoding="utf-8-sig", errors="replace")
    if magic == b"\xfd7zXZ\x00":
        import lzma

        return lzma.open(path, "rt", encoding="utf-8-sig", errors="replace")
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

    def clean(text: str) -> str:
        return DESC_RE.sub("", text) if STRIP_DESC else text

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
                programmes.append(clean(first + "".join(programme_buffer[1:])))
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
                        clean(line.replace(f'channel="{source}"', f'channel="{wanted[source]}"', 1))
                    )
                else:
                    programme_buffer = [line]
                    skipping_programme = source
            continue

    return channels, programmes


def pick_fallback_id(tvg_id: str, counts: dict[str, int], names: dict[str, set[str]]) -> str | None:
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

    try:
        primary_path, primary_label = download_primary()
    except Exception as exc:  # noqa: BLE001 - nessuna sorgente primaria raggiungibile
        log(f"[errore] nessuna sorgente primaria disponibile: {exc}")
        return 1

    primary_counts, primary_names = index_source(primary_path)
    log(f"[{primary_label}] {sum(primary_counts.values())} programmi, {len(primary_counts)} canali")

    # I fallback servono solo per i canali che la sorgente primaria non copre:
    # se non ne mancano, evitiamo download e parsing inutili.
    uncovered = [tvg_id for tvg_id in ids if primary_counts.get(tvg_id, 0) <= 0]

    fallbacks: list[dict] = []
    if uncovered:
        for label, url, filename in FALLBACK_SOURCES:
            try:
                path = download(url, filename)
            except Exception as exc:  # noqa: BLE001 - le sorgenti di fallback sono opzionali
                log(f"[warn] sorgente {label} non disponibile: {exc}")
                continue
            counts, names = index_source(path)
            log(f"[{label}] {sum(counts.values())} programmi, {len(counts)} canali")
            fallbacks.append(
                {"label": label, "path": path, "counts": counts, "names": names, "wanted": {}}
            )
    else:
        log("[fallback] non necessari: la sorgente primaria copre tutti i tvg-id")

    primary_wanted: dict[str, str] = {}
    source_of: dict[str, str] = {}

    for tvg_id in ids:
        if primary_counts.get(tvg_id, 0) > 0:
            primary_wanted[tvg_id] = tvg_id
            source_of[tvg_id] = primary_label
            continue
        for source in fallbacks:
            fallback_id = pick_fallback_id(tvg_id, source["counts"], source["names"])
            if fallback_id:
                source["wanted"][fallback_id] = tvg_id
                source_of[tvg_id] = f"{source['label']}:{fallback_id}"
                break

    channels: list[str] = []
    programmes: list[str] = []
    if primary_wanted:
        ch, pr = collect(primary_path, primary_wanted)
        channels.extend(ch)
        programmes.extend(pr)
    for source in fallbacks:
        if not source["wanted"]:
            continue
        ch, pr = collect(source["path"], source["wanted"])
        channels.extend(ch)
        programmes.extend(pr)

    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<tv generator-info-name="IPTV-Italia merged EPG" '
        'generator-info-url="https://github.com/pasq96/IPTV-Italia">\n'
    )
    with OUTPUT.open("wb") as raw, gzip.GzipFile(
        fileobj=raw, mode="wb", compresslevel=9, mtime=0
    ) as gz, io.TextIOWrapper(gz, encoding="utf-8", newline="\n") as out:
        out.write(header)
        out.writelines(channels)
        out.writelines(programmes)
        out.write("</tv>\n")

    used = sorted(tvg_id for tvg_id in ids if tvg_id in source_of)
    missing = [tvg_id for tvg_id in ids if tvg_id not in source_of]

    log("")
    log(f"[output] {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB)")
    log(f"[output] {len(channels)} canali, {len(programmes)} programmi")
    log(f"[output] descrizioni: {'rimosse' if STRIP_DESC else 'incluse'}")
    log(f"[copertura] {len(used)}/{len(ids)} tvg-id con EPG")
    if missing:
        log(f"[senza EPG] {len(missing)}: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(build())
