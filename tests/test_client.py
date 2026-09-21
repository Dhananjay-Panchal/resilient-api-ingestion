from __future__ import annotations

from dataclasses import dataclass

from resilient_api_ingestion.client import ApiClient


@dataclass
class FakeResponse:
    status_code: int
    payload: dict
    headers: dict[str, str]
    text: str = ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return next(self.responses)


def test_retries_then_paginates() -> None:
    session = FakeSession(
        [
            FakeResponse(503, {}, {"Retry-After": "0"}, "busy"),
            FakeResponse(200, {"items": [{"id": "1"}], "nextPageToken": "next"}, {}),
            FakeResponse(200, {"items": [{"id": "2"}]}, {}),
        ]
    )
    sleeps: list[float] = []
    client = ApiClient(
        "https://api.example.com",
        "token",
        session=session,
        sleep=sleeps.append,
    )

    pages = list(
        client.iter_pages(
            "/v1/events",
            start_at="2026-01-01T00:00:00Z",
            end_at="2026-01-02T00:00:00Z",
        )
    )

    assert [page.records[0]["id"] for page in pages] == ["1", "2"]
    assert session.calls[-1]["params"]["nextPageToken"] == "next"
    assert sleeps == [0.0]

