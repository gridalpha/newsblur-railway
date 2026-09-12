# newsblur/newsblur_node carries node_modules at /node and expects the server
# source to be bind-mounted at /srv, which is how upstream's docker-compose runs
# it. This layer supplies the source and makes the datastore addresses
# configurable: the shipped files hardcode the compose hostnames
# `newsblur_db_mongo` / `newsblur_db_redis` and pass no Redis password, neither
# of which can be expressed on Railway.
FROM newsblur/newsblur_node:latest

USER root

ARG NEWSBLUR_REF=main

ENV NODE_ENV=docker \
    NODE_PATH=/node/node_modules/

WORKDIR /srv

RUN set -ex \
    && apt-get update \
    && apt-get install -y --no-install-recommends git tini \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN set -ex \
    && git clone --depth 1 --branch "${NEWSBLUR_REF}" https://github.com/samuelclay/NewsBlur.git /tmp/newsblur \
    && cp -a /tmp/newsblur/node/. /srv/ \
    && rm -rf /tmp/newsblur

# Each substitution is asserted straight afterwards, so an upstream rename fails
# the build in seconds instead of leaving a server that quietly dials the
# compose hostnames and never connects.
RUN set -ex \
    && sed -i 's|MONGODB_SERVER = "newsblur_db_mongo";|MONGODB_SERVER = process.env.MONGODB_SERVER \|\| "newsblur_db_mongo";|' favicons.js \
    && sed -i 's|url = `mongodb://${MONGODB_SERVER}:${MONGODB_PORT}/newsblur`;|url = process.env.MONGODB_URL \|\| `mongodb://${MONGODB_SERVER}:${MONGODB_PORT}/newsblur`;|' favicons.js \
    && sed -i 's|REDIS_SERVER = "newsblur_db_redis";|REDIS_SERVER = process.env.REDIS_SERVER \|\| "newsblur_db_redis";|' unread_counts.js \
    && sed -i 's|REDIS_PORT = ENV_DOCKER ? 6579 : 6383;|REDIS_PORT = parseInt(process.env.REDIS_PORT \|\| (ENV_DOCKER ? 6579 : 6383), 10);|' unread_counts.js \
    && sed -i 's|host: REDIS_SERVER,|host: REDIS_SERVER, password: process.env.REDIS_PASSWORD \|\| undefined,|g' unread_counts.js \
    && sed -i 's|server.listen(8008);|server.listen(parseInt(process.env.PORT \|\| 8008, 10));|' newsblur.js \
    && grep -q 'process.env.MONGODB_URL' favicons.js \
    && grep -q 'process.env.REDIS_SERVER' unread_counts.js \
    && grep -q 'process.env.REDIS_PASSWORD' unread_counts.js \
    && grep -q 'process.env.PORT' newsblur.js \
    && node --check favicons.js \
    && node --check unread_counts.js \
    && node --check newsblur.js

# original_page.js writes fetched pages under /srv/originals. NewsBlur is
# configured with BACKED_BY_AWS.pages_on_node = false, so this is only a cache,
# but the directory has to exist for the route to answer at all.
RUN mkdir -p /srv/originals

EXPOSE 8008

ENTRYPOINT ["/usr/bin/tini", "-s", "--"]
CMD ["node", "newsblur.js"]
