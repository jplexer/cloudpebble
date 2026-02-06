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

# Django stuff
RUN apt-get update && apt-get install -y \
    gettext \
    postgresql-client libpq-dev \
    gcc \
    make \
    bzip2 \
    git \
    libc6-dev \
  --no-install-recommends && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

# CloudPebble stuff
RUN npm install -g bower@1.8.14 && echo '{"allow_root": true}' > ~/.bowerrc

# Grab the toolchain
RUN curl -o /tmp/arm-cs-tools.tar https://cloudpebble-vagrant.s3.amazonaws.com/arm-cs-tools-stripped.tar && \
  tar -xf /tmp/arm-cs-tools.tar -C / && rm /tmp/arm-cs-tools.tar

ADD requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV SDK_THREE_CHANNEL=beta
ENV SDK_THREE_VERSION=4.3

# Install SDK 3
RUN mkdir /sdk3 && \
  curl -L "https://github.com/aveao/PebbleArchive/raw/master/SDKCores/sdk-core-$SDK_THREE_VERSION.tar.bz2" | \
  tar --strip-components=1 -xj -C /sdk3

# Install SDK 3 Node dependencies
RUN cd /sdk3 && npm install
ENV WAF_NODE_PATH=/sdk3/node_modules

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

RUN python manage.py compilemessages

RUN make -C /code/c-preload

CMD ["sh", "docker_start.sh"]
