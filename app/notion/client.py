"""Notion API client creation and data source resolution.

Verified against the installed notion-client SDK (v3.1.0, Notion-Version
2025-09-03): under this API version, creating a page targets a database's
*data source* ID, not the plain database ID shown in a Notion URL - so
NOTION_DATABASE_ID (the URL-friendly ID a user copies) is resolved to its
data source ID once per run via ``databases.retrieve``.
"""

from __future__ import annotations

from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError


class NotionSyncError(RuntimeError):
    """Raised when the Notion client cannot be created or a sync operation fails."""


def create_notion_client(api_key: str | None) -> Client:
    """Create the Notion client, failing clearly if no API key is configured."""

    if not api_key:
        raise NotionSyncError(
            "NOTION_API_KEY is required for --sync-notion. Add it to .env or your environment."
        )
    return Client(auth=api_key)


def resolve_data_source_id(client: Client, database_id: str | None) -> str:
    """Resolve a Notion database's data source ID, required for page creation."""

    if not database_id:
        raise NotionSyncError(
            "NOTION_DATABASE_ID is required for --sync-notion. Add it to .env or your environment."
        )
    try:
        database = client.databases.retrieve(database_id=database_id)
    except (APIResponseError, RequestTimeoutError) as exc:
        raise NotionSyncError(
            f"Could not access Notion database {database_id!r}: {exc}. Check NOTION_DATABASE_ID "
            "and that the database has been shared with your integration."
        ) from exc

    data_sources = database.get("data_sources") or []
    if not data_sources:
        raise NotionSyncError(f"Notion database {database_id!r} has no data sources.")
    return data_sources[0]["id"]
