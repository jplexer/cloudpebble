FROM python:3.11-slim-bookworm
LABEL maintainer="CloudPebble Contributors"

ENV NPM_CONFIG_LOGLEVEL=info NODE_VERSION=20.11.0 DJANGO_VERSION=4.2 NODEJS_CHECK_SIGNATURES=no

# Node stuff.
RUN apt-get update && apt-get install -y curl && \
  curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" && \
  curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt.asc" && \
  grep " node-v$NODE_VERSION-linux-x64.tar.gz\$" SHASUMS256.txt.asc | sha256sum -c - && \
  tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 && \
  rm "node-v$NODE_VERSION-linux-x64.tar.gz" SHASUMS256.txt.asc

RUN npm install -g jshint@2.13.6

# Django stuff + emulator dependencies
RUN apt-get update && apt-get install -y \
    gettext \
    postgresql-client libpq-dev \
    gcc \
    make \
    bzip2 \
    git \
    libc6-dev \
    libsdl1.2debian \
    libfdt1 \
    libglib2.0-0 \
  --no-install-recommends && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

# CloudPebble stuff
RUN npm install -g bower@1.8.14 && echo '{"allow_root": true}' > ~/.bowerrc

# Install uv for Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install pebble-tool via uv
RUN uv tool install pebble-tool --python 3.11

# Ensure pebble is in PATH
ENV PATH="/root/.local/share/uv/tools/pebble-tool/bin:$PATH"

# Install Pebble SDKs (downloads SDK + toolchain + QEMU)
RUN pebble sdk install 4.9.121-1-moddable
RUN pebble sdk install 4.9.77
RUN pebble sdk activate 4.9.121-1-moddable

# Set up SDK paths for CloudPebble
ENV PEBBLE_SDK_PATH=/root/.pebble-sdk
ENV PATH="${PEBBLE_SDK_PATH}/SDKs/current/toolchain/arm-none-eabi/bin:$PATH"

ADD requirements.txt /tmp/requirements.txt
# Use Python 3.11 from the base image directly
RUN /usr/local/bin/pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /code
WORKDIR /code

# Bower is awful. Run bower directly instead of Django management command
RUN rm -rf bower_components && \
  bower install --allow-root \
    "https://github.com/krisk/Fuse.git#2ec2f2c40059e135cabf2b01c8c3f96f808b8809" \
    "jquery#~2.1.3" \
    "underscore" \
    "backbone" \
    "text-encoding" \
    "jshint/jshint" \
    "html.sortable#~0.3.1" \
    "alexgorbatchev/jquery-textext" \
    "codemirror#4.2.0" \
    "bluebird#3.3.4" \
    "kanaka/noVNC#v0.5"

RUN SECRET_KEY=build-placeholder /usr/local/bin/python manage.py compilemessages

RUN make -C /code/c-preload

CMD ["sh", "docker_start.sh"]
