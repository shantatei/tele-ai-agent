"""Environment-backed settings for the Telegram reader."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class SettingsError(ValueError):
    """Raised when required application configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Configuration required by the Telegram-only Phase 1 application."""

    telegram_api_id: int
    telegram_api_hash: str
    telegram_test_chat: str | None = None
    telegram_session_name: str = "tele_ai_agent"
    anthropic_api_key: str | None = None
    notion_api_key: str | None = None
    notion_database_id: str | None = None
    notion_status_page_id: str | None = None


def load_settings(env_file: Path | None = None) -> Settings:
    """Load settings from ``.env`` (when present) and process environment variables.

    Explicit environment variables take precedence over values in ``.env``.
    No credential values are logged or returned outside this settings object.
    """

    load_dotenv(dotenv_path=env_file, override=False)

    raw_api_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    test_chat = os.getenv("TELEGRAM_TEST_CHAT", "").strip() or None
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "tele_ai_agent").strip()
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or None
    notion_api_key = os.getenv("NOTION_API_KEY", "").strip() or None
    notion_database_id = os.getenv("NOTION_DATABASE_ID", "").strip() or None
    notion_status_page_id = os.getenv("NOTION_STATUS_PAGE_ID", "").strip() or None

    if not raw_api_id:
        raise SettingsError("TELEGRAM_API_ID is required. Add it to .env or your environment.")
    try:
        api_id = int(raw_api_id)
    except ValueError as exc:
        raise SettingsError("TELEGRAM_API_ID must be an integer.") from exc
    if api_id <= 0:
        raise SettingsError("TELEGRAM_API_ID must be a positive integer.")
    if not api_hash:
        raise SettingsError("TELEGRAM_API_HASH is required. Add it to .env or your environment.")
    if not session_name:
        raise SettingsError("TELEGRAM_SESSION_NAME cannot be empty.")

    return Settings(
        telegram_api_id=api_id,
        telegram_api_hash=api_hash,
        telegram_test_chat=test_chat,
        telegram_session_name=session_name,
        anthropic_api_key=anthropic_api_key,
        notion_api_key=notion_api_key,
        notion_database_id=notion_database_id,
        notion_status_page_id=notion_status_page_id,
    )
