FROM python:3.9-alpine

# Install system dependencies
RUN apk add --no-cache ffmpeg git dos2unix build-base python3-dev

WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# correct path: requirements.txt is inside app/ folder in the repo
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (including config.py and server.py which are in app/)
COPY app/ .

# Expose port (Internal for Ingress)
EXPOSE 8099

# Start command
CMD ["python3", "-u", "server.py"]
