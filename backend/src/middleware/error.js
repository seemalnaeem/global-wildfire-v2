// Central error handler. Consistent shape, no stack traces or internal detail to
// clients. 5xx are logged server-side and returned with a generic message so we
// never leak SQL, paths, or stack frames.
export function errorHandler(err, req, res, next) {
  const status = err.status || 500;
  const code = err.code || (status === 400 ? 'bad_request' : 'internal_error');
  if (status >= 500) {
    console.error(err);
    return res.status(status).json({
      error: { code, message: err.publicMessage || 'Internal server error' },
    });
  }
  res.status(status).json({ error: { code, message: err.publicMessage || err.message } });
}
