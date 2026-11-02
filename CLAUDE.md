# Global Wildfire Portal

Full stack geospatial portal for wildfire risk and monitoring. Serves vector tiles
(PostGIS `ST_AsMVT`) and raster tiles (TiTiler) over a web map.

## Stack (PERN + Python FastAPI)

- **DB**: PostgreSQL 16 + PostGIS 3.4. Database name `global-wildfire`.
- **Backend**: Node.js + Express. REST API and vector tile endpoints.
- **Geoprocessing**: Python FastAPI + GDAL/OGR (osgeo, ogr2ogr) for ingest and analysis.
- **Raster tiles**: TiTiler (FastAPI) serving Cloud Optimized GeoTIFFs.
- **Frontend**: React + Vite + Tailwind CSS. Icons from `react-icons` only.

## Ports (fixed, do not change)

| Service            | Host port | Notes                          |
|--------------------|-----------|--------------------------------|
| PostgreSQL/PostGIS | 5440      | maps to container 5432         |
| Backend (Express)  | 3040      | REST + `ST_AsMVT` vector tiles |
| Geoprocessing API  | 3041      | FastAPI ingest/analysis        |
| TiTiler (raster)   | 3042      | COG tiles                      |
| Frontend (Vite)    | 5180      | dev server + build             |

Backend family lives in the 3040 range. Frontend on 5180. DB on 5440.

## Layout

```
frontend/         React + Vite + Tailwind, react-icons
backend/          Express API, ST_AsMVT vector tiles
geoprocessing/    FastAPI + GDAL/OGR ingest and analysis
db/               PostGIS init SQL, migrations
shared/           cross-service constants and helpers (JS + Python)
data/             source rasters (elevation.tif, slope.tif) and COGs
docker-compose.yml
```

## Conventions

- No em-dashes in code, comments, docs, or UI copy. Use commas or parentheses.
- Reuse `shared/` utilities. Do not duplicate helpers across services.
- Styling is Tailwind utility classes. No inline styles unless dynamic.
- Icons come from `react-icons`. Never install or use `lucide-react`.
- Vectors are served as MVT via `ST_AsMVT`. Rasters are served as COG via TiTiler.
- All geometry stored in EPSG:4326, tiled in EPSG:3857.
- This project is self contained. Do not import context or code from other projects.

## Common commands

```bash
docker compose up -d            # start the global-wildfire-portal stack
docker compose logs -f backend  # follow one service
docker compose down             # stop
```

## Context engineering

- Agents: `.claude/agents/` (frontend, backend, middleware, db, geoprocessing).
- Skills: `.claude/skills/` (repeatable tasks).
- Playbooks: `.claude/playbooks/` (multi-step procedures).
- Guardrails and conventions: `.claude/rules/`.
- Project memory: `.claude/memory/` (architecture, decisions, data sources, glossary).
