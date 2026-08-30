"""Command-line entry point for Phase 1: Telegram to Terminal."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from app.ai.processor import AIProcessorError, UsageTotals, classify_message, create_ai_client
from app.ai.prompts import is_chat_ignored, load_ignored_chats, load_target_folders
from app.ai.schemas import MessageClassification
from app.config.settings import SettingsError, load_settings
from app.database.database import get_connection
from app.database.repository import (
    find_or_create_message,
    get_ai_result,
    get_unsynced_ai_results,
    record_notion_sync,
    store_ai_result,
)
from app.notion.client import NotionSyncError, create_notion_client, resolve_data_source_id
from app.notion.status import update_last_synced_marker
from app.notion.sync import build_notion_properties, create_notion_page
from app.telegram.client import TelegramAuthenticationError, authenticate_client, create_client
from app.telegram.folders import TelegramFolderError, get_folder_chats
from app.telegram.reader import TelegramReaderError, get_messages


DEFAULT_LOOKBACK = timedelta(days=1)


def resolve_after_timestamp(args: argparse.Namespace) -> datetime | None:
    """Default to the last 24 hours when neither --after-id nor --after-timestamp is
    given, so a plain daily invocation naturally covers "yesterday" without extra
    flags. An explicit --after-id or --after-timestamp always takes precedence."""

    if args.after_id is not None or args.after_timestamp is not None:
        return args.after_timestamp
    return datetime.now(timezone.utc) - DEFAULT_LOOKBACK


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
    target.add_argument(
        "--folder",
        help=(
            "Telegram folder name; fetches messages from every chat inside it. If omitted "
            "along with --chat, falls back to the '## Folders to query' list in template.md "
            "(processing all of them in one run), then to TELEGRAM_TEST_CHAT."
        ),
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum messages to retrieve per chat (default: 20).")
    parser.add_argument("--after-id", type=int, help="Only retrieve messages with a greater message ID.")
    parser.add_argument("--after-timestamp", type=parse_timestamp, help="Only retrieve messages after an ISO 8601 timestamp.")
    parser.add_argument(
        "--ai-filter",
        action="store_true",
        help=(
            "Classify each message with Claude and print only non-'ignore' results with "
            "extracted details (requires ANTHROPIC_API_KEY)."
        ),
    )
    parser.add_argument(
        "--sync-notion",
        action="store_true",
        help=(
            "Sync any not-yet-synced AI results to the Notion database (requires "
            "NOTION_API_KEY and NOTION_DATABASE_ID). Runs after any --ai-filter "
            "processing this invocation, and also picks up results left over from "
            "earlier runs, so it can be used on its own to retry a failed sync."
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
    db_connection: object,
    run_stats: dict[str, int],
    ignored_chats: set[str],
) -> None:
    """Classify each new message (reusing stored results for already-processed ones)
    and print only non-'ignore' results with extracted details. Messages in an ignored
    forum topic are skipped entirely - no database write, no AI call."""

    print(f"\nChat: {chat_label}")
    shown = 0
    skipped_topics = 0
    for message in messages:
        if is_chat_ignored(None, ignored_chats, topic_name=message.get("topic_name")):
            skipped_topics += 1
            continue
        message_row_id, already_processed = find_or_create_message(db_connection, message)
        result: MessageClassification | None = get_ai_result(db_connection, message_row_id) if already_processed else None
        if result is None:
            result = classify_message(ai_client, message, usage_totals)
            store_ai_result(db_connection, message_row_id, result)
            run_stats["classified"] += 1
        else:
            run_stats["cached"] += 1
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
        if skipped_topics and skipped_topics == len(messages):
            print("\nAll messages were in an ignored topic - skipped entirely.")
        else:
            print("\nNo relevant messages (everything classified as ignore).")


async def run_folder(
    client: object,
    folder_name: str,
    args: argparse.Namespace,
    ai_client: object | None,
    usage_totals: UsageTotals | None,
    db_connection: object | None,
    run_stats: dict[str, int],
    ignored_chats: set[str],
) -> None:
    chats = await get_folder_chats(client, folder_name)
    print(f"\n{'=' * 40}\nFolder: {folder_name}\n{'=' * 40}")
    if not chats:
        print(f"\nFolder '{folder_name}' has no chats.")
        return
    for chat in chats:
        chat_label = getattr(chat, "title", None) or getattr(chat, "id", None)
        if ai_client is not None and is_chat_ignored(getattr(chat, "title", None), ignored_chats):
            print(f"\nChat: {chat_label}")
            print("Skipped (ignored chat - no AI call made).")
            continue
        messages = await get_messages(
            client,
            chat,
            limit=args.limit,
            after_message_id=args.after_id,
            after_timestamp=args.after_timestamp,
        )
        if ai_client is not None:
            print_ai_results(chat_label, messages, ai_client, usage_totals, db_connection, run_stats, ignored_chats)
        else:
            print_chat_messages(chat_label, messages)


async def run_chat(
    client: object,
    chat_identifier: object,
    args: argparse.Namespace,
    ai_client: object | None,
    usage_totals: UsageTotals | None,
    db_connection: object | None,
    run_stats: dict[str, int],
    ignored_chats: set[str],
) -> None:
    messages = await get_messages(
        client,
        chat_identifier,
        limit=args.limit,
        after_message_id=args.after_id,
        after_timestamp=args.after_timestamp,
    )
    chat_label = messages[0]["chat_name"] if messages else chat_identifier
    if ai_client is not None and is_chat_ignored(str(chat_label), ignored_chats):
        print(f"\nChat: {chat_label}")
        print("Skipped (ignored chat - no AI call made).")
        return
    if ai_client is not None:
        print_ai_results(chat_label, messages, ai_client, usage_totals, db_connection, run_stats, ignored_chats)
    else:
        print_chat_messages(chat_label, messages)


def print_usage_summary(usage_totals: UsageTotals, run_stats: dict[str, int]) -> None:
    cost = usage_totals.estimated_cost_usd()
    print("\n" + "=" * 40)
    print("AI usage this run")
    print(f"Newly classified: {run_stats['classified']}")
    print(f"Already processed (reused from database): {run_stats['cached']}")
    print(f"Input tokens:  {usage_totals.input_tokens}")
    print(f"Output tokens: {usage_totals.output_tokens}")
    if cost is not None:
        print(f"Estimated cost: ${cost:.4f}")
    print("=" * 40)


def sync_pending_results_to_notion(db_connection: object, notion_client_obj: object, data_source_id: str) -> None:
    """Create a Notion page for every ai_result not yet synced; skip and report
    failures per-item rather than aborting the whole batch."""

    rows = get_unsynced_ai_results(db_connection)
    if not rows:
        print("\nNotion sync: nothing pending.")
        return
    print(f"\nNotion sync: {len(rows)} pending item(s)...")
    synced = 0
    failed = 0
    for row in rows:
        try:
            properties = build_notion_properties(row)
            page_id = create_notion_page(notion_client_obj, data_source_id, properties)
            record_notion_sync(db_connection, row["id"], page_id)
            synced += 1
        except NotionSyncError as exc:
            print(f"  Failed to sync ai_result {row['id']}: {exc}")
            failed += 1
    print(f"Notion sync complete: {synced} synced, {failed} failed.")


async def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    original_after_timestamp = args.after_timestamp
    args.after_timestamp = resolve_after_timestamp(args)
    if args.after_timestamp is not None and original_after_timestamp is None and args.after_id is None:
        print(
            "No --after-id/--after-timestamp given; defaulting to the last 24 hours "
            f"(since {args.after_timestamp.isoformat(sep=' ')})."
        )
    ai_client = create_ai_client(settings.anthropic_api_key) if args.ai_filter else None
    usage_totals = UsageTotals() if args.ai_filter else None
    needs_db = args.ai_filter or args.sync_notion
    db_connection = get_connection() if needs_db else None
    run_stats = {"classified": 0, "cached": 0}
    ignored_chats = load_ignored_chats() if args.ai_filter else set()

    if args.folder:
        target_folders = [args.folder]
    elif args.chat:
        target_folders = []
    else:
        target_folders = load_target_folders()

    client = create_client(settings)
    try:
        await authenticate_client(client)
        print_app_header()
        if target_folders:
            for folder_name in target_folders:
                try:
                    await run_folder(client, folder_name, args, ai_client, usage_totals, db_connection, run_stats, ignored_chats)
                except TelegramFolderError as exc:
                    print(f"\nFolder: {folder_name}\nError: {exc}")
        else:
            chat_identifier = args.chat or settings.telegram_test_chat
            if not chat_identifier:
                raise SettingsError(
                    "No chat/folder specified. Provide --chat or --folder, add a "
                    "'## Folders to query' section to template.md, or set TELEGRAM_TEST_CHAT."
                )
            await run_chat(client, chat_identifier, args, ai_client, usage_totals, db_connection, run_stats, ignored_chats)
        if usage_totals is not None:
            print_usage_summary(usage_totals, run_stats)
        if args.sync_notion:
            notion_client_obj = create_notion_client(settings.notion_api_key)
            data_source_id = resolve_data_source_id(notion_client_obj, settings.notion_database_id)
            sync_pending_results_to_notion(db_connection, notion_client_obj, data_source_id)
            update_last_synced_marker(notion_client_obj, settings.notion_database_id, datetime.now(timezone.utc))
    finally:
        await client.disconnect()
        if db_connection is not None:
            db_connection.close()


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
        NotionSyncError,
    ) as exc:
        print(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
