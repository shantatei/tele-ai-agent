"""Fetch every announcement from the Notion Telegram AI Inbox for the desktop widget.

Reuses the already-tested app.config.settings / app.notion.client modules from the
main project rather than duplicating Notion connection logic. Prints a JSON array to
stdout - the Übersicht widget's command output - or {"error": "..."} on failure, so
the widget can render a friendly state either way instead of crashing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/Users/shantatei/Documents/Personal Projects/Telegram AI Agent")

from app.config.settings import load_settings
from app.notion.client import NotionSyncError, create_notion_client, resolve_data_source_id

PAGE_SIZE = 100


def fetch_all_events() -> list[dict[str, object]]:
    """Fetch every synced row (no date filtering), ordered by when the underlying
    Telegram message was actually sent (most recently sent first) - not by the
    event's own Date/Deadline, which can be arbitrarily far in the future or past."""

    settings = load_settings()
    client = create_notion_client(settings.notion_api_key)
    data_source_id = resolve_data_source_id(client, settings.notion_database_id)

    events = []
    start_cursor = None
    while True:
        query_args: dict[str, object] = {"data_source_id": data_source_id, "page_size": PAGE_SIZE}
        if start_cursor:
            query_args["start_cursor"] = start_cursor
        result = client.data_sources.query(**query_args)

        for page in result["results"]:
            props = page["properties"]
            title_parts = props["Name"]["title"]
            name = title_parts[0]["plain_text"] if title_parts else "Untitled"
            type_select = props["Type"]["select"]
            importance_select = props["Importance"]["select"]
            location_rich = props["Location"]["rich_text"]
            summary_rich = props["Summary"]["rich_text"]
            date_prop = props["Date"]["date"]
            deadline_prop = props["Deadline"]["date"]
            sent_prop = props["Created"]["date"]
            source_chat_rich = props["Source Chat"]["rich_text"]

            date_str = date_prop["start"] if date_prop else None
            deadline_str = deadline_prop["start"] if deadline_prop else None
            # "Created" holds the original Telegram message timestamp (set by
            # app/notion/sync.py), not Notion's own page-creation time. Rows
            # synced before that fix won't have it, so fall back to the page's
            # own created_time rather than sorting them to the very bottom.
            sort_key = (sent_prop["start"] if sent_prop else None) or page["created_time"]

            events.append(
                {
                    "name": name,
                    "type": type_select["name"] if type_select else "Information",
                    "importance": importance_select["name"] if importance_select else None,
                    "location": location_rich[0]["plain_text"] if location_rich else None,
                    "summary": summary_rich[0]["plain_text"] if summary_rich else None,
                    "date": date_str,
                    "deadline": deadline_str,
                    "sourceChat": source_chat_rich[0]["plain_text"] if source_chat_rich else None,
                    "url": page["url"],
                    "_sortKey": sort_key,
                }
            )

        if not result.get("has_more"):
            break
        start_cursor = result["next_cursor"]

    events.sort(key=lambda event: event["_sortKey"], reverse=True)
    for event in events:
        del event["_sortKey"]
    return events


def main() -> None:
    try:
        events = fetch_all_events()
        print(json.dumps({"events": events, "fetchedAt": datetime.now(timezone.utc).isoformat()}))
    except NotionSyncError as exc:
        print(json.dumps({"error": str(exc)}))
    except Exception as exc:  # last-resort guard so the widget never crashes on bad output
        print(json.dumps({"error": f"Unexpected error: {exc}"}))


if __name__ == "__main__":
    main()
