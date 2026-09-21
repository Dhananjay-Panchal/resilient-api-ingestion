from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SqliteStore:
    """Local state and target store used for the runnable reference project."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
                    pipeline_name TEXT PRIMARY KEY,
                    next_token TEXT,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS operational_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    event_timestamp_utc TEXT NOT NULL,
                    source_updated_at_utc TEXT,
                    payload_json TEXT NOT NULL,
                    loaded_at_utc TEXT NOT NULL
                );
                """
            )

    def get_checkpoint(self, pipeline_name: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT next_token FROM pipeline_checkpoints WHERE pipeline_name = ?",
                (pipeline_name,),
            ).fetchone()
        return row["next_token"] if row else None

    def save_page(
        self,
        pipeline_name: str,
        records: Iterable[dict[str, Any]],
        next_token: str | None,
    ) -> tuple[int, int]:
        now = datetime.now(UTC).isoformat()
        inserted = 0
        updated = 0
        with self._connect() as connection:
            for record in records:
                exists = connection.execute(
                    "SELECT 1 FROM operational_events WHERE event_id = ?",
                    (record["event_id"],),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO operational_events (
                        event_id, event_type, event_timestamp_utc,
                        source_updated_at_utc, payload_json, loaded_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        event_type = excluded.event_type,
                        event_timestamp_utc = excluded.event_timestamp_utc,
                        source_updated_at_utc = excluded.source_updated_at_utc,
                        payload_json = excluded.payload_json,
                        loaded_at_utc = excluded.loaded_at_utc
                    """,
                    (
                        record["event_id"],
                        record["event_type"],
                        record["event_timestamp_utc"],
                        record.get("source_updated_at_utc"),
                        json.dumps(record["payload"], sort_keys=True),
                        now,
                    ),
                )
                if exists:
                    updated += 1
                else:
                    inserted += 1

            if next_token:
                connection.execute(
                    """
                    INSERT INTO pipeline_checkpoints (pipeline_name, next_token, updated_at_utc)
                    VALUES (?, ?, ?)
                    ON CONFLICT(pipeline_name) DO UPDATE SET
                        next_token = excluded.next_token,
                        updated_at_utc = excluded.updated_at_utc
                    """,
                    (pipeline_name, next_token, now),
                )
            else:
                connection.execute(
                    "DELETE FROM pipeline_checkpoints WHERE pipeline_name = ?",
                    (pipeline_name,),
                )
        return inserted, updated

    def event_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM operational_events").fetchone()[0])

