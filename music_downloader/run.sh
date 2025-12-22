#!/usr/bin/with-contenv bashio

echo "Starting Music Downloader Add-on..."

# Check config
DOWNLOAD_PATH=$(bashio::config 'download_dir')

echo "Download directory configured as: $DOWNLOAD_PATH"

# Start the Flask App
echo "Starting Flask Server..."
python3 server.py
