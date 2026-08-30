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


class FakeTopic:
    def __init__(self, id: int, title: str) -> None:
        self.id = id
        self.title = title


class FakeTopicsResult:
    def __init__(self, topics: list[FakeTopic]) -> None:
        self.topics = topics


class FakeReplyTo:
    def __init__(self, forum_topic: bool, reply_to_msg_id: int | None) -> None:
        self.forum_topic = forum_topic
        self.reply_to_msg_id = reply_to_msg_id


class FakeClient:
    def __init__(self, chat: object, messages: list[object], topics: list[FakeTopic] | None = None) -> None:
        self.chat = chat
        self.messages = messages
        self.topics = topics or []
        self.min_id: int | None = None
        self.topics_requested = False

    async def get_entity(self, identifier: object) -> object:
        return self.chat

    def iter_messages(self, chat: object, limit: int, min_id: int) -> object:
        self.min_id = min_id

        async def iterate() -> object:
            for message in self.messages[:limit]:
                yield message

        return iterate()

    async def __call__(self, request: object) -> FakeTopicsResult:
        self.topics_requested = True
        return FakeTopicsResult(self.topics)


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

    async def test_topic_name_defaults_to_none(self) -> None:
        chat = SimpleNamespace(id=42, title="Example Chat")
        message = FakeMessage(id=1, chat_id=42, sender_id=None, message="hi", date=None)

        parsed = await message_to_dict(message, chat)

        self.assertIsNone(parsed["topic_name"])

    async def test_topic_name_is_included_when_provided(self) -> None:
        chat = SimpleNamespace(id=42, title="Example Chat")
        message = FakeMessage(id=1, chat_id=42, sender_id=None, message="hi", date=None)

        parsed = await message_to_dict(message, chat, topic_name="Laundry")

        self.assertEqual(parsed["topic_name"], "Laundry")


class ForumTopicResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolves_topic_name_for_forum_chats(self) -> None:
        chat = SimpleNamespace(id=42, title="Sample Forum", forum=True)
        message = FakeMessage(
            id=3,
            chat_id=42,
            sender_id=None,
            message="D5 done",
            date=datetime(2026, 8, 29, tzinfo=timezone.utc),
            reply_to=FakeReplyTo(forum_topic=True, reply_to_msg_id=3),
        )
        client = FakeClient(chat, [message], topics=[FakeTopic(id=3, title="Laundry")])

        messages = await get_messages(client, "sample forum", limit=20)

        self.assertTrue(client.topics_requested)
        self.assertEqual(messages[0]["topic_name"], "Laundry")

    async def test_non_forum_chats_skip_topic_lookup(self) -> None:
        chat = SimpleNamespace(id=42, title="Regular Chat", forum=False)
        message = FakeMessage(
            id=1, chat_id=42, sender_id=None, message="hi", date=datetime(2026, 8, 29, tzinfo=timezone.utc)
        )
        client = FakeClient(chat, [message], topics=[FakeTopic(id=3, title="Laundry")])

        messages = await get_messages(client, "regular", limit=20)

        self.assertFalse(client.topics_requested)
        self.assertIsNone(messages[0]["topic_name"])

    async def test_message_not_in_a_topic_has_no_topic_name(self) -> None:
        chat = SimpleNamespace(id=42, title="Sample Forum", forum=True)
        message = FakeMessage(
            id=1,
            chat_id=42,
            sender_id=None,
            message="general chat",
            date=datetime(2026, 8, 29, tzinfo=timezone.utc),
            reply_to=None,
        )
        client = FakeClient(chat, [message], topics=[FakeTopic(id=3, title="Laundry")])

        messages = await get_messages(client, "sample forum", limit=20)

        self.assertIsNone(messages[0]["topic_name"])


if __name__ == "__main__":
    unittest.main()
