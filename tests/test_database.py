"""Unit tests for local persistence. Uses an in-memory SQLite database only."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app.ai.schemas import MessageClassification
from app.database.database import get_connection
from app.database.repository import (
    find_or_create_message,
    get_ai_result,
    get_unsynced_ai_results,
    record_notion_sync,
    store_ai_result,
)


def make_message(message_id: int = 1, chat_id: int = 100, text: str = "Hello") -> dict[str, object]:
    return {
        "message_id": message_id,
        "chat_id": chat_id,
        "chat_name": "Example Chat",
        "sender_name": "Ada",
        "message_text": text,
        "timestamp": datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
    }


class SchemaTests(unittest.TestCase):
    def test_expected_tables_are_created(self) -> None:
        connection = get_connection(":memory:")
        try:
            tables = {
                row["name"]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            self.assertTrue({"messages", "ai_results", "notion_sync"}.issubset(tables))
        finally:
            connection.close()


class FindOrCreateMessageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_connection(":memory:")

    def tearDown(self) -> None:
        self.connection.close()

    def test_new_message_is_created_and_unprocessed(self) -> None:
        message_row_id, already_processed = find_or_create_message(self.connection, make_message())

        self.assertIsInstance(message_row_id, int)
        self.assertFalse(already_processed)

    def test_same_message_returns_same_row_without_duplicate_insert(self) -> None:
        message = make_message()

        first_id, _ = find_or_create_message(self.connection, message)
        second_id, second_processed = find_or_create_message(self.connection, message)

        self.assertEqual(first_id, second_id)
        self.assertFalse(second_processed)
        count = self.connection.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
        self.assertEqual(count, 1)

    def test_different_chats_with_same_telegram_id_are_distinct(self) -> None:
        first_id, _ = find_or_create_message(self.connection, make_message(message_id=5, chat_id=1))
        second_id, _ = find_or_create_message(self.connection, make_message(message_id=5, chat_id=2))

        self.assertNotEqual(first_id, second_id)


class AIResultPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_connection(":memory:")

    def tearDown(self) -> None:
        self.connection.close()

    def test_get_ai_result_returns_none_before_processing(self) -> None:
        message_row_id, _ = find_or_create_message(self.connection, make_message())

        self.assertIsNone(get_ai_result(self.connection, message_row_id))

    def test_store_ai_result_round_trips_all_fields(self) -> None:
        message_row_id, _ = find_or_create_message(self.connection, make_message())
        classification = MessageClassification(
            classification="event",
            title="Club Meeting",
            summary="Bring your laptop.",
            date="2026-08-21",
            time="19:00",
            location="COM3",
            deadline=None,
            importance="high",
        )

        store_ai_result(self.connection, message_row_id, classification)
        stored = get_ai_result(self.connection, message_row_id)

        self.assertEqual(stored, classification)

    def test_message_is_marked_processed_after_storing_result(self) -> None:
        message_row_id, _ = find_or_create_message(self.connection, make_message())
        store_ai_result(self.connection, message_row_id, MessageClassification(classification="ignore"))

        _, already_processed = find_or_create_message(self.connection, make_message())

        self.assertTrue(already_processed)

    def test_reprocessing_avoided_across_simulated_runs(self) -> None:
        message = make_message()
        message_row_id, already_processed = find_or_create_message(self.connection, message)
        self.assertFalse(already_processed)
        store_ai_result(self.connection, message_row_id, MessageClassification(classification="task", title="Do X"))

        # Simulate a second run fetching the same message again.
        second_row_id, already_processed_again = find_or_create_message(self.connection, message)

        self.assertEqual(message_row_id, second_row_id)
        self.assertTrue(already_processed_again)
        cached = get_ai_result(self.connection, second_row_id)
        self.assertEqual(cached.title, "Do X")


class NotionSyncPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_connection(":memory:")

    def tearDown(self) -> None:
        self.connection.close()

    def _store_result(self, message_id: int, classification: MessageClassification) -> int:
        message_row_id, _ = find_or_create_message(self.connection, make_message(message_id=message_id))
        store_ai_result(self.connection, message_row_id, classification)
        return self.connection.execute(
            "SELECT id FROM ai_results WHERE message_id = ?", (message_row_id,)
        ).fetchone()["id"]

    def test_ignore_results_are_excluded(self) -> None:
        self._store_result(1, MessageClassification(classification="ignore"))

        self.assertEqual(get_unsynced_ai_results(self.connection), [])

    def test_non_ignore_results_are_pending_by_default(self) -> None:
        ai_result_id = self._store_result(1, MessageClassification(classification="event", title="Meeting"))

        pending = get_unsynced_ai_results(self.connection)

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], ai_result_id)
        self.assertEqual(pending[0]["title"], "Meeting")
        self.assertEqual(pending[0]["chat_name"], "Example Chat")

    def test_synced_results_are_excluded_from_pending(self) -> None:
        ai_result_id = self._store_result(1, MessageClassification(classification="task", title="Do X"))
        record_notion_sync(self.connection, ai_result_id, "notion-page-123")

        self.assertEqual(get_unsynced_ai_results(self.connection), [])

    def test_only_unsynced_results_are_returned_among_several(self) -> None:
        synced_id = self._store_result(1, MessageClassification(classification="task", title="Synced"))
        pending_id = self._store_result(2, MessageClassification(classification="event", title="Pending"))
        record_notion_sync(self.connection, synced_id, "notion-page-1")

        pending = get_unsynced_ai_results(self.connection)

        self.assertEqual([row["id"] for row in pending], [pending_id])


if __name__ == "__main__":
    unittest.main()
