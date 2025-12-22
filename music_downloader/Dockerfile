FROM python:3.9-slim

# Install system dependencies (Debian based now)
# ffmpeg: audio conversion
# git: required for some pip packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .
COPY config.py .

# Expose port (Internal for Ingress)
EXPOSE 8099

# Start command
CMD ["python3", "-u", "server.py"]
