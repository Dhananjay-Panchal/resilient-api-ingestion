from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .client import ApiClient
from .store import SqliteStore


@dataclass(frozen=True)
class RunStats:
    pages: int = 0
    fetched: int = 0
    inserted: int = 0
    updated: int = 0


class ApiIngestionPipeline:
    def __init__(
        self,
        client: ApiClient,
        store: SqliteStore,
        *,
        resource: str,
        pipeline_name: str,
    ) -> None:
        self.client = client
        self.store = store
        self.resource = resource
        self.pipeline_name = pipeline_name

    def run(self, *, start_at: str, end_at: str) -> RunStats:
        checkpoint = self.store.get_checkpoint(self.pipeline_name)
        stats = RunStats()
        for page in self.client.iter_pages(
            self.resource,
            start_at=start_at,
            end_at=end_at,
            start_token=checkpoint,
        ):
            normalized = [self._normalize(record) for record in page.records]
            inserted, updated = self.store.save_page(
                self.pipeline_name, normalized, page.next_token
            )
            stats = RunStats(
                pages=stats.pages + 1,
                fetched=stats.fetched + len(normalized),
                inserted=stats.inserted + inserted,
                updated=stats.updated + updated,
            )
        return stats

    @staticmethod
    def _normalize(record: dict[str, Any]) -> dict[str, Any]:
        event_id = str(record.get("id", "")).strip()
        event_type = str(record.get("type", "unknown")).strip() or "unknown"
        occurred_at = record.get("occurredAt")
        if not event_id or not occurred_at:
            raise ValueError("every record requires id and occurredAt")
        return {
            "event_id": event_id,
            "event_type": event_type,
            "event_timestamp_utc": _as_utc(occurred_at),
            "source_updated_at_utc": _as_utc(record["updatedAt"])
            if record.get("updatedAt")
            else None,
            "payload": record,
        }


def _as_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a timezone: {value}")
    return parsed.astimezone(UTC).isoformat()
