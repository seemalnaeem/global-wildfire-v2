---
name: create-api-endpoint
description: Add an Express REST endpoint with validation, shared pool query, and error handling. Use for non-tile JSON API routes on the backend.
---

# Create an API endpoint

1. **Route**: add to `backend/src/routes/<area>.js`, mount in `app.js`.
2. **Validate**: use a `shared/js` validator in middleware before the controller.
3. **Controller**: `backend/src/controllers/<area>.js`. Query via the shared pool
   (`backend/src/db/pool.js`), parameterized only.
4. **Respond**: JSON on success. On error, `next(err)` to the central handler which
   returns `{ error: { code, message } }`.
5. **Reuse**: pull constants and formatters from `shared/js`. Do not duplicate.

## Template
```js
// controllers/area.js
export async function getThing(req, res, next) {
  try {
    const { rows } = await pool.query('SELECT id, name FROM thing WHERE id = $1', [req.params.id]);
    if (!rows[0]) return res.status(404).json({ error: { code: 'not_found', message: 'thing not found' } });
    res.json(rows[0]);
  } catch (err) { next(err); }
}
```

## Verify
`curl :3040/<route>` returns the expected shape and status codes.
