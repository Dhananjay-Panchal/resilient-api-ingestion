from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar

import requests


@dataclass(frozen=True)
class ApiPage:
    records: list[dict[str, Any]]
    next_token: str | None


class ApiClient:
    """Small API client with bounded retries and token-based pagination."""

    RETRYABLE_STATUS_CODES: ClassVar[set[int]] = {429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: int = 30,
        max_retries: int = 5,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )
        self.sleep = sleep

    def iter_pages(
        self,
        resource: str,
        *,
        start_at: str,
        end_at: str,
        start_token: str | None = None,
    ) -> Iterator[ApiPage]:
        next_token = start_token
        while True:
            params = {"updated_after": start_at, "updated_before": end_at, "limit": 500}
            if next_token:
                params["nextPageToken"] = next_token
            payload = self._get(resource, params=params)
            page = ApiPage(
                records=list(payload.get("items", [])),
                next_token=payload.get("nextPageToken"),
            )
            yield page
            if not page.next_token:
                break
            next_token = page.next_token

    def _get(self, resource: str, *, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{resource.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_seconds)
                if response.status_code not in self.RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response.json()
                last_error = RuntimeError(
                    f"retryable API response {response.status_code}: {response.text[:200]}"
                )
                delay = self._retry_delay(response, attempt)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                delay = min(2**attempt, 30)

            if attempt == self.max_retries:
                break
            self.sleep(delay)

        raise RuntimeError(f"API request failed after retries: {last_error}")

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            if retry_after.isdigit():
                return min(float(retry_after), 60.0)
            try:
                retry_at = parsedate_to_datetime(retry_after)
                return max(0.0, min((retry_at.timestamp() - time.time()), 60.0))
            except (TypeError, ValueError, OverflowError):
                pass
        return float(min(2**attempt, 30))
