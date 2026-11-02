"""Base connector. Every provider connector follows the same four steps.

  fetch    -> get raw bytes from the provider (or a local sample)
  persist  -> save the original to object storage, register provenance
  validate -> drop rows that fail coordinate/time/quality checks
  load     -> write clean records into PostGIS

run() wires these together and records an ingest_run for audit. Subclasses set
`name`, `kind`, `provider` and implement fetch/parse/load. Keep provider details
inside the connector, never leak them to callers.
"""
from __future__ import annotations

from typing import Any

from app.ingest import repository as repo
from app.storage import get_storage


class BaseConnector:
    name: str = "base"
    kind: str = "api"           # 'api' | 'vector' | 'raster'
    provider: str = "unknown"
    content_type: str = "application/octet-stream"

    def fetch(self, params: dict[str, Any]) -> bytes:
        """Return the raw payload. Subclasses override with provider logic."""
        raise NotImplementedError

    def storage_key(self, params: dict[str, Any]) -> str:
        """Object key for the original. Override to add date/partition prefixes."""
        return f"raw/{self.name}/payload"

    def parse_and_validate(self, raw: bytes) -> list[dict[str, Any]]:
        """Turn raw bytes into clean, validated records. Override per provider."""
        raise NotImplementedError

    def load(self, run_id: int, records: list[dict[str, Any]]) -> int:
        """Write validated records to PostGIS. Return rows written. Override."""
        raise NotImplementedError

    def config(self) -> dict[str, Any]:
        """Non-secret connector config stored in the source registry."""
        return {}

    def run(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        source_id = repo.upsert_source(self.name, self.kind, self.provider, self.config())
        run_id = repo.start_run(source_id, self.name, params)
        try:
            raw = self.fetch(params)
            obj = get_storage().put_bytes(self.storage_key(params), raw, self.content_type)
            repo.register_raw_file(run_id, obj, meta={"params": params})
            records = self.parse_and_validate(raw)
            written = self.load(run_id, records)
            repo.finish_run(run_id, "success", rows_in=len(records), rows_out=written)
            return {"run_id": run_id, "status": "success",
                    "rows_in": len(records), "rows_out": written, "raw_uri": obj.uri}
        except Exception as exc:  # noqa: BLE001 record failure, then re-raise
            repo.finish_run(run_id, "failed", message=str(exc)[:500])
            raise
