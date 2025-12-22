# Anleitung: Musik Downloader als GitHub Repository installieren

Da du das Add-on lieber als GitHub Repository installieren möchtest (statt Samba), sind hier die Schritte.

## 1. GitHub Repository erstellen
1. Logge dich bei **GitHub.com** ein.
2. Erstelle ein **Neues Repository** (z.B. Name: `ha-music-downloader`).
   - Wähle "Private" oder "Public" (Public ist einfacher für HA, Private erfordert SSH-Keys in HA, aber Public ist ok, wenn keine Passwörter in den Dateien sind).
   - **Wichtig**: Initialisiere es *nicht* mit README/gitignore, damit wir den Code hier einfach hochladen können.

## 2. Code hochladen (Von diesem PC)
Öffne eine Konsole (CMD/PowerShell) in diesem Ordner (`e:\Programme\Python\Musik_downloader`).

Gib folgende Befehle ein (ersetze `<DEIN_USER>` und `<REPO>` entsprechend):

```powershell
# Git initialisieren
git init

# Alle Dateien hinzufügen
git add .

# Ersten Commit machen
git commit -m "Initial Music Downloader Addon"

# Mit deinem neuen GitHub Repo verknüpfen
git remote add origin https://github.com/<DEIN_USER>/ha-music-downloader.git

# Hochladen
git push -u origin master
```

## 3. In Home Assistant installieren
1. Gehe in Home Assistant zu **Einstellungen** -> **Add-ons** -> **Add-on Store**.
2. Klicke oben rechts auf die **drei Punkte** -> **Repositorys**.
3. Füge die URL deines Repositories hinzu (z.B. `https://github.com/<DEIN_USER>/ha-music-downloader`).
4. Klicke Hinzufügen.
5. Lade die Seite neu (oder klicke "Updates prüfen").
6. Scrolle nach unten: Du solltest nun **"Youtube Music Downloader"** sehen.
7. Klicke auf Installieren.

## 4. Konfiguration & Start
1. Im Tab **Konfiguration**:
   - `download_dir`: Stelle sicher, dass der Pfad stimmt (z.B. `/share/Music`).
   - *Hinweis*: Damit `/share` funktioniert, muss dein NAS in HA gemountet sein oder du nutzt den Standard HA Share.
2. Starte das Add-on.
3. Klicke auf **Web-Oberfläche öffnen**.
4. Gib einen Songtitel ein (z.B. "Eminem - Not Afraid") -> Klicke "Search" -> "Download".

Fertig!
