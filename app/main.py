"""Command-line entry point for Phase 1: Telegram to Terminal."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone

from app.config.settings import SettingsError, load_settings
from app.telegram.client import TelegramAuthenticationError, authenticate_client, create_client
from app.telegram.reader import TelegramReaderError, get_messages


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp, accepting a trailing ``Z`` for UTC."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Timestamp must be ISO 8601, for example 2026-08-16T01:30:00+00:00."
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read Telegram messages to the terminal.")
    parser.add_argument("--chat", help="Chat username, ID, or invite link. Defaults to TELEGRAM_TEST_CHAT.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum messages to retrieve (default: 20).")
    parser.add_argument("--after-id", type=int, help="Only retrieve messages with a greater message ID.")
    parser.add_argument("--after-timestamp", type=parse_timestamp, help="Only retrieve messages after an ISO 8601 timestamp.")
    return parser


def print_messages(messages: list[dict[str, object]], chat_identifier: str | int) -> None:
    """Render structured messages in a deliberately simple terminal format."""

    print("=" * 40)
    print("Tele AI Agent — Telegram Reader")
    print("=" * 40)
    print(f"\nChat: {messages[0]['chat_name'] if messages else chat_identifier}")
    if not messages:
        print("\nNo messages matched the requested filters.")
        return
    for message in messages:
        timestamp = message["timestamp"]
        timestamp_text = timestamp.isoformat(sep=" ") if isinstance(timestamp, datetime) else "Unknown"
        print(f"\nMessage ID: {message['message_id']}")
        print(f"Sender: {message['sender_name'] or 'Unknown'}")
        print(f"Timestamp: {timestamp_text}")
        print("Message:")
        print(message["message_text"])
        print("\n" + "-" * 40)


async def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    chat_identifier = args.chat or settings.telegram_test_chat
    if not chat_identifier:
        raise SettingsError("Set TELEGRAM_TEST_CHAT in .env or provide --chat.")

    client = create_client(settings)
    try:
        await authenticate_client(client)
        messages = await get_messages(
            client,
            chat_identifier,
            limit=args.limit,
            after_message_id=args.after_id,
            after_timestamp=args.after_timestamp,
        )
        print_messages(messages, chat_identifier)
    finally:
        await client.disconnect()


def main() -> int:
    args = build_parser().parse_args()
    try:
        asyncio.run(run(args))
    except (SettingsError, TelegramAuthenticationError, TelegramReaderError) as exc:
        print(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
