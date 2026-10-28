<p align="center">
  <img src="https://github.com/pasq96/IPTV-Italia/actions/workflows/check-stream.yml/badge.svg" alt="CI Status">
  <img src="https://img.shields.io/badge/Update-Every_12h-blue?style=flat&logo=githubactions&logoColor=white" alt="Update Schedule">
  <img src="https://img.shields.io/github/repo-size/pasq96/IPTV-Italia?color=success" alt="Repo Size">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
</p>

# 🇮🇹 IPTV Italia - Playlist M3U con Automazione CI/CD

## Descrizione

Playlist IPTV per canali italiani, potenziata da un sistema di controllo automatico tramite GitHub Actions che verifica la salute dei flussi ed esegue il refresh dinamico dei token di streaming (Sky, TV8, Cielo, ecc.).

> Forked from [Tundrak/IPTV-Italia](https://github.com/Tundrak/IPTV-Italia) (grazie Tundrak)  

---

## 📌 Link per Player (URL Raw)

Copia il link sottostante e incollalo nel tuo player IPTV preferito (es. TiviMate, VLC, GSE Smart IPTV):

https://raw.githubusercontent.com/pasq96/IPTV-Italia/refs/heads/main/iptvitaplus.m3u

---

## 📅 Guida TV (EPG)

La playlist include già la guida TV: l'header contiene

```
#EXTM3U x-tvg-url="https://github.com/pasq96/IPTV-Italia/releases/download/epg/epg.xml.gz"
```

quindi i player compatibili (TiviMate, OTT Navigator, IPTV Smarters, …) scaricano l'EPG **automaticamente**, senza configurazioni manuali. Se il tuo player non legge l'header, aggiungi come unica sorgente EPG:

```
https://github.com/pasq96/IPTV-Italia/releases/download/epg/epg.xml.gz
```

### Come viene generato

Il file `epg.xml.gz` è prodotto ogni giorno dal workflow [Build Merged EPG](./.github/workflows/build-epg.yml) tramite `scripts/build_epg.py` e pubblicato come **asset della release `epg`**: viene sovrascritto a ogni esecuzione, quindi l'aggiornamento non genera commit nel repository. Lo script unisce:

| Sorgente | Contenuto |
|---|---|
| [epgitalia.tv](https://www.epgitalia.tv) (`/gzip`) | guida completa dei canali nazionali (Rai, Mediaset, Sky, Warner…) |
| [open-epg.com](https://www.open-epg.com) (`italy9.xml.gz`) | palinsesti Warner/Discovery e radio TV assenti in epgitalia |
| [open-epg.com](https://www.open-epg.com) (`italy3.xml.gz`) | fallback per QVC, Donna TV, Radio 105 TV |
| [open-epg.com](https://www.open-epg.com) (`italy2.xml.gz`) | fallback per Rai 4K, RDS Social TV |

Il merge tiene solo i canali presenti nella playlist e riscrive gli id sui rispettivi `tvg-id`, così una sola sorgente EPG copre tutti i canali che hanno palinsesto disponibile. I tre feed di **Mediaset Italia** (America, Australia e Asia, Europa e Africa) hanno `tvg-id` distinti e quindi una guida separata. Attualmente **67 canali su 78** ricevono la guida; restano senza EPG (nessuna sorgente li pubblica): `BOM Channel`, `Radio Ibiza TV`, `Camera dei Deputati`, `Radio Kiss Kiss TV`, `RTL 102.5 Napulè`, `Radio24`, `Radio Zeta`, `Radio Capital TV`, `M2O TV`, `Rai Italia`, `Radio TV Serie A`.

---

## 🚀 Caratteristiche Principali

- **EPG nativo**: la playlist punta a un unico file EPG aggiornato ogni giorno (epgitalia + open-epg) e pubblicato come asset di release.
- **Nessun commit automatico**: né l'EPG né i controlli degli stream scrivono nella storia del repository.
- **Token Sky a lunga scadenza**: i link di TV8, Cielo e Sky TG24 sono validi fino a dicembre 2027.
- **Health check on demand**: il workflow manuale *Stream Health Check* testa i flussi con `ffprobe` e allega `status.json` al run, senza toccare il repository.

---

## ⚙️ Come Funziona l'Automazione

1. **Build Merged EPG** parte ogni giorno alle 04:30 UTC (06:30 italiane) e a ogni modifica di script o playlist.
2. Genera `epg.xml.gz` e lo **sovrascrive come asset della release `epg`**: l'URL resta stabile, la cronologia del repo non cresce.
3. Il controllo degli stream non è più schedulato: si avvia a mano dalla tab **Actions** e produce solo artifact.
