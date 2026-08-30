"""Keep a "Last synced" marker in the Telegram AI Inbox database's own description
up to date - the text shown right under the database's title in Notion.

Appends/replaces a trailing " — Last synced: <timestamp>" segment on the database's
``description`` field, preserving whatever descriptive text was there originally.
Idempotent: re-running it replaces only the previously-appended marker, it never
accumulates duplicates. Verified against the installed notion-client SDK (v3.1.0):
``client.databases.update(database_id=..., description=[...])``.

The displayed timestamp is always converted to Singapore time (UTC+8), regardless
of what timezone the caller's ``timestamp`` argument is in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError

MARKER_PREFIX = "Last synced:"
SEPARATOR = " — "
SINGAPORE_TZ = timezone(timedelta(hours=8))


def _strip_existing_marker(text: str) -> str:
    idx = text.find(MARKER_PREFIX)
    if idx == -1:
        return text.strip()
    return text[:idx].rstrip(" -—").strip()


def update_last_synced_marker(client: Client, database_id: str | None, timestamp: datetime) -> None:
    """Update the database description's trailing "Last synced: ..." segment.

    This is cosmetic status text, not part of the data pipeline - any failure
    (missing database ID, API error) is swallowed after a printed note rather
    than failing the whole sync run.
    """

    if not database_id:
        return
    try:
        database = client.databases.retrieve(database_id=database_id)
        existing = database.get("description") or []
        current_text = "".join(rt.get("plain_text", "") for rt in existing)
        base_text = _strip_existing_marker(current_text)

        timestamp_text = timestamp.astimezone(SINGAPORE_TZ).strftime("%Y-%m-%d %H:%M SGT")
        marker_text = f"{MARKER_PREFIX} {timestamp_text}"
        new_text = f"{base_text}{SEPARATOR}{marker_text}" if base_text else marker_text

        client.databases.update(
            database_id=database_id,
            description=[{"type": "text", "text": {"content": new_text}}],
        )
    except (APIResponseError, RequestTimeoutError) as exc:
        print(f"  Note: could not update the Notion database description marker: {exc}")
