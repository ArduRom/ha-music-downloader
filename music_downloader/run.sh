#!/bin/bash

echo "Starting Music Downloader Add-on (v1.1.4)..."

# Note: Config layout is handled by Python's config.py reading /data/options.json
# We don't need bashio here, which avoids the s6-overlay-suexec PID 1 error in some cases.

cd /app
echo "Starting Flask Server..."
python3 server.py
