"""Telethon client creation and interactive authentication."""

from __future__ import annotations

from telethon import TelegramClient
from telethon.errors import RPCError

from app.config.settings import Settings


class TelegramAuthenticationError(RuntimeError):
    """Raised when Telegram cannot authenticate the local user session."""


def create_client(settings: Settings) -> TelegramClient:
    """Create an unconnected Telethon client using environment-backed settings."""

    return TelegramClient(
        settings.telegram_session_name,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )


async def authenticate_client(client: TelegramClient) -> TelegramClient:
    """Connect and perform Telethon's standard interactive sign-in when needed."""

    try:
        await client.start()
    except (RPCError, OSError, ValueError) as exc:
        await client.disconnect()
        raise TelegramAuthenticationError(
            "Unable to authenticate with Telegram. Check your network and API "
            "credentials, then complete the interactive sign-in prompts."
        ) from exc
    return client
