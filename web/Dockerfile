# NewsBlur's published image (newsblur/newsblur_python3) is a dependency base:
# upstream's docker-compose bind-mounts the checkout over /srv/newsblur, so the
# image carries the virtualenv and none of the application. This layer supplies
# the code, reconciles the requirements file against the base image's venv, and
# builds the production asset bundles that DEBUG=False expects.
FROM newsblur/newsblur_python3:latest

# The base ends on a non-root stage on some rebuilds; every step below needs root.
USER root

ARG NEWSBLUR_REF=main

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/srv/newsblur \
    DJANGO_SETTINGS_MODULE=newsblur_web.settings \
    DOCKERBUILD=True \
    LANG=C.UTF-8

WORKDIR /srv/newsblur

# terser and lightningcss are what django-pipeline shells out to when it builds
# the common.js / common.css bundles; tini reaps the children gunicorn and
# celery fork, since a Railway start command never runs as PID 1.
RUN set -ex \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        nodejs \
        npm \
        tini \
    && npm install -g terser@5 \
    && npm cache clean --force \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN uv pip install lightningcss whitenoise

# A shallow checkout of the branch, minus the trees that are not part of the
# server: the iOS/Android clients, the marketing blog and the release tooling.
RUN set -ex \
    && git clone --depth 1 --branch "${NEWSBLUR_REF}" https://github.com/samuelclay/NewsBlur.git /tmp/newsblur \
    && rm -rf \
        /tmp/newsblur/.git \
        /tmp/newsblur/blog \
        /tmp/newsblur/clients \
        /tmp/newsblur/archive \
        /tmp/newsblur/fastlane \
        /tmp/newsblur/TestFlight \
        /tmp/newsblur/ansible \
    && cp -a /tmp/newsblur/. /srv/newsblur/ \
    && rm -rf /tmp/newsblur

# The base image is rebuilt less often than the branch, so anything the branch
# has added since is installed here. Unchanged pins are a no-op.
RUN uv pip install -r /srv/newsblur/config/requirements.txt

# rss_feeds/0003 hardcodes `setFeatureCompatibilityVersion: "4.0"`, which any
# server newer than 4.4 rejects outright -- upstream's compose runs mongo:4.0, and
# this deployment runs 5.0 because that is the newest server pymongo 3 can speak
# to. Comparing instead of testing inequality makes the step raise the FCV and
# never lower it, which is the only direction that was ever meaningful.
RUN set -ex \
    && MIG=/srv/newsblur/apps/rss_feeds/migrations/0003_mongo_version_4_0.py \
    && grep -q "if old_version != new_version:" "$MIG" \
    && sed -i "s/if old_version != new_version:/if old_version < new_version:/" "$MIG" \
    && grep -q "if old_version < new_version:" "$MIG" \
    && python -c "import py_compile; py_compile.compile('/srv/newsblur/apps/rss_feeds/migrations/0003_mongo_version_4_0.py', doraise=True)"

COPY web/local_settings.py /srv/newsblur/newsblur_web/local_settings.py
COPY web/reader_subdomain_patch.py /tmp/reader_subdomain_patch.py
COPY web/rss_feeds_similar_patch.py /tmp/rss_feeds_similar_patch.py
COPY web/railway_whitenoise.py /srv/newsblur/utils/railway_whitenoise.py
COPY web/entrypoint.sh /usr/local/bin/newsblur-entrypoint

RUN chmod +x /usr/local/bin/newsblur-entrypoint \
    && bash -n /usr/local/bin/newsblur-entrypoint \
    && python -c "import py_compile; py_compile.compile('/srv/newsblur/newsblur_web/local_settings.py', doraise=True)" \
    && python -c "import py_compile; py_compile.compile('/srv/newsblur/utils/railway_whitenoise.py', doraise=True)" \
    && grep -q "^def get_subdomain(request):" /srv/newsblur/apps/reader/views.py \
    && cat /tmp/reader_subdomain_patch.py >> /srv/newsblur/apps/reader/views.py \
    && rm -f /tmp/reader_subdomain_patch.py \
    && python -c "import py_compile; py_compile.compile('/srv/newsblur/apps/reader/views.py', doraise=True)" \
    && grep -q "    def count_similar_feeds(" /srv/newsblur/apps/rss_feeds/models.py \
    && cat /tmp/rss_feeds_similar_patch.py >> /srv/newsblur/apps/rss_feeds/models.py \
    && rm -f /tmp/rss_feeds_similar_patch.py \
    && python -c "import py_compile; py_compile.compile('/srv/newsblur/apps/rss_feeds/models.py', doraise=True)"

# Build the bundles. DEBUG=False turns django-pipeline on, so a container that
# skipped this step serves a page referencing files that do not exist. Upstream's
# own deploy image asserts on the two bundle sizes; a silent terser crash is the
# failure this catches.
RUN set -ex \
    && mkdir -p /srv/newsblur/logs /srv/newsblur/.prom_cache \
    && python manage.py collectstatic --no-input --clear -v 1 -l \
    && CSS_SIZE=$(stat -c%s /srv/newsblur/static/css/common.css) \
    && JS_SIZE=$(stat -c%s /srv/newsblur/static/js/common.js) \
    && echo "common.css: ${CSS_SIZE} bytes, common.js: ${JS_SIZE} bytes" \
    && [ "$CSS_SIZE" -gt 1000 ] \
    && [ "$JS_SIZE" -gt 1000 ]

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "-s", "--"]
CMD ["/usr/local/bin/newsblur-entrypoint", "web"]
