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
#EXTM3U x-tvg-url="https://raw.githubusercontent.com/pasq96/IPTV-Italia/refs/heads/main/epg.xml.gz"
```

quindi i player compatibili (TiviMate, OTT Navigator, IPTV Smarters, …) scaricano l'EPG **automaticamente**, senza configurazioni manuali. Se il tuo player non legge l'header, aggiungi come unica sorgente EPG:

```
https://raw.githubusercontent.com/pasq96/IPTV-Italia/refs/heads/main/epg.xml.gz
```

### Come viene generato

Il file `epg.xml.gz` è prodotto ogni giorno dal workflow [Build Merged EPG](./.github/workflows/build-epg.yml) tramite `scripts/build_epg.py`, che unisce:

| Sorgente | Contenuto |
|---|---|
| [epgitalia.tv](https://www.epgitalia.tv) (`/gzip`) | guida completa dei canali nazionali (Rai, Mediaset, Sky, Warner…) |
| [open-epg.com](https://www.open-epg.com) (`italy9.xml.gz`) | palinsesti Warner/Discovery e radio TV assenti in epgitalia |

Il merge tiene solo i canali presenti nella playlist e riscrive gli id sui rispettivi `tvg-id`, così una sola sorgente EPG copre tutti i canali che hanno palinsesto disponibile. Attualmente **59 canali su 76** ricevono la guida; restano senza EPG (nessuna delle due sorgenti li pubblica): `QVC`, `Donna TV`, `Radio 105 TV`, `BOM Channel`, `Radio Ibiza TV`, `Camera dei Deputati`, `Radio Kiss Kiss TV`, `Rai 4K`, `RTL 102.5 Napulè`, `Radio24`, `RDS Social TV`, `Radio Zeta`, `Radio Capital TV`, `M2O TV`, `Rai Italia`, `Mediaset Italia`, `Radio TV Serie A`.

---

## 🚀 Caratteristiche Principali

- **Refresh Dinamico dei Token**: Estrazione automatica dei token aggiornati per i canali protetti (TV8, Cielo, Sky TG24) tramite logiche dedicate per prevenire blocchi.
- **Health Check Parallelo**: Esecuzione rapida tramite `ffprobe` e thread pool multipli per testare la stabilità di tutti i flussi in pochi secondi.
- **Report di Stato in Tempo Reale**: Monitoraggio dettagliato dello stato dei canali consultabile nel file [status.json](./status.json), con flag espliciti per i token rigenerati (`token_refreshed`).

---

## ⚙️ Come Funziona l'Automazione

1. Il workflow di GitHub Actions si avvia automaticamente **ogni 12 ore** (o a ogni modifica manuale della playlist).
2. I flussi vengono validati in background filtrando quelli offline o non disponibili.
3. I link con token scaduti vengono aggiornati al volo e il file `iptvitaplus.m3u` viene salvato in autonomia sul branch `main`.
