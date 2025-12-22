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

# Copy data for add-on (requirements first for cache)
COPY app/requirements.txt /app/
RUN pip3 install -r requirements.txt --break-system-packages

COPY app /app
COPY run.sh /app/run.sh

# Make run script executable
RUN chmod a+x /app/run.sh

CMD [ "/app/run.sh" ]
