<p align="center">
  <img src="https://github.com/pasq96/IPTV-Italia/actions/workflows/check-stream.yml/badge.svg" alt="CI Status">
  <img src="https://img.shields.io/badge/Update-Every_12h-blue?style=flat&logo=githubactions&logoColor=white" alt="Update Schedule">
  <img src="https://img.shields.io/github/repo-size/pasq96/IPTV-Italia?color=success" alt="Repo Size">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/github/repo-size/pasq96/IPTV-Italia" alt="Repository size")
</p>



# 🇮🇹 IPTV Italia - Playlist M3U con Automazione CI/CD

## Descrizione

Playlist IPTV per canali italiani, potenziata da un sistema di controllo automatico tramite GitHub Actions che verifica la salute dei flussi ed esegue il refresh dinamico dei token di streaming (Sky, TV8, Cielo, ecc.).

> Forked by [IPTV-Italia](https://github.com/Tundrak/IPTV-Italia) (grazie Tundrak)  

---

## 📌 Link per Player (URL Raw)

Copia il link sottostante e incollalo nel tuo player IPTV preferito (es. TiviMate, VLC, GSE Smart IPTV):

https://raw.githubusercontent.com/pasq96/IPTV-Italia/refs/heads/main/iptvitaplus.m3u

---

## 📅 Guida TV (EPG)

Per un'esperienza ottimale con i palinsesti, consiglio l'utilizzo degli EPG messi a disposizione da [epgitalia.tv](https://epgitalia.tv).

---

## 🚀 Caratteristiche Principali

- Refresh Dinamico dei Token: Estrazione automatica dei token aggiornati per i canali protetti (TV8, Cielo, Sky TG24) tramite API dedicate per evitare blocchi.
- Health Check Automatizzato: Esecuzione tramite ffprobe e worker paralleli ogni 12 ore per filtrare i flussi offline o non disponibili.
- Report di Stato in Tempo Reale: Monitoraggio dettagliato dello stato dei canali consultabile nel file status.json.

---

## ⚙️ Come Funziona l'Automazione

1. Il workflow di GitHub Actions si avvia automaticamente ogni 12 ore (o a ogni modifica manuale della playlist).
2. I flussi vengono testati per verificarne la stabilità.
3. I link con token scaduti vengono rigenerati al volo e il file iptvitaplus.m3u viene aggiornato in autonomia sul branch main.
