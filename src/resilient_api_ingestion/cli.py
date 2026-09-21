from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .client import ApiClient
from .config import Settings
from .pipeline import ApiIngestionPipeline
from .store import SqliteStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a checkpointed API ingestion window")
    parser.add_argument("--start", required=True, help="ISO-8601 inclusive start timestamp")
    parser.add_argument("--end", required=True, help="ISO-8601 exclusive end timestamp")
    args = parser.parse_args()

    settings = Settings.from_env()
    pipeline = ApiIngestionPipeline(
        ApiClient(
            settings.base_url,
            settings.token,
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
        ),
        SqliteStore(settings.state_db),
        resource=settings.resource,
        pipeline_name=settings.pipeline_name,
    )
    print(json.dumps(asdict(pipeline.run(start_at=args.start, end_at=args.end)), indent=2))


if __name__ == "__main__":
    main()

