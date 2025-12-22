#!/usr/bin/with-contenv bashio

echo "Starting Music Downloader Add-on (v1.1.2)..."

DOWNLOAD_PATH=$(bashio::config 'download_dir')
echo "Download directory configured as: $DOWNLOAD_PATH"

# Ensure /app is working dir
cd /app

echo "Starting Flask Server..."
python3 server.py
