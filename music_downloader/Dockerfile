ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
RUN \
  apk add --no-cache \
  python3 \
  py3-pip \
  ffmpeg \
  dos2unix

# Python 3 HTTP Server serves the current directory
WORKDIR /app

# Copy data for add-on
COPY app/requirements.txt /app/
RUN pip3 install -r requirements.txt --break-system-packages

COPY app /app
# Copy run.sh to ROOT /run.sh (Standard location)
COPY run.sh /run.sh

# Fix Windows line endings and permissions
RUN dos2unix /run.sh && chmod a+x /run.sh

CMD [ "/run.sh" ]
