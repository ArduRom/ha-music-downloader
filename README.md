# YouTube Music Downloader for Home Assistant

This Add-on helps you download high-quality MP3s from YouTube (Artist Channels) directly to your NAS/Home Assistant.

## Installation

### Method 1: Local Add-on (Easiest for testing)
1.  Access your Home Assistant configuration folder (e.g. via Samba Share or VS Code Add-on).
2.  Navigate to the `addons` folder. If it doesn't exist, create it.
3.  Create a new folder inside `addons` named `music_downloader`.
4.  Copy **all files** from this directory (`config.yaml`, `Dockerfile`, `*.py`, `run.sh`, etc.) into that new `addons/music_downloader` folder.
5.  Restart Home Assistant (Settings -> System -> Restart).
6.  Go to **Settings** -> **Add-ons** -> **Add-on Store**.
7.  Click the **Refresh** button (top right menu seems hidden sometimes, try "Check for updates").
8.  You should see "Youtube Music Downloader" under "Local Add-ons".
9.  Click **Install**.

### Method 2: GitHub Repository
(Requires pushing this code to a minimal GitHub Repo).

## Configuration
After installation, go to the **Configuration** tab of the Add-on.
- **download_dir**: Path where files should be saved.
  - Default: `/share/downloads/Music`
  - Note: Ensure your NAS drive is mounted to `/share` or `/media` in Home Assistant.

## Usage
1.  Start the Add-on.
2.  Click **Open Web UI** (or go to `http://homeassistant:5000`).
3.  Paste a YouTube Link.
4.  Click Download.
5.  Check the configured folder for your MP3s.

## Home Assistant Dashboard Integration
To add this to your dashboard:
1.  Edit Dashboard.
2.  Add Card -> **Webpage**.
3.  URL: `http://YOUR_HA_IP:5000` (or the Ingress URL if supported later, currently direct port access).
