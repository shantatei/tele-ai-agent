"""Unit tests for the "Last synced" Notion page marker, using fakes only."""

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


def make_paragraph_block(block_id: str, text: str) -> dict[str, object]:
    return {"type": "paragraph", "id": block_id, "paragraph": {"rich_text": [{"plain_text": text}]}}


class FakeChildrenEndpoint:
    def __init__(self, blocks: list[dict[str, object]], error: Exception | None = None) -> None:
        self._blocks = blocks
        self._error = error

    def list(self, block_id: str, page_size: int = 20) -> dict[str, object]:
        if self._error is not None:
            raise self._error
        return {"results": self._blocks}


class FakeBlocksEndpoint:
    def __init__(self, blocks: list[dict[str, object]], list_error=None, update_error=None) -> None:
        self.children = FakeChildrenEndpoint(blocks, list_error)
        self.update_calls: list[tuple[str, dict[str, object]]] = []
        self._update_error = update_error

    def update(self, block_id: str, paragraph: dict[str, object]) -> None:
        if self._update_error is not None:
            raise self._update_error
        self.update_calls.append((block_id, paragraph))


class FakeStatusClient:
    def __init__(self, blocks: list[dict[str, object]], list_error=None, update_error=None) -> None:
        self.blocks = FakeBlocksEndpoint(blocks, list_error, update_error)


class UpdateLastSyncedMarkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timestamp = datetime(2026, 8, 30, 7, 0, tzinfo=timezone.utc)

    def test_does_nothing_when_page_id_missing(self) -> None:
        client = FakeStatusClient(blocks=[])
        update_last_synced_marker(client, None, self.timestamp)
        self.assertEqual(client.blocks.update_calls, [])

    def test_updates_marker_block_when_found(self) -> None:
        blocks = [
            make_paragraph_block("other-block", "Some unrelated paragraph"),
            make_paragraph_block("marker-block", "Last synced: never"),
        ]
        client = FakeStatusClient(blocks=blocks)

        update_last_synced_marker(client, "page-123", self.timestamp)

        self.assertEqual(len(client.blocks.update_calls), 1)
        block_id, paragraph = client.blocks.update_calls[0]
        self.assertEqual(block_id, "marker-block")
        rendered = "".join(rt["text"]["content"] for rt in paragraph["rich_text"])
        self.assertIn("Last synced:", rendered)
        self.assertIn("2026-08-30 07:00 UTC", rendered)

    def test_skips_when_marker_not_found(self) -> None:
        blocks = [make_paragraph_block("other-block", "Some unrelated paragraph")]
        client = FakeStatusClient(blocks=blocks)

        update_last_synced_marker(client, "page-123", self.timestamp)

        self.assertEqual(client.blocks.update_calls, [])

    def test_swallows_list_api_errors(self) -> None:
        client = FakeStatusClient(blocks=[], list_error=make_api_error())
        update_last_synced_marker(client, "page-123", self.timestamp)  # should not raise

    def test_swallows_update_api_errors(self) -> None:
        blocks = [make_paragraph_block("marker-block", "Last synced: never")]
        client = FakeStatusClient(blocks=blocks, update_error=make_api_error())
        update_last_synced_marker(client, "page-123", self.timestamp)  # should not raise


if __name__ == "__main__":
    unittest.main()
