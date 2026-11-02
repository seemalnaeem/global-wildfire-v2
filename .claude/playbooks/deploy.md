# Playbook: build and deploy

Ship the global-wildfire-portal stack as built images.

## Build
```bash
docker compose build
```
Each service has its own Dockerfile. TiTiler uses the upstream image.

## Configure
- Set real secrets in the target `.env` (never commit it).
- Point `VITE_BACKEND_URL` and `VITE_TITILER_URL` at the public hosts.
- Confirm ports: DB 5440, backend 3040, geoprocessing 3041, TiTiler 3042,
  frontend 5180.

## Data
- COGs must exist in the mounted `data/` volume before TiTiler starts.
- Run DB migrations against the target database once it is healthy.

## Release
```bash
docker compose up -d
docker compose ps        # all healthy
```

## Rollback
Keep the previous image tags. `docker compose up -d` with the prior tags. The
Postgres volume persists across releases, so migrations must be backward safe.
