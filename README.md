# 🎵 Home Assistant Music Downloader

[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.9+-yellow.svg)](https://www.python.org/)

Ein einfaches und leistungsstarkes Home Assistant Add-on, um Musik von YouTube (Official Artist Channels) in höchster Qualität herunterzuladen.

Die Lieder werden automatisch mit **Artist** (Kanalname) und **Titel** getaggt und direkt auf dein NAS oder einen lokalen Ordner gespeichert – perfekt für **Synology DS Audio**, Plex oder Jellyfin.

---

## ✨ Features

*   📺 **Oberfläche wie YouTube:** Ergebnisraster mit Vorschaubildern, Dauer, Kanal & Aufrufen, Watch-Seite mit eingebettetem Player – hell/dunkel automatisch.
*   🔎 **Live-Vorschläge:** Schon beim Tippen erscheinen passende Songs (Cover, Interpret, Album, Länge) aus Musikbibliotheken.
*   📚 **Automatischer Metadaten-Abgleich:** Titel, Interpreten, Album, Jahr, Genre, Track-Nr., ISRC und Album-Cover werden mit **MusicBrainz**, **iTunes** und **Deezer** abgeglichen (kostenlos, kein API-Key nötig).
*   ⏱️ **Längenvergleich:** Jedes Video zeigt, wie stark es von der Originallänge abweicht (✓ Original, +11 s, +1:12 …). Live-, Remix-, Sped-Up-, Karaoke- & Loop-Versionen werden markiert, die beste Übereinstimmung wird empfohlen.
*   🧹 **Filter:** Beste Übereinstimmung · Passende Länge · Offizielle Kanäle · Ohne Live/Remix.
*   ⬇️ **Download-Warteschlange:** Fortschrittsanzeige, mehrere Downloads parallel, Ein-Klick-Download direkt aus dem Raster, Hinweis bei bereits vorhandenen Dateien.
*   🎧 **High Quality:** **320 kbps MP3** mit echtem quadratischem Album-Cover (statt YouTube-Thumbnail) und vollständigen ID3-Tags.
*   📂 **Saubere Ordnerstruktur:** `Interpret/Album/Interpret - Titel.mp3` – perfekt für **Synology DS Audio**, Plex oder Jellyfin.
*   🤖 **Optional KI:** Mit OpenAI-Key wird der Videotitel zusätzlich per KI zerlegt, bevor die Bibliotheken abgefragt werden.

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
    Im Reiter *Konfiguration*:
    *   `download_dir` – Zielordner (Standard: `/media`).
    *   `metadata_country` – Ländercode für den iTunes-Abgleich (Standard: `DE`).
    *   `openai_api_key` – optional, für KI-gestützte Titelerkennung.

    *Stelle sicher, dass dein NAS in Home Assistant unter "Netzwerkspeicher" eingebunden ist, damit `/share` bzw. `/media` funktioniert.*

4.  **Starten:**
    Klicke auf *Starten* und aktiviere den Schalter **"In der Seitenleiste anzeigen"**.

---

## 🛠️ Nutzung

1.  Klicke in der linken Seitenleiste auf **Music Downloader**.
2.  Tippe einen Songnamen (z.B. "Eminem Not Afraid") – wähle einen Vorschlag aus der Liste, um ihn als **Referenz** festzulegen, oder drücke Enter.
3.  Die Ergebnisse zeigen oben die Referenz aus den Musikbibliotheken (inkl. Originallänge) und darunter alle Videos mit Abweichungs-Badge.
4.  Klicke ein Video an: Player, Längenvergleich und die automatisch befüllten Metadaten erscheinen. Bei Bedarf einen anderen Bibliothekstreffer übernehmen oder Felder anpassen.
5.  **Herunterladen** – Fortschritt siehst du oben rechts im Download-Menü. 🎶

**Tastenkürzel:** `/` fokussiert die Suche, `↑`/`↓` wählen Vorschläge, `Esc` schließt Menüs bzw. die Videoansicht.

---

## ⚙️ Tech Stack

*   **Python 3** & **Flask** (Backend)
*   **yt-dlp** (Download-Engine)
*   **FFmpeg** (Konvertierung)
*   **Mutagen** (ID3 Tagging)
*   **MusicBrainz / iTunes Search / Deezer API** (Metadaten-Abgleich)
*   **Alpine Linux** (Docker Base)

---

**Lizenz:** MIT
*Made with ❤️ for Home Assistant*
