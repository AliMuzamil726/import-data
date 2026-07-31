# Deployment notes

## Environment variables

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | 50+ random characters. Never reuse across environments. |
| `DJANGO_DEBUG` | `False` in production. Flipping it on enables HSTS, secure cookies and SSL redirect. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Full origins (`https://sawie.example.com`) when behind a proxy. |
| `DB_ENGINE` | `postgres` or `sqlite`. |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | Postgres connection. |
| `REDIS_URL` | Enables the Redis channel layer and the Celery broker. Blank falls back to in-memory. |
| `WEATHER_PROVIDER` | `open-meteo` by default; no key required. |
| `WEATHER_CACHE_MINUTES` | How long a cached observation stays fresh. |
| `TIME_ZONE` | Defaults to `Asia/Karachi`. |

## Build the Tailwind stylesheet

```bash
npm install -D tailwindcss
npx tailwindcss -i ./static/css/tailwind.src.css -o ./static/css/tailwind.build.css --minify
```

Your `tailwind.config.js` at the project root should mirror the tokens in
`static/js/tailwind.config.js` and set `content: ['./templates/**/*.html', './static/js/**/*.js']`.
Then in `templates/base.html` and `templates/accounts/login.html`, replace the two
CDN script tags with `<link rel="stylesheet" href="{% static 'css/tailwind.build.css' %}">`.

## Static and media files

```bash
python manage.py collectstatic --noinput
```

WhiteNoise serves the hashed manifest when `DEBUG=False`. In the Docker stack,
nginx serves `/static/` and `/media/` from shared volumes instead.

Media grows quickly once NDVI bands are uploaded. For anything beyond a single
server, move `STORAGES["default"]` to S3 or compatible object storage.

## Process model

- `daphne config.asgi:application` — HTTP **and** WebSockets in one process.
- `gunicorn config.wsgi:application` — HTTP only. Use it only if you drop Channels.
- `celery -A config worker` — NDVI processing and weather refresh.
- `celery -A config beat` — the schedule in `config/celery.py`.

Without Celery, run the weather refresh from cron:

```
0 */3 * * * cd /app && python manage.py refresh_weather
```

## Database

```bash
python manage.py migrate
python manage.py bootstrap_roles
```

Back up with `pg_dump`. The `boundary` and `forecast` columns are JSON, so they
travel with a normal dump — no PostGIS extension is required. If you later need
spatial queries (distance, intersection), migrate `boundary` to a PostGIS
`PolygonField` and switch the database engine to `django.contrib.gis.db.backends.postgis`.

## Health checks

`GET /accounts/login/` returns 200 without authentication and is what the
Dockerfile's `HEALTHCHECK` uses.
