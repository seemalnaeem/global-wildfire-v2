"""Object storage seam.

Phase 1 stores originals on the local volume. The interface matches S3 so a MinIO
backend drops in later without changing callers. Set STORAGE_BACKEND=s3 then.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

DATA_DIR = os.environ.get("DATA_DIR", "/data")
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
# Root for stored objects on the local volume. Kept apart from source rasters.
OBJSTORE_ROOT = os.path.join(DATA_DIR, "objstore")


@dataclass
class StoredObject:
    uri: str          # backend-agnostic key, for example 'raw/firms/2026/x.csv'
    bytes: int
    checksum: str     # sha256 hex
    content_type: str


class LocalStorage:
    """Writes objects under DATA_DIR/objstore. uri is the key relative to root."""

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> StoredObject:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return StoredObject(
            uri=key,
            bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
            content_type=content_type,
        )

    def path_for(self, key: str) -> str:
        return self._path(key)

    def _path(self, key: str) -> str:
        path = os.path.normpath(os.path.join(OBJSTORE_ROOT, key))
        if not path.startswith(os.path.abspath(OBJSTORE_ROOT)):
            raise ValueError("key escapes object store root")
        return path


def get_storage():
    """Factory. Returns the configured backend. Only 'local' exists in Phase 1."""
    if STORAGE_BACKEND == "local":
        return LocalStorage()
    raise NotImplementedError(f"storage backend '{STORAGE_BACKEND}' not wired yet")
