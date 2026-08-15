"""Unit tests that use fakes and never contact Telegram."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from app.telegram.reader import get_messages, message_to_dict


class FakeMessage:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)

    async def get_sender(self) -> object | None:
        return getattr(self, "_sender", None)


class FakeClient:
    def __init__(self, chat: object, messages: list[object]) -> None:
        self.chat = chat
        self.messages = messages
        self.min_id: int | None = None

    async def get_entity(self, identifier: object) -> object:
        return self.chat

    def iter_messages(self, chat: object, limit: int, min_id: int) -> object:
        self.min_id = min_id

        async def iterate() -> object:
            for message in self.messages[:limit]:
                yield message

        return iterate()


class MessageParsingTests(unittest.IsolatedAsyncioTestCase):
    async def test_message_is_converted_to_structured_data(self) -> None:
        sender = SimpleNamespace(id=7, first_name="Ada", last_name="Lovelace")
        chat = SimpleNamespace(id=42, title="Example Chat")
        message = FakeMessage(
            id=99,
            chat_id=42,
            sender_id=7,
            message="Hello Telegram",
            date=datetime(2026, 8, 16, 1, 30, tzinfo=timezone.utc),
            _sender=sender,
        )

        parsed = await message_to_dict(message, chat)

        self.assertEqual(parsed["message_id"], 99)
        self.assertEqual(parsed["chat_name"], "Example Chat")
        self.assertEqual(parsed["sender_name"], "Ada Lovelace")
        self.assertEqual(parsed["message_text"], "Hello Telegram")

    async def test_missing_text_and_sender_are_handled(self) -> None:
        chat = SimpleNamespace(id=42, title="Example Chat")
        message = FakeMessage(id=100, chat_id=42, sender_id=None, message=None, date=None)

        parsed = await message_to_dict(message, chat)

        self.assertIsNone(parsed["sender_name"])
        self.assertEqual(parsed["message_text"], "[No text content]")
        self.assertIsNone(parsed["timestamp"])

    async def test_retrieval_applies_id_and_timestamp_filters(self) -> None:
        chat = SimpleNamespace(id=42, title="Example Chat")
        newest = FakeMessage(
            id=12,
            chat_id=42,
            sender_id=None,
            message="newest",
            date=datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc),
        )
        oldest = FakeMessage(
            id=11,
            chat_id=42,
            sender_id=None,
            message="oldest",
            date=datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc),
        )
        client = FakeClient(chat, [newest, oldest])

        messages = await get_messages(
            client,
            "example_chat",
            limit=20,
            after_message_id=10,
            after_timestamp=datetime(2026, 8, 16, 1, 30),
        )

        self.assertEqual(client.min_id, 10)
        self.assertEqual([message["message_id"] for message in messages], [12])


if __name__ == "__main__":
    unittest.main()
