"""Unit tests for the "Last synced" database description marker, fakes only."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx
from notion_client.errors import APIErrorCode, APIResponseError

from app.notion.status import update_last_synced_marker


def make_api_error() -> APIResponseError:
    return APIResponseError(
        code=APIErrorCode.ObjectNotFound,
        status=404,
        message="boom",
        headers=httpx.Headers({}),
        raw_body_text="{}",
    )


def make_description(text: str | None) -> list[dict[str, object]]:
    if text is None:
        return []
    return [{"plain_text": text}]


class FakeDatabasesEndpoint:
    def __init__(self, description_text: str | None, retrieve_error=None, update_error=None) -> None:
        self._description = make_description(description_text)
        self._retrieve_error = retrieve_error
        self._update_error = update_error
        self.update_calls: list[tuple[str, list[dict[str, object]]]] = []

    def retrieve(self, database_id: str) -> dict[str, object]:
        if self._retrieve_error is not None:
            raise self._retrieve_error
        return {"description": self._description}

    def update(self, database_id: str, description: list[dict[str, object]]) -> None:
        if self._update_error is not None:
            raise self._update_error
        self.update_calls.append((database_id, description))


class FakeStatusClient:
    def __init__(self, description_text: str | None = "", retrieve_error=None, update_error=None) -> None:
        self.databases = FakeDatabasesEndpoint(description_text, retrieve_error, update_error)


def rendered_text(description: list[dict[str, object]]) -> str:
    return "".join(rt["text"]["content"] for rt in description)


class UpdateLastSyncedMarkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timestamp = datetime(2026, 8, 30, 7, 0, tzinfo=timezone.utc)

    def test_does_nothing_when_database_id_missing(self) -> None:
        client = FakeStatusClient()
        update_last_synced_marker(client, None, self.timestamp)
        self.assertEqual(client.databases.update_calls, [])

    def test_appends_marker_to_existing_description(self) -> None:
        client = FakeStatusClient(description_text="AI-classified items synced from Telegram.")

        update_last_synced_marker(client, "db-123", self.timestamp)

        self.assertEqual(len(client.databases.update_calls), 1)
        database_id, description = client.databases.update_calls[0]
        self.assertEqual(database_id, "db-123")
        text = rendered_text(description)
        self.assertTrue(text.startswith("AI-classified items synced from Telegram."))
        self.assertIn("Last synced: 2026-08-30 15:00 SGT", text)  # 07:00 UTC + 8h

    def test_replaces_previous_marker_instead_of_accumulating(self) -> None:
        client = FakeStatusClient(
            description_text="AI-classified items synced from Telegram. — Last synced: 2026-08-29 09:00 SGT"
        )

        update_last_synced_marker(client, "db-123", self.timestamp)

        _, description = client.databases.update_calls[0]
        text = rendered_text(description)
        self.assertEqual(text.count("Last synced:"), 1)
        self.assertEqual(
            text, "AI-classified items synced from Telegram. — Last synced: 2026-08-30 15:00 SGT"
        )

    def test_handles_empty_description(self) -> None:
        client = FakeStatusClient(description_text=None)

        update_last_synced_marker(client, "db-123", self.timestamp)

        _, description = client.databases.update_calls[0]
        self.assertEqual(rendered_text(description), "Last synced: 2026-08-30 15:00 SGT")

    def test_converts_to_singapore_time_across_a_day_boundary(self) -> None:
        late_utc = datetime(2026, 8, 30, 20, 30, tzinfo=timezone.utc)  # rolls to next day in SGT
        client = FakeStatusClient(description_text="")

        update_last_synced_marker(client, "db-123", late_utc)

        _, description = client.databases.update_calls[0]
        self.assertIn("2026-08-31 04:30 SGT", rendered_text(description))

    def test_swallows_retrieve_api_errors(self) -> None:
        client = FakeStatusClient(retrieve_error=make_api_error())
        update_last_synced_marker(client, "db-123", self.timestamp)  # should not raise

    def test_swallows_update_api_errors(self) -> None:
        client = FakeStatusClient(description_text="Some description.", update_error=make_api_error())
        update_last_synced_marker(client, "db-123", self.timestamp)  # should not raise


if __name__ == "__main__":
    unittest.main()
