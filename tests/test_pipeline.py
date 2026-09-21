from __future__ import annotations

from resilient_api_ingestion.client import ApiPage
from resilient_api_ingestion.pipeline import ApiIngestionPipeline
from resilient_api_ingestion.store import SqliteStore


class FakeClient:
    def __init__(self, pages: list[ApiPage]) -> None:
        self.pages = pages
        self.start_tokens: list[str | None] = []

    def iter_pages(self, resource: str, **kwargs):
        self.start_tokens.append(kwargs["start_token"])
        yield from self.pages


def event(event_id: str, event_type: str = "call") -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "occurredAt": "2026-01-01T08:30:00-05:00",
        "updatedAt": "2026-01-01T14:00:00Z",
    }


def test_pipeline_is_idempotent(tmp_path) -> None:
    store = SqliteStore(tmp_path / "state.db")
    client = FakeClient(
        [ApiPage([event("evt-1"), event("evt-2")], "page-2"), ApiPage([event("evt-3")], None)]
    )
    pipeline = ApiIngestionPipeline(
        client,
        store,
        resource="/v1/events",
        pipeline_name="events",
    )

    first = pipeline.run(start_at="2026-01-01T00:00:00Z", end_at="2026-01-02T00:00:00Z")
    second = pipeline.run(start_at="2026-01-01T00:00:00Z", end_at="2026-01-02T00:00:00Z")

    assert first.inserted == 3
    assert second.updated == 3
    assert store.event_count() == 3
    assert store.get_checkpoint("events") is None


def test_pipeline_resumes_from_saved_token(tmp_path) -> None:
    store = SqliteStore(tmp_path / "state.db")
    store.save_page("events", [], "resume-here")
    client = FakeClient([ApiPage([event("evt-4")], None)])
    pipeline = ApiIngestionPipeline(
        client,
        store,
        resource="/v1/events",
        pipeline_name="events",
    )

    pipeline.run(start_at="2026-01-01T00:00:00Z", end_at="2026-01-02T00:00:00Z")

    assert client.start_tokens == ["resume-here"]

