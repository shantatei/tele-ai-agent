"""Keep a "Last synced" marker on the Tele AI Agent Notion page up to date.

Finds the marker by its "Last synced:" text prefix rather than a hardcoded block
ID, so it keeps working even if the page is edited and the block gets recreated
with a new ID. Verified against the installed notion-client SDK (v3.1.0): a
paragraph block's text is updated via ``client.blocks.update(block_id=...,
paragraph={"rich_text": [...]})``.

The displayed timestamp is always converted to Singapore time (UTC+8), regardless
of what timezone the caller's ``timestamp`` argument is in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError

MARKER_PREFIX = "Last synced:"
SINGAPORE_TZ = timezone(timedelta(hours=8))


def _find_marker_block_id(client: Client, page_id: str) -> str | None:
    """Search every direct child of the page, not just the first page of results -
    the marker isn't necessarily near the top of a long page."""

    start_cursor = None
    while True:
        list_args: dict[str, object] = {"block_id": page_id, "page_size": 100}
        if start_cursor:
            list_args["start_cursor"] = start_cursor
        result = client.blocks.children.list(**list_args)
        for block in result["results"]:
            if block["type"] != "paragraph":
                continue
            text = "".join(rt.get("plain_text", "") for rt in block["paragraph"]["rich_text"])
            if text.startswith(MARKER_PREFIX):
                return block["id"]
        if not result.get("has_more"):
            return None
        start_cursor = result["next_cursor"]


def update_last_synced_marker(client: Client, page_id: str | None, timestamp: datetime) -> None:
    """Update the page's "Last synced: ..." paragraph, if configured and found.

    This is cosmetic status text, not part of the data pipeline - any failure
    (missing page ID, marker not found, API error) is swallowed after a warning
    rather than failing the whole sync run.
    """

    if not page_id:
        return
    try:
        block_id = _find_marker_block_id(client, page_id)
        if block_id is None:
            print(f"  Note: no '{MARKER_PREFIX}' marker found on the status page; skipping update.")
            return
        timestamp_text = timestamp.astimezone(SINGAPORE_TZ).strftime("%Y-%m-%d %H:%M SGT")
        client.blocks.update(
            block_id=block_id,
            paragraph={
                "rich_text": [
                    {"type": "text", "text": {"content": f"{MARKER_PREFIX} "}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": timestamp_text}},
                ]
            },
        )
    except (APIResponseError, RequestTimeoutError) as exc:
        print(f"  Note: could not update the Notion status page marker: {exc}")
