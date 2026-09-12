# NewsBlur on Railway

Deployment files for running [NewsBlur](https://github.com/samuelclay/NewsBlur) —
the self-hosted RSS reader with training, full-text search and shared blurblogs —
on [Railway](https://railway.com). Three images are built from this one repository.

| Path | Railway service | What it is |
|---|---|---|
| `web/Dockerfile` | `web`, `tasks` | NewsBlur's Django app. `web` serves HTTP and owns the schema; `tasks` runs the celery worker with its embedded beat scheduler. |
| `node/Dockerfile` | `node` | NewsBlur's Node servers: favicons, original-text extraction, original-page cache and the Socket.IO unread-count stream. |
| `caddy/Dockerfile` | `newsblur` | The public origin. Splits one hostname across the Django, Node and imageproxy backends, which Railway's edge cannot do on its own. |

## Why these files exist

`newsblur/newsblur_python3` and `newsblur/newsblur_node` are **dependency base
images**: upstream's `docker-compose.yml` bind-mounts the checkout over
`/srv/newsblur` and `/srv`, so neither published image contains any application
code. Each Dockerfile here supplies the code at build time and adds the pieces a
container-per-service platform needs:

- **`web/local_settings.py`** — the override hook upstream's README documents for
  self-hosted installs, driven entirely from the container environment. It also
  subclasses `redis.ConnectionPool` and `redis.Redis` to split `user:password@host`
  back out, because NewsBlur constructs every Redis client without a password
  argument and an authenticated Redis is otherwise unreachable.
- **`web/entrypoint.sh`** — waits for PostgreSQL, migrates, seeds the Django
  superuser once, then execs gunicorn with stdout logging (upstream's
  `gunicorn_conf.py` writes to files, which `railway logs` never sees).
- **`node/Dockerfile`** — patches the hardcoded `newsblur_db_mongo` /
  `newsblur_db_redis` compose hostnames, the fixed Redis port, the missing Redis
  password and the fixed listen port into environment variables. Each substitution
  is asserted in the same layer, so an upstream rename fails the build rather than
  the deployment.

## Build arguments

| Arg | Default | Notes |
|---|---|---|
| `NEWSBLUR_REF` | `master` | Branch or tag of `samuelclay/NewsBlur` to build. NewsBlur publishes no versioned server releases; `master` is the line self-hosters run. |

## Environment

The Railway template sets everything. `deployments/` in the pipeline repo, and the
template's own variable descriptions, are the reference for each one.

## Licence

NewsBlur is MIT licensed. These deployment files are provided under the same terms.
