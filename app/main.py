"""Command-line entry point for Phase 1: Telegram to Terminal."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone

from app.ai.processor import AIProcessorError, UsageTotals, classify_message, create_ai_client
from app.ai.schemas import MessageClassification
from app.config.settings import SettingsError, load_settings
from app.telegram.client import TelegramAuthenticationError, authenticate_client, create_client
from app.telegram.folders import TelegramFolderError, get_folder_chats
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
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--chat", help="Chat username, ID, or invite link. Defaults to TELEGRAM_TEST_CHAT.")
    target.add_argument("--folder", help="Telegram folder name; fetches messages from every chat inside it.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum messages to retrieve per chat (default: 20).")
    parser.add_argument("--after-id", type=int, help="Only retrieve messages with a greater message ID.")
    parser.add_argument("--after-timestamp", type=parse_timestamp, help="Only retrieve messages after an ISO 8601 timestamp.")
    parser.add_argument(
        "--ai-filter",
        action="store_true",
        help=(
            "Classify each message with Gemini and print only non-'ignore' results with "
            "extracted details (requires GEMINI_API_KEY)."
        ),
    )
    return parser


def print_app_header() -> None:
    print("=" * 40)
    print("Tele AI Agent — Telegram Reader")
    print("=" * 40)


def print_chat_messages(chat_label: object, messages: list[dict[str, object]]) -> None:
    """Render one chat's structured messages in a deliberately simple terminal format."""

    print(f"\nChat: {chat_label}")
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


def print_ai_results(
    chat_label: object,
    messages: list[dict[str, object]],
    ai_client: object,
    usage_totals: UsageTotals,
) -> None:
    """Classify each message and print only non-'ignore' results with extracted details."""

    print(f"\nChat: {chat_label}")
    shown = 0
    for message in messages:
        result: MessageClassification = classify_message(ai_client, message, usage_totals)
        if result.classification == "ignore":
            continue
        shown += 1
        timestamp = message["timestamp"]
        timestamp_text = timestamp.isoformat(sep=" ") if isinstance(timestamp, datetime) else "Unknown"

        print(f"\n[{result.classification.upper()}] {result.title or '(untitled)'}", end="")
        print(f" (importance: {result.importance})" if result.importance else "")
        for label, value in (
            ("Date", result.date),
            ("Time", result.time),
            ("Location", result.location),
            ("Deadline", result.deadline),
        ):
            if value:
                print(f"  {label}: {value}")
        if result.summary:
            print(f"  Summary: {result.summary}")
        print(f"  Message ID: {message['message_id']} | Sender: {message['sender_name'] or 'Unknown'} | {timestamp_text}")
        print(f"  Original: {message['message_text']}")
        print("-" * 40)

    if shown == 0:
        print("\nNo relevant messages (everything classified as ignore).")


async def run_folder(
    client: object,
    folder_name: str,
    args: argparse.Namespace,
    ai_client: object | None,
    usage_totals: UsageTotals | None,
) -> None:
    chats = await get_folder_chats(client, folder_name)
    print_app_header()
    if not chats:
        print(f"\nFolder '{folder_name}' has no chats.")
        return
    for chat in chats:
        messages = await get_messages(
            client,
            chat,
            limit=args.limit,
            after_message_id=args.after_id,
            after_timestamp=args.after_timestamp,
        )
        chat_label = getattr(chat, "title", None) or getattr(chat, "id", None)
        if ai_client is not None:
            print_ai_results(chat_label, messages, ai_client, usage_totals)
        else:
            print_chat_messages(chat_label, messages)


async def run_chat(
    client: object,
    chat_identifier: object,
    args: argparse.Namespace,
    ai_client: object | None,
    usage_totals: UsageTotals | None,
) -> None:
    messages = await get_messages(
        client,
        chat_identifier,
        limit=args.limit,
        after_message_id=args.after_id,
        after_timestamp=args.after_timestamp,
    )
    print_app_header()
    chat_label = messages[0]["chat_name"] if messages else chat_identifier
    if ai_client is not None:
        print_ai_results(chat_label, messages, ai_client, usage_totals)
    else:
        print_chat_messages(chat_label, messages)


def print_usage_summary(usage_totals: UsageTotals) -> None:
    print("\n" + "=" * 40)
    print("AI usage this run (Gemini free tier)")
    print(f"Input tokens:  {usage_totals.input_tokens}")
    print(f"Output tokens: {usage_totals.output_tokens}")
    print("=" * 40)


async def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    ai_client = create_ai_client(settings.gemini_api_key) if args.ai_filter else None
    usage_totals = UsageTotals() if args.ai_filter else None

    client = create_client(settings)
    try:
        await authenticate_client(client)
        if args.folder:
            await run_folder(client, args.folder, args, ai_client, usage_totals)
        else:
            chat_identifier = args.chat or settings.telegram_test_chat
            if not chat_identifier:
                raise SettingsError("Set TELEGRAM_TEST_CHAT in .env, or provide --chat or --folder.")
            await run_chat(client, chat_identifier, args, ai_client, usage_totals)
        if usage_totals is not None:
            print_usage_summary(usage_totals)
    finally:
        await client.disconnect()


def main() -> int:
    args = build_parser().parse_args()
    try:
        asyncio.run(run(args))
    except (
        SettingsError,
        TelegramAuthenticationError,
        TelegramReaderError,
        TelegramFolderError,
        AIProcessorError,
    ) as exc:
        print(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
