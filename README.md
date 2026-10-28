<p align="center">
  <img src="https://github.com/pasq96/IPTV-Italia/actions/workflows/build-epg.yml/badge.svg" alt="EPG Build">
  <img src="https://github.com/pasq96/IPTV-Italia/actions/workflows/validate.yml/badge.svg" alt="Validate">
  <img src="https://img.shields.io/badge/Update-Every_day-blue?style=flat&logo=githubactions&logoColor=white" alt="Update Schedule">
  <img src="https://img.shields.io/github/repo-size/pasq96/IPTV-Italia?color=success" alt="Repo Size">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
</p>

# 🇮🇹 IPTV Italia - Playlist M3U con EPG nativo

## Descrizione

Playlist IPTV per canali italiani con guida TV **unita e generata ogni giorno** (epgitalia + open-epg), pubblicata come asset di release e caricata nativamente dall'header della playlist. Nessun commit automatico: la cronologia del repository resta pulita.

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

Il merge tiene solo i canali presenti nella playlist e riscrive gli id sui rispettivi `tvg-id`, così una sola sorgente EPG copre tutti i canali che hanno palinsesto disponibile. I tre feed di **Mediaset Italia** (America, Australia e Asia, Europa e Africa) hanno `tvg-id` distinti e quindi una guida separata.

Attualmente **67 canali su 82** ricevono la guida. Restano senza EPG, perché nessuna sorgente li pubblica: `BOM Channel`, `Radio Ibiza TV`, `Camera dei Deputati`, `Radio Kiss Kiss TV`, `RTL 102.5 Napulè`, `Radio24`, `Radio Zeta`, `Radio Capital TV`, `M2O TV`, `Radio TV Serie A` e i feed `Rai Italia` (Asia e Australia, Europa e Africa, Sud America, World Premium).

Il workflow può essere lanciato a mano con l'opzione **strip_desc** per generare un EPG senza descrizioni dei programmi (~147 KB invece di ~356 KB).

---

## 📻 Altre playlist

| File | Contenuto | Note |
|---|---|---|
| [`ipradioita.m3u`](./ipradioita.m3u) | canali radio italiani | non aggiornata automaticamente, senza EPG |
| [`iptvitapluto.m3u`](./iptvitapluto.m3u) | canali Pluto TV | non aggiornata automaticamente, senza EPG |

Entrambe vengono comunque controllate a livello di sintassi dal workflow di validazione.

---

## 🚀 Caratteristiche Principali

- **EPG nativo**: la playlist punta a un unico file aggiornato ogni giorno e pubblicato come asset di release.
- **Nessun commit automatico**: né l'EPG né i controlli degli stream scrivono nella storia del repository.
- **Token Sky a lunga scadenza**: i link di TV8, Cielo e Sky TG24 sono validi fino a dicembre 2027.
- **Validazione automatica**: playlist ed EPG controllati a ogni push e pull request (sintassi, id orfani, copertura, giorni disponibili).
- **Report mensile**: una sola issue aggiornata con i canali offline, senza notifiche ripetute.
- **Health check on demand**: workflow manuale con `ffprobe` e report allegato al run.

---

## ⚙️ Come Funziona l'Automazione

1. **Build Merged EPG** parte ogni giorno alle 04:30 UTC (06:30 italiane) e a ogni modifica di script o playlist.
2. Genera `epg.xml.gz` e lo **sovrascrive come asset della release `epg`**: l'URL resta stabile e il riepilogo di copertura finisce nel run.
3. **Validate Playlist and EPG** controlla a ogni push/PR che playlist ed EPG siano coerenti; non modifica nulla.
4. **Monthly Stream Report** gira il primo di ogni mese, verifica i flussi e apre/aggiorna **una sola** issue con i canali offline (la chiude quando sono tutti online).
5. **Stream Health Check** resta disponibile a mano dalla tab Actions, con il report allegato come artifact.

---

## 📄 Licenza e disclaimer

Il codice di questo repository è distribuito con licenza [MIT](./LICENSE).

I flussi, i loghi e i palinsesti appartengono ai rispettivi titolari: il repository **non ospita alcun contenuto**, si limita a raccogliere link pubblicamente disponibili. Non c'è alcuna garanzia di funzionamento o di legalità della fruizione nel tuo paese: verifica le condizioni dei singoli fornitori.
