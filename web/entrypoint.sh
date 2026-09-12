#!/usr/bin/env bash
# One entrypoint, two roles. `web` owns the schema and serves HTTP; `tasks` runs
# the celery worker with its embedded beat scheduler, exactly as upstream's
# docker-compose does. Railway has no service ordering, so both roles retry
# until the datastores answer instead of assuming they are already up.
set -eo pipefail

cd /srv/newsblur

ROLE="${1:-web}"

log() { echo " ---> [entrypoint] $*"; }

mkdir -p logs .prom_cache static

wait_for_postgres() {
    for attempt in $(seq 1 60); do
        if python - <<'PY'
import sys

import django
from django.conf import settings

django.setup()
from django.db import connection

try:
    connection.ensure_connection()
except Exception as exc:  # noqa: BLE001
    print("    postgres not ready: %s" % exc)
    sys.exit(1)
PY
        then
            return 0
        fi
        log "waiting for postgres (attempt ${attempt})"
        sleep 5
    done
    log "postgres never became reachable"
    return 1
}

seed_admin() {
    # Creates the Django superuser once. It is never updated afterwards, so an
    # operator who changes the password in the admin keeps that change across
    # every redeploy.
    [ -n "${NEWSBLUR_ADMIN_USERNAME}" ] || return 0
    [ -n "${NEWSBLUR_ADMIN_PASSWORD}" ] || return 0
    python - <<'PY'
import os

import django

django.setup()
from django.contrib.auth.models import User

username = os.environ["NEWSBLUR_ADMIN_USERNAME"]
password = os.environ["NEWSBLUR_ADMIN_PASSWORD"]
email = os.environ.get("NEWSBLUR_ADMIN_EMAIL", "")

if User.objects.filter(username=username).exists():
    print(" ---> [entrypoint] admin user already exists, leaving it alone")
else:
    user = User.objects.create_superuser(username=username, email=email, password=password)
    try:
        user.profile.activate_premium()
    except Exception as exc:  # noqa: BLE001
        print(" ---> [entrypoint] could not activate premium for admin: %s" % exc)
    print(" ---> [entrypoint] created admin user %s" % username)
PY
}

case "$ROLE" in
    web)
        wait_for_postgres
        log "applying migrations"
        for attempt in $(seq 1 10); do
            if python manage.py migrate --noinput; then
                break
            fi
            log "migrate failed, retrying (attempt ${attempt})"
            sleep 10
        done
        seed_admin
        log "starting gunicorn on ${PORT:-8000}"
        exec gunicorn \
            -c config/gunicorn_conf.py \
            --bind "0.0.0.0:${PORT:-8000}" \
            --workers "${GUNICORN_WORKERS:-3}" \
            --access-logfile - \
            --error-logfile - \
            --log-file - \
            newsblur_web.wsgi:application
        ;;
    tasks)
        wait_for_postgres
        # The web role owns migrations. Waiting for the schema keeps the worker
        # from raising on a table that does not exist yet on a cold deploy.
        for attempt in $(seq 1 60); do
            if python manage.py migrate --check >/dev/null 2>&1; then
                break
            fi
            log "waiting for the web service to finish migrating (attempt ${attempt})"
            sleep 10
        done
        log "starting celery worker with embedded beat"
        exec celery worker \
            -A newsblur_web \
            -B \
            --loglevel="${CELERY_LOGLEVEL:-INFO}"
        ;;
    *)
        exec "$@"
        ;;
esac
