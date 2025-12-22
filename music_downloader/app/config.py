import os
import json

# Add-on Options Path
OPTIONS_PATH = "/data/options.json"

def get_ha_option(key, default):
    """Retrieve option from Home Assistant configuration."""
    if os.path.exists(OPTIONS_PATH):
        try:
            with open(OPTIONS_PATH, 'r') as f:
                options = json.load(f)
                return options.get(key, default)
        except Exception as e:
            print(f"Error reading options.json: {e}")
    return default

# Base directory of the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# DETECT ENVIRONMENT
# If /data/options.json exists, we are likely in HA
IS_HA = os.path.exists(OPTIONS_PATH) or os.path.exists("/app/server.py")

# DIRECTORY SETTINGS
if IS_HA:
    # Read from Add-on Config
    DOWNLOAD_DIR = get_ha_option("download_dir", "/share/downloads/Music")
    OPENAI_API_KEY = get_ha_option("openai_api_key", "")
    
    # In Docker/Alpine, ffmpeg is installed via APK to /usr/bin/ffmpeg
    # We can rely on PATH or specify explicitly.
    FFMPEG_BIN = "ffmpeg" 
    FFPROBE_BIN = "ffprobe"
    BIN_DIR = "" # Not needed in PATH mode
else:
    # LOCAL WINDOWS MODE
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    BIN_DIR = os.path.join(BASE_DIR, "bin")
    FFMPEG_BIN = os.path.join(BIN_DIR, "ffmpeg.exe")
    FFPROBE_BIN = os.path.join(BIN_DIR, "ffprobe.exe")

# Ensure download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    try:
        os.makedirs(DOWNLOAD_DIR)
        print(f"Created download directory: {DOWNLOAD_DIR}")
    except Exception as e:
        print(f"Warning: Could not create download directory {DOWNLOAD_DIR}: {e}")
