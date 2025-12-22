# 🎵 Home Assistant Music Downloader

[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.9+-yellow.svg)](https://www.python.org/)

Ein einfaches und leistungsstarkes Home Assistant Add-on, um Musik von YouTube (Official Artist Channels) in höchster Qualität herunterzuladen.

Die Lieder werden automatisch mit **Artist** (Kanalname) und **Titel** getaggt und direkt auf dein NAS oder einen lokalen Ordner gespeichert – perfekt für **Synology DS Audio**, Plex oder Jellyfin.

---

## ✨ Features

*   🔎 **Integrierte Suche:** Suche direkt im Add-on nach Titeln (kein Copy-Paste von URLs nötig).
*   🎧 **High Quality:** Lädt Audio in **320kbps MP3** herunter.
*   🏷️ **Auto-Tagging:** Automatische ID3-Tags (Artist & Title) und Cover-Art (Thumbnail).
*   📱 **Responsive UI:** Funktioniert nahtlos in der Home Assistant App (Ingress / Seitenleiste).
*   📂 **NAS Support:** Speichert direkt in `/share/downloads` (konfigurierbar).

---

## 🚀 Installation

1.  **Repository hinzufügen:**
    Gehe in Home Assistant zu **Einstellungen** -> **Add-ons** -> **Add-on Store** -> **(...) Drei Punkte** -> **Repositorys**.
    Füge folgende URL hinzu:
    ```text
    https://github.com/ArduRom/ha-music-downloader
    ```

2.  **Add-on installieren:**
    Lade den Store neu, suche nach **"Youtube Music Downloader"** und klicke auf *Installieren*.

3.  **Konfiguration (Optional):**
    Im Reiter *Konfiguration* kannst du den Zielordner anpassen (Standard: `/share/downloads/Music`).
    *Stelle sicher, dass dein NAS in Home Assistant unter "Netzwerkspeicher" eingebunden ist, damit `/share` funktioniert.*

4.  **Starten:**
    Klicke auf *Starten* und aktiviere den Schalter **"In der Seitenleiste anzeigen"**.

---

## 🛠️ Nutzung

1.  Klicke in der linke Seitenleiste auf **Music Downloader**.
2.  Gib einen Suchbegriff ein (z.B. "Eminem Not Afraid").
3.  Das Add-on zeigt dir das beste Ergebnis mit Cover an.
4.  Klicke auf **Download Selection**.
5.  Nach wenigen Sekunden liegt die MP3 fertig getaggt in deinem Ordner! 🎶

---

## ⚙️ Tech Stack

*   **Python 3** & **Flask** (Backend)
*   **yt-dlp** (Download-Engine)
*   **FFmpeg** (Konvertierung)
*   **Mutagen** (ID3 Tagging)
*   **Alpine Linux** (Docker Base)

---

**Lizenz:** MIT
*Made with ❤️ for Home Assistant*
