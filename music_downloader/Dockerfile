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

# Directly start Python. 
# Since init: false is set in config.yaml, this will be PID 1.
CMD [ "python3", "-u", "server.py" ]
