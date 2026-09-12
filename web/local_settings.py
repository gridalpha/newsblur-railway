"""Railway configuration for NewsBlur.

`newsblur_web/settings.py` imports `newsblur_web/docker_local_settings.py` (because
DOCKERBUILD is set) and then this file, which is the override hook the upstream
README documents for self-hosted installations. Everything here is driven from the
container environment so one image serves the web, task and build roles and a
Railway template needs no file edits.

Read the ordering carefully before adding anything: settings.py continues *after*
this import and rebuilds CACHES, CELERY_BROKER_URL, SESSION_REDIS and every
redis.ConnectionPool from the REDIS_* dicts below, so those dicts -- not the
derived values -- are the place to configure Redis.
"""

import os
import sys as _sys

import redis as _redis


def _env(key, default=None):
    value = os.environ.get(key)
    return value if value not in (None, "") else default


def _flag(key, default):
    value = _env(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# ==========================================================================
# = Redis credentials =
# ==========================================================================
# NewsBlur builds every client with redis.ConnectionPool(host=..., port=...) and
# passes no password, so an authenticated Redis is otherwise unreachable. The
# host strings below carry `user:password@host`, which makes the URL forms
# settings.py derives (CACHES, CELERY_BROKER_URL) correct as written, and these
# two subclasses split the credentials back out for the keyword-argument forms.


def _split_credentials(kwargs):
    host = kwargs.get("host")
    if not host or "@" not in host:
        return
    credentials, _, hostname = host.rpartition("@")
    username, _, password = credentials.partition(":")
    kwargs["host"] = hostname
    if not password:
        username, password = "", username
    if password:
        kwargs.setdefault("password", password)
    if username and username != "default":
        kwargs.setdefault("username", username)


class _AuthConnectionPool(_redis.ConnectionPool):
    def __init__(self, *args, **kwargs):
        _split_credentials(kwargs)
        super().__init__(*args, **kwargs)


class _AuthRedis(_redis.Redis):
    def __init__(self, *args, **kwargs):
        _split_credentials(kwargs)
        super().__init__(*args, **kwargs)


_redis.ConnectionPool = _AuthConnectionPool
_redis.Redis = _AuthRedis
_redis.StrictRedis = _AuthRedis

# ==========================================================================
# = Site =
# ==========================================================================

NEWSBLUR_URL = _env("NEWSBLUR_URL", "http://localhost:8000")
SERVER_NAME = _env("RAILWAY_SERVICE_NAME", "newsblur")
SECRET_KEY = _env("SECRET_KEY", "railway-build-time-placeholder")
IMAGES_SECRET_KEY = _env("IMAGES_SECRET_KEY", "railway-build-time-placeholder")
IMAGES_URL = _env("IMAGES_URL", "/imageproxy")

# A host-only session cookie. Upstream scopes it to `.newsblur.com`, and
# `up.railway.app` is on the Public Suffix List, so any Domain= attribute built
# from the deployed hostname is dropped by the browser and every login fails.
SESSION_COOKIE_DOMAIN = None

# The edge terminates TLS and Caddy passes the original X-Forwarded-Proto
# through, so Django can tell a real request is https. Without this the CSRF
# referer check rejects every POST and the session cookie loses `Secure`.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DEBUG = False
DEBUG_ASSETS = False
DEBUG_QUERIES = False
DEBUG_QUERIES_SUMMARY_ONLY = True

# Upstream ships a placeholder Sentry DSN that parses as a valid URL, so leaving
# it in place with DEBUG=False ships every exception to someone else's account.
SENTRY_DSN = None
FLASK_SENTRY_DSN = None

# media/ is a STATICFILES_DIRS entry, so collectstatic copies it into
# STATIC_ROOT and WhiteNoise serves both trees from one URL prefix.
MEDIA_URL = "/static/"

LOG_TO_STREAM = True

# WhiteNoise serves STATIC_ROOT directly from the app container, which replaces
# the nginx service upstream's compose runs beside gunicorn. `from ... import *`
# runs this file in its own namespace, so the existing tuple has to be read back
# off the half-initialised settings module rather than referenced by name.
_settings_module = _sys.modules.get("newsblur_web.settings")
if _settings_module is not None and hasattr(_settings_module, "MIDDLEWARE"):
    MIDDLEWARE = ("whitenoise.middleware.WhiteNoiseMiddleware",) + tuple(_settings_module.MIDDLEWARE)
WHITENOISE_MAX_AGE = 31536000
WHITENOISE_INDEX_FILE = False

# Accounts are usable the moment they are created, which is upstream's
# self-hosted default. Set NEWSBLUR_AUTO_ENABLE_NEW_USERS=false to have signups
# land inactive until an administrator enables them in /admin/.
AUTO_ENABLE_NEW_USERS = _flag("NEWSBLUR_AUTO_ENABLE_NEW_USERS", True)
AUTO_PREMIUM = _flag("NEWSBLUR_AUTO_PREMIUM", True)
AUTO_PREMIUM_NEW_USERS = AUTO_PREMIUM
AUTO_PREMIUM_ARCHIVE_NEW_USERS = AUTO_PREMIUM
AUTO_PREMIUM_PRO_NEW_USERS = AUTO_PREMIUM
ENFORCE_SIGNUP_CAPTCHA = False
ENABLE_PUSH = False

HOMEPAGE_USERNAME = _env("NEWSBLUR_HOMEPAGE_USERNAME", "popular")
DAYS_OF_UNREAD = int(_env("NEWSBLUR_DAYS_OF_UNREAD", "30"))
DAYS_OF_UNREAD_FREE = int(_env("NEWSBLUR_DAYS_OF_UNREAD_FREE", "14"))

# Nothing here uses S3: pages, icons and avatars are stored in MongoDB.
BACKED_BY_AWS = {
    "pages_on_node": False,
    "pages_on_s3": False,
    "icons_on_s3": False,
}

# ==========================================================================
# = Email =
# ==========================================================================

if _env("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _env("EMAIL_HOST")
    EMAIL_PORT = int(_env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = _env("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = _env("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = _flag("EMAIL_USE_TLS", True)
    EMAIL_USE_SSL = _flag("EMAIL_USE_SSL", False)
    SERVER_EMAIL = _env("EMAIL_FROM", "newsblur@localhost")
    HELLO_EMAIL = SERVER_EMAIL
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ==========================================================================
# = PostgreSQL =
# ==========================================================================

DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": _env("POSTGRES_DB", "newsblur"),
        "USER": _env("POSTGRES_USER", "newsblur"),
        "PASSWORD": _env("POSTGRES_PASSWORD", "newsblur"),
        "HOST": _env("POSTGRES_HOST", "127.0.0.1"),
        "PORT": int(_env("POSTGRES_PORT", "5432")),
        "CONN_MAX_AGE": int(_env("POSTGRES_CONN_MAX_AGE", "0")),
        "OPTIONS": {
            "sslmode": _env("POSTGRES_SSLMODE", "prefer"),
            "connect_timeout": 10,
        },
    },
}

# ==========================================================================
# = MongoDB =
# ==========================================================================
# pymongo is pinned below 4 by mongoengine 0.21, so the newest server it can
# speak to is MongoDB 5.0 -- see the profile for why the template ships its own
# mongo:5.0 service rather than Railway's managed MongoDB 8.

_mongo_host = _env("MONGODB_HOST", "127.0.0.1:27017")
_mongo_user = _env("MONGODB_USERNAME")
_mongo_password = _env("MONGODB_PASSWORD")
_mongo_auth_source = _env("MONGODB_AUTH_SOURCE", "admin")

if _mongo_user and _mongo_password:
    _mongo_url = "mongodb://%s:%s@%s/?authSource=%s" % (
        _mongo_user,
        _mongo_password,
        _mongo_host,
        _mongo_auth_source,
    )
else:
    _mongo_url = "mongodb://%s/" % _mongo_host

MONGO_DB = {
    "name": _env("MONGODB_NAME", "newsblur"),
    "host": _env("MONGODB_URL", _mongo_url),
}
MONGO_ANALYTICS_DB = {
    "name": _env("MONGODB_ANALYTICS_NAME", "nbanalytics"),
    "host": _mongo_host,
}
if _mongo_user and _mongo_password:
    MONGO_ANALYTICS_DB["username"] = _mongo_user
    MONGO_ANALYTICS_DB["password"] = _mongo_password
MONGODB_SLAVE = {"host": _mongo_host}

# ==========================================================================
# = Redis =
# ==========================================================================
# One Redis serves all four roles, separated by database number exactly as
# upstream's own docker-compose does. settings.py forces port 6579 under
# DOCKERBUILD, which is why the service is deployed on that port.

_redis_host = _env("REDIS_HOST", "127.0.0.1")
_redis_username = _env("REDIS_USERNAME", "default")
_redis_password = _env("REDIS_PASSWORD")
if _redis_password:
    _redis_host = "%s:%s@%s" % (_redis_username, _redis_password, _redis_host)

REDIS_USER = {"host": _redis_host}
REDIS_STORY = {"host": _redis_host}
REDIS_SESSIONS = {"host": _redis_host}
REDIS_PUBSUB = {"host": _redis_host}
REDIS_STORY_SECONDARY = None

# ==========================================================================
# = Elasticsearch =
# ==========================================================================

_elasticsearch = _env("ELASTICSEARCH_HOST", "http://127.0.0.1:9200")
_elasticsearch_hostport = _elasticsearch.split("://", 1)[-1].rstrip("/")

ELASTICSEARCH_FEED_HOST = _elasticsearch
ELASTICSEARCH_STORY_HOST = _elasticsearch
ELASTICSEARCH_DISCOVER_HOST = _elasticsearch
ELASTICSEARCH_FEED_HOSTS = [_elasticsearch_hostport]
ELASTICSEARCH_STORY_HOSTS = [_elasticsearch_hostport]
ELASTICSEARCH_DISCOVER_HOSTS = [_elasticsearch_hostport]

# ==========================================================================
# = Optional third-party keys =
# ==========================================================================
# Left at their placeholder values unless a deployer supplies a real one, so no
# feature silently talks to an account nobody owns.

for _name in (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_GEMINI_API_KEY",
    "XAI_GROK_API_KEY",
    "YOUTUBE_API_KEY",
):
    _value = _env(_name)
    if _value:
        globals()[_name] = _value
