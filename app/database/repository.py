"""Message and AI-result persistence: tracks what has already been processed.

The core rule (per the Notion spec's Telegram Layer design decision): never
re-run AI classification on a message that has already been processed. Callers
should use ``find_or_create_message`` to check/register a message, and only
call the AI layer when it reports ``already_processed=False``.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from app.ai.schemas import MessageClassification


def find_or_create_message(connection: sqlite3.Connection, message: dict[str, Any]) -> tuple[int, bool]:
    """Return ``(message_row_id, already_processed)`` for a structured Telegram message.

    Inserts a new ``messages`` row (with ``processed = 0``) the first time a
    given ``(chat_id, telegram_message_id)`` pair is seen; subsequent calls
    return the existing row instead of inserting a duplicate.
    """

    row = connection.execute(
        "SELECT id, processed FROM messages WHERE chat_id = ? AND telegram_message_id = ?",
        (message["chat_id"], message["message_id"]),
    ).fetchone()
    if row is not None:
        return row["id"], bool(row["processed"])

    timestamp = message.get("timestamp")
    cursor = connection.execute(
        """
        INSERT INTO messages (telegram_message_id, chat_id, chat_name, sender, message_text, timestamp, processed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (
            message["message_id"],
            message["chat_id"],
            message.get("chat_name"),
            message.get("sender_name"),
            message.get("message_text"),
            timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        ),
    )
    connection.commit()
    return cursor.lastrowid, False


def get_ai_result(connection: sqlite3.Connection, message_row_id: int) -> MessageClassification | None:
    """Return the most recent stored classification for a message, if any."""

    row = connection.execute(
        "SELECT * FROM ai_results WHERE message_id = ? ORDER BY id DESC LIMIT 1",
        (message_row_id,),
    ).fetchone()
    if row is None:
        return None
    return MessageClassification(
        classification=row["classification"],
        title=row["title"],
        summary=row["summary"],
        date=row["date"],
        time=row["time"],
        location=row["location"],
        deadline=row["deadline"],
        importance=row["importance"],
    )


def store_ai_result(connection: sqlite3.Connection, message_row_id: int, result: MessageClassification) -> int:
    """Persist a classification result and mark its message as processed."""

    cursor = connection.execute(
        """
        INSERT INTO ai_results
            (message_id, classification, title, summary, date, time, location, deadline, importance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_row_id,
            result.classification,
            result.title,
            result.summary,
            result.date,
            result.time,
            result.location,
            result.deadline,
            result.importance,
        ),
    )
    connection.execute("UPDATE messages SET processed = 1 WHERE id = ?", (message_row_id,))
    connection.commit()
    return cursor.lastrowid


def get_unsynced_ai_results(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return ai_results (joined with their source message) that are not classified
    as ``ignore`` and have no row yet in ``notion_sync`` - i.e. still pending sync."""

    rows = connection.execute(
        """
        SELECT ai_results.*, messages.chat_name AS chat_name,
               messages.telegram_message_id AS telegram_message_id,
               messages.timestamp AS message_timestamp
        FROM ai_results
        JOIN messages ON ai_results.message_id = messages.id
        WHERE ai_results.classification != 'ignore'
          AND NOT EXISTS (
              SELECT 1 FROM notion_sync WHERE notion_sync.ai_result_id = ai_results.id
          )
        ORDER BY ai_results.id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def record_notion_sync(connection: sqlite3.Connection, ai_result_id: int, notion_page_id: str) -> None:
    """Record a successful sync so the same ai_result is never sent to Notion twice."""

    connection.execute(
        "INSERT INTO notion_sync (ai_result_id, notion_page_id, synced, synced_at) VALUES (?, ?, 1, datetime('now'))",
        (ai_result_id, notion_page_id),
    )
    connection.commit()
