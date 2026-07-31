# Architecture

## Request paths

```
Browser ──HTTP──►  nginx ──►  Daphne (ASGI) ──►  Django views ──►  PostgreSQL
        └─WS───►  nginx ──►  Daphne ──► Channels consumer ──► Redis channel layer

Celery worker ──► NDVI processing (NumPy/Pillow) ──► media storage
              └─► Open-Meteo ──► WeatherData cache
```

## Access control, in two layers

1. **Module gate.** `ROLE_MODULES` in `apps/accounts/models.py` maps each role to
   the modules it may open. `ModuleRequiredMixin` and `@module_required` enforce
   it, and the same map drives which sidebar links render.
2. **Row scope.** `apps/core/scoping.py` narrows querysets. A Farmer-role user
   sees only the fields and crops belonging to their linked farmer record — in
   the web views and in the REST API alike.

Write and delete permissions are separate again: Field Officers can edit but not
delete; Farmers are read-only.

## Geometry without PostGIS

Field boundaries are GeoJSON `Polygon` objects in a `JSONField`, validated in
`Field.clean()`. Area is computed in the browser from the drawn polygon using the
spherical-excess formula in `static/js/geo.js`, then saved server-side. This keeps
the deployment to a plain Postgres image. Swap to PostGIS when you need spatial
queries rather than storage.

## Notifications

`apps/core/notifications.notify()` writes a row and pushes it to the channel
layer — either to `sawie_user_<id>` for a targeted alert, or to `sawie_broadcast`.
Push failures are logged and swallowed, so a Redis outage never breaks a request.
The browser falls back to polling `/notifications/feed/` if the socket drops.

Domain events live in `apps/core/signals.py`: farmer registration, field mapping,
health-band changes and recorded harvests.

## Dashboard aggregation

`apps/core/services.dashboard_metrics()` and `apps/analytics/services.analytics_payload()`
do all their work in SQL — `Sum`, `Count`, `Avg`, `TruncMonth` — and return plain
dictionaries. Nothing is computed in Python loops over querysets, so the pages
stay flat as the dataset grows. Both helpers take the user and apply the same
scoping rules as the views.
