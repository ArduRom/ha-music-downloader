FROM python:3.9-alpine

# Install system dependencies
# ffmpeg: required for audio conversation
# git: required for pip installing from git
# dos2unix: helpful for script line endings
RUN apk add --no-cache ffmpeg git dos2unix

WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# correct path: requirements.txt is inside app/ folder
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Expose port (Internal for Ingress)
EXPOSE 8099

# Start command (Direct Python execution for signal handling)
CMD ["python3", "-u", "server.py"]
