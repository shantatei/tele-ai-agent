"""SQLite schema definitions for the local persistence layer.

Table shapes follow the Tele AI Agent Notion spec's SQLite Layer section.
"""

from __future__ import annotations

MESSAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    chat_name TEXT,
    sender TEXT,
    message_text TEXT,
    timestamp TEXT,
    processed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (chat_id, telegram_message_id)
);
"""

AI_RESULTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages (id),
    classification TEXT NOT NULL,
    title TEXT,
    summary TEXT,
    date TEXT,
    time TEXT,
    location TEXT,
    deadline TEXT,
    importance TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

NOTION_SYNC_SCHEMA = """
CREATE TABLE IF NOT EXISTS notion_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ai_result_id INTEGER NOT NULL REFERENCES ai_results (id),
    notion_page_id TEXT,
    synced INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT
);
"""

# Tracks which calendar days (Singapore time) --once-daily has already completed
# a run for, so an hourly scheduler can safely check in without doing extra work
# once today's run has already succeeded.
DAILY_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_runs (
    run_date TEXT PRIMARY KEY,
    completed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

ALL_SCHEMAS = (MESSAGES_SCHEMA, AI_RESULTS_SCHEMA, NOTION_SYNC_SCHEMA, DAILY_RUNS_SCHEMA)
