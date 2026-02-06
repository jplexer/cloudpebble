FROM python:2.7
MAINTAINER Katharine Berry <katharine@pebble.com>

# Fix for Debian Buster EOL - switch to archive repos
RUN sed -i -e 's/deb.debian.org/archive.debian.org/g' \
           -e 's/security.debian.org/archive.debian.org/g' \
           -e '/buster-updates/d' \
    /etc/apt/sources.list

RUN apt-get update && apt-get install -y cmake libncurses5

# ycmd
RUN git clone https://github.com/Valloric/ycmd.git /ycmd && cd /ycmd && \
  git reset --hard 10c456c6e32487c2b75b9ee754a1f6cc6bf38a4f && \
  git submodule update --init --recursive && \
  python build.py --clang-completer

# Grab the toolchain
RUN curl -o /tmp/arm-cs-tools.tar https://cloudpebble-vagrant.s3.amazonaws.com/arm-cs-tools-stripped.tar && \
  tar -xf /tmp/arm-cs-tools.tar -C / && rm /tmp/arm-cs-tools.tar

# Node stuff - skip GPG verification for ancient Node 4.x
ENV NODE_VERSION=4.4.5 NPM_CONFIG_LOGLEVEL=info

RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt.asc" \
  && grep " node-v$NODE_VERSION-linux-x64.tar.gz\$" SHASUMS256.txt.asc | sha256sum -c - \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz" SHASUMS256.txt.asc

ENV SDK_THREE_VERSION=4.3

# Install SDK 3
RUN mkdir /sdk3 && \
  curl -L "https://github.com/aveao/PebbleArchive/raw/master/SDKCores/sdk-core-$SDK_THREE_VERSION.tar.bz2" | \
  tar --strip-components=1 -xj -C /sdk3

ADD requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /code
WORKDIR /code

ENV PATH="$PATH:/arm-cs-tools/bin" YCMD_PEBBLE_SDK3=/sdk3/ \
  YCMD_STDLIB=/arm-cs-tools/arm-none-eabi/include/ \
  DEBUG=yes YCMD_PORT=80 YCMD_BINARY=/ycmd/ycmd/__main__.py \
  YCMD_DEFAULT_SETTINGS=/ycmd/ycmd/default_settings.json

ENV PATH="$PATH:/ycmd"

CMD ["python", "proxy.py"]
