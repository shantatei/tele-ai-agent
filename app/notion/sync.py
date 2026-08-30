"""Map AI results to Notion page properties and create pages in the Notion inbox."""

from __future__ import annotations

from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError

from app.notion.client import NotionSyncError

_TYPE_LABELS = {
    "event": "Event",
    "task": "Task",
    "important": "Important",
    "information": "Information",
}
_IMPORTANCE_LABELS = {"low": "Low", "medium": "Medium", "high": "High"}


def _rich_text(value: str) -> dict[str, Any]:
    return {"rich_text": [{"text": {"content": value}}]}


def build_notion_properties(row: dict[str, Any]) -> dict[str, Any]:
    """Map one joined ai_results+messages row to Notion property values.

    ``row`` must have: classification, title, summary, date, time, location,
    deadline, importance, chat_name, telegram_message_id, message_timestamp.
    """

    title = row.get("title") or row.get("chat_name") or "Untitled"
    properties: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Type": {"select": {"name": _TYPE_LABELS.get(row["classification"], "Information")}},
        "Status": {"select": {"name": "Not Started"}},
    }
    if row.get("date"):
        properties["Date"] = {"date": {"start": row["date"]}}
    if row.get("deadline"):
        properties["Deadline"] = {"date": {"start": row["deadline"]}}
    if row.get("location"):
        properties["Location"] = _rich_text(row["location"])
    if row.get("importance"):
        properties["Importance"] = {
            "select": {"name": _IMPORTANCE_LABELS.get(row["importance"], row["importance"].capitalize())}
        }
    if row.get("chat_name"):
        properties["Source Chat"] = _rich_text(row["chat_name"])
    if row.get("telegram_message_id") is not None:
        properties["Telegram Message ID"] = _rich_text(str(row["telegram_message_id"]))
    if row.get("summary"):
        properties["Summary"] = _rich_text(row["summary"])
    if row.get("message_timestamp"):
        properties["Created"] = {"date": {"start": str(row["message_timestamp"]).replace(" ", "T")}}
    return properties


def create_notion_page(client: Client, data_source_id: str, properties: dict[str, Any]) -> str:
    """Create a Notion page in the given data source and return its page ID."""

    try:
        page = client.pages.create(
            parent={"type": "data_source_id", "data_source_id": data_source_id},
            properties=properties,
        )
    except (APIResponseError, RequestTimeoutError) as exc:
        raise NotionSyncError(f"Failed to create Notion page: {exc}") from exc
    return page["id"]
