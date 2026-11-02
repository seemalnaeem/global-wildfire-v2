# Conventions (style and structure)

## Writing
- No em-dashes anywhere (code, comments, docs, UI). Use commas or parentheses.
- Plain, humanized copy. Short sentences.

## Code reuse
- Shared JS helpers in `shared/js`, shared Python in `shared/py`.
- Constants (SRIDs, tile size, layer names) live once in `shared`. Import them.
- If you write the same logic twice, move it to `shared` and import.

## Naming
- SQL: `snake_case`, PK `id`, geometry `geom`.
- JS: `camelCase` for vars, `PascalCase` for React components.
- Python: `snake_case`, modules lowercase.
- Files: kebab-case for configs and docs, match language norms for source.

## Frontend
- Tailwind utilities, no inline styles unless dynamic.
- Icons from `react-icons`.
- API base URLs from `import.meta.env`, never hardcoded.

## Backend
- One concern per middleware file. Routes thin, logic in controllers.
- Errors go through the central handler as `{ error: { code, message } }`.

## Geospatial
- Store 4326, tile 3857. GiST index every geometry column.
- Vectors as MVT (`ST_AsMVT`), rasters as COG via TiTiler.
