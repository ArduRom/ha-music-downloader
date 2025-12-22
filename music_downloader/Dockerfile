ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
RUN \
  apk add --no-cache \
  python3 \
  py3-pip \
  ffmpeg

# Python 3 HTTP Server serves the current directory
WORKDIR /app

# Copy data for add-on
COPY app/requirements.txt /app/
RUN pip3 install -r requirements.txt --break-system-packages

COPY app /app

# NUCLEAR OPTION: Create run.sh inside Docker to guarantee LF line endings
# This avoids any Windows/Git CRLF issues completely.
RUN echo '#!/bin/bash' > /run.sh && \
  echo 'echo "Starting Music Downloader (v1.1.6 - Generated)..."' >> /run.sh && \
  echo 'cd /app' >> /run.sh && \
  echo 'python3 server.py' >> /run.sh && \
  chmod a+x /run.sh

CMD [ "/run.sh" ]
