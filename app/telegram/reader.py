"""Structured Telegram message retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from telethon.errors import RPCError
from telethon.tl.functions.messages import GetForumTopicsRequest


class TelegramReaderError(RuntimeError):
    """Raised when a chat or its messages cannot be read."""


def _display_name(entity: Any) -> str | None:
    """Return a useful display name without assuming a Telegram entity type."""

    title = getattr(entity, "title", None)
    if title:
        return str(title)
    first_name = getattr(entity, "first_name", None)
    last_name = getattr(entity, "last_name", None)
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return full_name or getattr(entity, "username", None)


def _extract_topic_id(message: Any) -> int | None:
    """Return the forum topic ID a message belongs to, if the chat uses forum topics."""

    reply_to = getattr(message, "reply_to", None)
    if reply_to is not None and getattr(reply_to, "forum_topic", False):
        return getattr(reply_to, "reply_to_msg_id", None)
    return None


async def _get_topic_titles(client: Any, chat: Any) -> dict[int, str]:
    """Map topic ID -> title for a forum-enabled chat. Empty dict for ordinary chats."""

    if not getattr(chat, "forum", False):
        return {}
    try:
        result = await client(
            GetForumTopicsRequest(peer=chat, offset_date=None, offset_id=0, offset_topic=0, limit=100)
        )
    except (RPCError, OSError):
        return {}
    return {topic.id: topic.title for topic in result.topics}


async def message_to_dict(
    message: Any, chat: Any, sender: Any | None = None, topic_name: str | None = None
) -> dict[str, Any]:
    """Convert a Telethon message to Phase 1's stable, structured format."""

    if sender is None:
        try:
            sender = await message.get_sender()
        except (AttributeError, RPCError):
            sender = None

    text = getattr(message, "message", None) or getattr(message, "text", None)
    return {
        "message_id": getattr(message, "id", None),
        "chat_id": getattr(message, "chat_id", None) or getattr(chat, "id", None),
        "chat_name": _display_name(chat),
        "topic_name": topic_name,
        "sender_id": getattr(message, "sender_id", None) or getattr(sender, "id", None),
        "sender_name": _display_name(sender) if sender is not None else None,
        "message_text": text if text else "[No text content]",
        "timestamp": getattr(message, "date", None),
    }


async def get_messages(
    client: Any,
    chat_identifier: Any,
    limit: int = 20,
    *,
    after_message_id: int | None = None,
    after_timestamp: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return recent messages newer than optional ID and/or timestamp filters.

    Telegram returns messages newest first. ``after_message_id`` is applied by
    Telegram where possible; timestamps are filtered locally for predictable
    semantics. Returned messages are ordered oldest to newest for terminal use.
    """

    if not chat_identifier:
        raise TelegramReaderError("A non-empty Telegram chat identifier is required.")
    if limit < 1:
        raise TelegramReaderError("Message limit must be at least 1.")
    if after_message_id is not None and after_message_id < 1:
        raise TelegramReaderError("after_message_id must be a positive integer.")
    if after_timestamp is not None and after_timestamp.tzinfo is None:
        after_timestamp = after_timestamp.replace(tzinfo=timezone.utc)

    if isinstance(chat_identifier, str) and chat_identifier.lstrip("-").isdigit():
        chat_identifier = int(chat_identifier)

    try:
        chat = await client.get_entity(chat_identifier)
        topic_titles = await _get_topic_titles(client, chat)
        iterator = client.iter_messages(chat, limit=limit, min_id=after_message_id or 0)
        messages: list[dict[str, Any]] = []
        async for message in iterator:
            message_date = getattr(message, "date", None)
            if after_timestamp is not None and message_date is not None:
                if message_date <= after_timestamp:
                    break
            topic_id = _extract_topic_id(message)
            topic_name = topic_titles.get(topic_id) if topic_id is not None else None
            messages.append(await message_to_dict(message, chat, topic_name=topic_name))
    except (RPCError, OSError, ValueError, TypeError) as exc:
        raise TelegramReaderError(
            f"Could not read chat {chat_identifier!r}. Check that it exists and "
            "that the authenticated account can access it."
        ) from exc

    messages.reverse()
    return messages
