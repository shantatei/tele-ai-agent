"""Unit tests that use fakes and never contact the Notion API."""

from __future__ import annotations

import unittest

import httpx
from notion_client.errors import APIErrorCode, APIResponseError

from app.notion.client import NotionSyncError, create_notion_client, resolve_data_source_id
from app.notion.sync import build_notion_properties, create_notion_page


def make_api_error(status: int = 404, message: str = "boom") -> APIResponseError:
    return APIResponseError(
        code=APIErrorCode.ObjectNotFound,
        status=status,
        message=message,
        headers=httpx.Headers({}),
        raw_body_text="{}",
    )


def make_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "classification": "event",
        "title": "Club Meeting",
        "summary": "Bring your laptop.",
        "date": "2026-08-21",
        "time": "19:00",
        "location": "COM3",
        "deadline": None,
        "importance": "high",
        "chat_name": "Example Chat",
        "telegram_message_id": 1414,
        "message_timestamp": "2026-08-21 12:00:00",
    }
    row.update(overrides)
    return row


class CreateNotionClientTests(unittest.TestCase):
    def test_raises_when_api_key_missing(self) -> None:
        with self.assertRaises(NotionSyncError):
            create_notion_client(None)

    def test_raises_when_api_key_empty(self) -> None:
        with self.assertRaises(NotionSyncError):
            create_notion_client("")


class FakeDatabasesEndpoint:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.last_database_id: str | None = None

    def retrieve(self, database_id: str) -> object:
        self.last_database_id = database_id
        if self._error is not None:
            raise self._error
        return self._result


class FakeNotionClient:
    def __init__(self, databases: FakeDatabasesEndpoint) -> None:
        self.databases = databases


class ResolveDataSourceIdTests(unittest.TestCase):
    def test_raises_when_database_id_missing(self) -> None:
        client = FakeNotionClient(FakeDatabasesEndpoint())
        with self.assertRaises(NotionSyncError):
            resolve_data_source_id(client, None)

    def test_returns_first_data_source_id(self) -> None:
        client = FakeNotionClient(FakeDatabasesEndpoint(result={"data_sources": [{"id": "ds-123", "name": "Inbox"}]}))

        result = resolve_data_source_id(client, "db-abc")

        self.assertEqual(result, "ds-123")
        self.assertEqual(client.databases.last_database_id, "db-abc")

    def test_raises_when_no_data_sources(self) -> None:
        client = FakeNotionClient(FakeDatabasesEndpoint(result={"data_sources": []}))
        with self.assertRaises(NotionSyncError):
            resolve_data_source_id(client, "db-abc")

    def test_wraps_api_error(self) -> None:
        client = FakeNotionClient(FakeDatabasesEndpoint(error=make_api_error(404, "not found")))
        with self.assertRaises(NotionSyncError):
            resolve_data_source_id(client, "db-abc")


class BuildNotionPropertiesTests(unittest.TestCase):
    def test_maps_all_fields(self) -> None:
        properties = build_notion_properties(make_row())

        self.assertEqual(properties["Name"]["title"][0]["text"]["content"], "Club Meeting")
        self.assertEqual(properties["Type"]["select"]["name"], "Event")
        self.assertEqual(properties["Date"]["date"]["start"], "2026-08-21")
        self.assertEqual(properties["Location"]["rich_text"][0]["text"]["content"], "COM3")
        self.assertEqual(properties["Importance"]["select"]["name"], "High")
        self.assertEqual(properties["Source Chat"]["rich_text"][0]["text"]["content"], "Example Chat")
        self.assertEqual(properties["Telegram Message ID"]["rich_text"][0]["text"]["content"], "1414")
        self.assertEqual(properties["Summary"]["rich_text"][0]["text"]["content"], "Bring your laptop.")
        self.assertEqual(properties["Status"]["select"]["name"], "Not Started")
        self.assertEqual(properties["Created"]["date"]["start"], "2026-08-21T12:00:00")
        self.assertNotIn("Deadline", properties)

    def test_includes_deadline_when_present(self) -> None:
        properties = build_notion_properties(make_row(deadline="2026-08-30"))

        self.assertEqual(properties["Deadline"]["date"]["start"], "2026-08-30")

    def test_falls_back_to_chat_name_when_title_missing(self) -> None:
        properties = build_notion_properties(make_row(title=None))

        self.assertEqual(properties["Name"]["title"][0]["text"]["content"], "Example Chat")

    def test_falls_back_to_untitled_when_nothing_available(self) -> None:
        properties = build_notion_properties(make_row(title=None, chat_name=None))

        self.assertEqual(properties["Name"]["title"][0]["text"]["content"], "Untitled")

    def test_unknown_classification_maps_to_information(self) -> None:
        properties = build_notion_properties(make_row(classification="something_new"))

        self.assertEqual(properties["Type"]["select"]["name"], "Information")

    def test_omits_optional_fields_when_absent(self) -> None:
        properties = build_notion_properties(
            make_row(location=None, importance=None, summary=None, deadline=None, message_timestamp=None)
        )

        self.assertNotIn("Location", properties)
        self.assertNotIn("Importance", properties)
        self.assertNotIn("Summary", properties)
        self.assertNotIn("Deadline", properties)
        self.assertNotIn("Created", properties)


class FakePagesEndpoint:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.last_call: dict[str, object] | None = None

    def create(self, **kwargs: object) -> object:
        self.last_call = kwargs
        if self._error is not None:
            raise self._error
        return self._result


class FakePagesClient:
    def __init__(self, pages: FakePagesEndpoint) -> None:
        self.pages = pages


class CreateNotionPageTests(unittest.TestCase):
    def test_returns_page_id_and_uses_data_source_parent(self) -> None:
        pages = FakePagesEndpoint(result={"id": "page-123", "url": "https://notion.so/page-123"})
        client = FakePagesClient(pages)

        page_id = create_notion_page(client, "ds-123", {"Name": {"title": []}})

        self.assertEqual(page_id, "page-123")
        self.assertEqual(pages.last_call["parent"], {"type": "data_source_id", "data_source_id": "ds-123"})

    def test_wraps_api_error(self) -> None:
        pages = FakePagesEndpoint(error=make_api_error(400, "bad request"))
        client = FakePagesClient(pages)

        with self.assertRaises(NotionSyncError):
            create_notion_page(client, "ds-123", {})


if __name__ == "__main__":
    unittest.main()
