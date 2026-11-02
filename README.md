# Global Wildfire Portal

A full stack geospatial portal for wildfire risk and monitoring. Vector data is
tiled from PostGIS with `ST_AsMVT`, rasters are tiled with TiTiler, and the map
UI is built with React, Vite, and Tailwind.

## Quick start

```bash
cp .env.example .env
docker compose up -d
```

Then open the frontend at http://localhost:5180.

| Service            | URL                     |
|--------------------|-------------------------|
| Frontend           | http://localhost:5180   |
| Backend API        | http://localhost:3040   |
| Geoprocessing API  | http://localhost:3041   |
| TiTiler raster     | http://localhost:3042   |
| PostGIS            | localhost:5440          |

## Repository map

See [CLAUDE.md](CLAUDE.md) for the full architecture, conventions, and the
`.claude/` context engineering package (agents, skills, playbooks, guardrails,
and project memory).

## Data

Source rasters live in `data/` (`elevation.tif`, `slope.tif`). They are converted
to Cloud Optimized GeoTIFFs before TiTiler serves them. See
`.claude/playbooks/add-data-source.md`.
