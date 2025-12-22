#!/usr/bin/with-contenv bashio

echo "Starting Music Downloader..."

# Check config (optional, bashio allows reading options easily)
DOWNLOAD_PATH=$(bashio::config 'download_dir')

echo "Download directory configured as: $DOWNLOAD_PATH"
echo "Ensure this path exists in /share or /media..."

# Start the Flask App
echo "Starting Flask Server..."
python3 server.py
