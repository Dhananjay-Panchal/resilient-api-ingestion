from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str
    token: str
    resource: str = "/v1/events"
    pipeline_name: str = "operational-events"
    state_db: str = "state.db"
    timeout_seconds: int = 30
    max_retries: int = 5

    @classmethod
    def from_env(cls) -> Settings:
        base_url = os.environ.get("API_BASE_URL", "").rstrip("/")
        token = os.environ.get("API_TOKEN", "")
        if not base_url or not token:
            raise ValueError("API_BASE_URL and API_TOKEN are required")
        return cls(
            base_url=base_url,
            token=token,
            resource=os.environ.get("API_RESOURCE", "/v1/events"),
            pipeline_name=os.environ.get("PIPELINE_NAME", "operational-events"),
            state_db=os.environ.get("STATE_DB", "state.db"),
            timeout_seconds=int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.environ.get("MAX_RETRIES", "5")),
        )

