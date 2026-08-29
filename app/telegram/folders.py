"""Telegram folder (dialog filter) discovery and per-folder chat resolution."""

from __future__ import annotations

from typing import Any

from telethon.errors import RPCError
from telethon.tl.functions.messages import GetDialogFiltersRequest


class TelegramFolderError(RuntimeError):
    """Raised when a folder cannot be found or its chats cannot be resolved."""


def _filter_title(dialog_filter: Any) -> str | None:
    """Return a folder's title, handling both plain-string and rich-text forms."""

    title = getattr(dialog_filter, "title", None)
    if title is None:
        return None
    text = getattr(title, "text", None)
    return text if text is not None else str(title)


async def get_folder_chats(client: Any, folder_name: str) -> list[Any]:
    """Return the chat entities included in the named Telegram folder.

    Folders are implemented as "dialog filters" and are not exposed through
    the regular dialog list, so this issues Telethon's raw API request.
    """

    if not folder_name:
        raise TelegramFolderError("A non-empty folder name is required.")

    try:
        result = await client(GetDialogFiltersRequest())
    except (RPCError, OSError) as exc:
        raise TelegramFolderError(f"Could not list Telegram folders: {exc}") from exc

    filters = getattr(result, "filters", result)
    target = folder_name.strip().lower()
    match = next(
        (f for f in filters if (_filter_title(f) or "").strip().lower() == target),
        None,
    )
    if match is None:
        raise TelegramFolderError(f"No Telegram folder named {folder_name!r} was found.")

    chats: list[Any] = []
    for peer in getattr(match, "include_peers", []):
        try:
            chats.append(await client.get_entity(peer))
        except (RPCError, OSError, ValueError, TypeError) as exc:
            raise TelegramFolderError(
                f"Could not resolve a chat in folder {folder_name!r}: {exc}"
            ) from exc
    return chats
