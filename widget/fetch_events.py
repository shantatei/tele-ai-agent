"""Fetch upcoming events/tasks from the Notion Telegram AI Inbox for the desktop widget.

Reuses the already-tested app.config.settings / app.notion.client modules from the
main project rather than duplicating Notion connection logic. Prints a JSON array to
stdout - the Übersicht widget's command output - or {"error": "..."} on failure, so
the widget can render a friendly state either way instead of crashing.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, "/Users/shantatei/Documents/Personal Projects/Telegram AI Agent")

from app.config.settings import load_settings
from app.notion.client import NotionSyncError, create_notion_client, resolve_data_source_id

MAX_EVENTS = 8


def fetch_upcoming_events() -> list[dict[str, object]]:
    settings = load_settings()
    client = create_notion_client(settings.notion_api_key)
    data_source_id = resolve_data_source_id(client, settings.notion_database_id)

    today = date.today().isoformat()
    result = client.data_sources.query(
        data_source_id=data_source_id,
        filter={
            "or": [
                {"property": "Date", "date": {"on_or_after": today}},
                {"property": "Deadline", "date": {"on_or_after": today}},
            ]
        },
        sorts=[{"property": "Date", "direction": "ascending"}],
        page_size=MAX_EVENTS,
    )

    events = []
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
        source_chat_rich = props["Source Chat"]["rich_text"]

        events.append(
            {
                "name": name,
                "type": type_select["name"] if type_select else "Information",
                "importance": importance_select["name"] if importance_select else None,
                "location": location_rich[0]["plain_text"] if location_rich else None,
                "summary": summary_rich[0]["plain_text"] if summary_rich else None,
                "date": date_prop["start"] if date_prop else None,
                "deadline": deadline_prop["start"] if deadline_prop else None,
                "sourceChat": source_chat_rich[0]["plain_text"] if source_chat_rich else None,
                "url": page["url"],
            }
        )
    return events


def main() -> None:
    try:
        events = fetch_upcoming_events()
        print(json.dumps({"events": events, "fetchedAt": datetime.now(timezone.utc).isoformat()}))
    except NotionSyncError as exc:
        print(json.dumps({"error": str(exc)}))
    except Exception as exc:  # last-resort guard so the widget never crashes on bad output
        print(json.dumps({"error": f"Unexpected error: {exc}"}))


if __name__ == "__main__":
    main()
