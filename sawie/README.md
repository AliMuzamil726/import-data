# SAWIE — Agricultural Intelligence Platform

A working Django 5 application for managing farmers, mapped fields, crop cycles,
weather and satellite vegetation indices. Real database, real authentication,
real CRUD, real file processing — no mocked screens.

---

## Run it locally in five commands

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # defaults to SQLite, no setup needed
python manage.py migrate
python manage.py bootstrap_roles                     # prints one account per role
python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in with the credentials printed by
`bootstrap_roles`. Change them straight away.

Want a populated interface to click through?

```bash
python manage.py seed_demo --farmers 40
```

That writes sample farmers, fields, crop cycles and activity logs across the
Punjab cotton and rice belt. It refuses to run if farmer records already exist,
unless you pass `--force`.

### Run with WebSockets and background tasks

`runserver` handles HTTP fine, but live notifications need the ASGI server:

```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Without Redis, Channels uses an in-memory layer (single process only) and Celery
runs tasks inline. Set `REDIS_URL` in `.env` to switch both to the real thing:

```bash
celery -A config worker -l info
celery -A config beat -l info      # scheduled weather refresh + NDVI sweep
```

### Run the whole stack in Docker

```bash
cp .env.example .env      # set DJANGO_SECRET_KEY and DJANGO_DEBUG=False
docker compose up --build
docker compose exec web python manage.py bootstrap_roles
```

Postgres, Redis, Daphne, a Celery worker, Celery beat and nginx come up together.

---

## What each module does

| Module | What works |
|---|---|
| **Authentication** | Django auth, hashed passwords, remember-me, password reset by email, session expiry |
| **Roles** | Super Admin / Agriculture Manager / Field Officer / Farmer. Roles gate both the sidebar and the views, and scope querysets at row level |
| **Dashboard** | Eight metric cards computed from live aggregates, each with a period-over-period change and a sparkline, plus crop-mix and canopy-health charts |
| **Farmers** | Full CRUD, CNIC normalisation and validation, search, filters, pagination, CSV/Excel/PDF export |
| **Fields** | Full CRUD, Leaflet marker + polygon drawing, area computed from the drawn geometry, GeoJSON stored in the database, activity log |
| **Map** | Satellite and street layers, marker clustering, polygon rendering coloured by health, live filtering by crop, health and status |
| **Crops** | Full CRUD, cross-field validation (harvest after planting, area within the plot), yield per acre and revenue derived from production |
| **Weather** | Live Open-Meteo integration per field coordinate, cached, 7-day forecast, agronomy advisories, scheduled refresh with threshold alerts |
| **NDVI** | Real raster maths in NumPy. Red + NIR bands give true NDVI; a single RGB image falls back to VARI and is labelled as such. Produces a colourised overlay, class distribution, health score, and writes the band back to the field |
| **Analytics** | Six charts over 6/12/24-month windows, all aggregated in SQL |
| **Reports** | PDF, Excel and CSV for every dataset, respecting the filters you set. Each export is logged |
| **Notifications** | WebSocket push via Channels, with an HTTP polling fallback when the socket cannot connect. Raised by registrations, weather thresholds and NDVI results |
| **REST API** | `/api/v1/` with role-scoped viewsets, filtering, search, ordering and pagination |

---

## Project layout

```
sawie/
├── config/            settings, URLs, ASGI/WSGI, Channels routing, Celery
├── apps/
│   ├── accounts/      custom user model, roles, permissions, auth views
│   ├── core/          shared base models, notifications, dashboard, scoping
│   ├── farmers/       farmer registry
│   ├── fields/        plots, GeoJSON boundaries, map endpoints, activity log
│   ├── crops/         crop cycles, yield and revenue
│   ├── weather/       provider integration, caching, advisories, tasks
│   ├── ndvi/          raster processing, overlays, alerting
│   ├── analytics/     chart datasets
│   └── reports/       CSV/Excel/PDF exporters and the report centre
├── api/               DRF serializers, viewsets, router
├── templates/         Django templates, Tailwind + Alpine
├── static/            CSS, JS, design tokens, logo
├── nginx/             reverse-proxy config with WebSocket upgrade
├── Dockerfile
└── docker-compose.yml
```

---

## Tests

```bash
python manage.py test
```

38 tests covering role permissions, CNIC validation, CRUD flows, GeoJSON
handling, the boundary endpoint, dashboard aggregation, notification routing,
API scoping, export content types, and the NDVI maths — including the case where
uniform bands of red=50 / NIR=200 must produce exactly 0.6.

---

## Three things to do before you go live

1. **Drop in the real logo.** `static/images/logo.svg` is a placeholder. Replace
   the file, keep the path, and the login page, sidebar, favicon and PDF headers
   all pick it up.
2. **Build Tailwind properly.** The CDN build is convenient for development but
   ships the whole framework. Run the Tailwind CLI against
   `static/js/tailwind.config.js` and swap the `<script src="cdn.tailwindcss.com">`
   tag in `templates/base.html` for the compiled stylesheet.
3. **Set the production environment.** `DJANGO_SECRET_KEY` to a long random
   string, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` to your domain,
   `DB_ENGINE=postgres`, and `REDIS_URL` so Channels and Celery leave their
   in-memory modes. With `DEBUG=False` the settings automatically switch on HSTS,
   secure cookies and SSL redirect.

---

## Notes on the NDVI module

NDVI is `(NIR − Red) / (NIR + Red)` and needs a near-infrared band. Sentinel-2,
Landsat and NIR-capable drones provide one. An ordinary RGB photo does not, so
the platform computes VARI — `(G − R) / (G + R − B)` — instead, and labels every
result with the index actually used. VARI tracks canopy greenness but is not
interchangeable with NDVI, and the interface never pretends otherwise.

Class boundaries live in `apps/ndvi/processing.py` (`CRITICAL_MAX`, `POOR_MAX`,
`MODERATE_MAX`). Tune them to your crops and calibration.

For very large GeoTIFFs, add `rasterio` and read windows rather than whole
rasters — the current path downsamples to 1600 px on the longest side, which is
fine for plot-scale scenes.
