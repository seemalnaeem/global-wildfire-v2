# Guardrails (hard rules)

Non-negotiable. Apply to every agent and every change.

## Safety
- Never run `docker compose down -v` or drop the `gwf_pgdata` volume without an
  explicit request. It wipes the database.
- Never `rm -rf` source or data directories.
- Never commit `.env` or print secrets in logs or responses.
- Do not delete or overwrite the source rasters in `data/`. Write COGs as new files.

## SQL
- Parameterize every query. No user input concatenated into SQL.
- Use the shared `pg` pool. No ad hoc connections.

## Ports and names (fixed)
- DB `global-wildfire` on 5440. Backend on 3040 range. Frontend on 5180.
- TiTiler on 3042. Geoprocessing on 3041. Do not change these.

## Stack
- Icons from `react-icons` only. `lucide-react` is banned.
- Styling is Tailwind. Vectors via `ST_AsMVT`. Rasters via TiTiler.
- Geometry stored in EPSG:4326, tiled in EPSG:3857.

## Scope
- This project is self contained. Do not pull code or context from other projects
  on this machine.
- Only process external API sources the codebase needs. Proxy the rest live.

## Resources
- Never load multi-GB rasters fully into memory. Stream, window, or use GDAL CLI.
