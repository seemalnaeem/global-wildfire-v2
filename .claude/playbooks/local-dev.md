# Playbook: local development

Bring up the global-wildfire-portal stack and work on it locally.

## Start
```bash
cp .env.example .env        # first run only
docker compose up -d
docker compose ps           # all healthy
```

## URLs
- Frontend: http://localhost:5180
- Backend: http://localhost:3040/health
- Geoprocessing: http://localhost:3041/health
- TiTiler: http://localhost:3042/healthz
- PostGIS: localhost:5440 (db `global-wildfire`, user `gwf`)

## Iterate
- Frontend and backend mount source for hot reload. Edit and save.
- After schema changes, rerun migrations (see `db` agent).
- Follow one service: `docker compose logs -f <service>`.

## Stop
```bash
docker compose down         # keep data
```
Never run `docker compose down -v` unless you intend to wipe the database volume.
