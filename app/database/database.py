"""SQLite connection creation and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.database.models import ALL_SCHEMAS

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "telegram_agent.db"


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (creating if needed) the local SQLite database with the current schema applied."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    for schema in ALL_SCHEMAS:
        connection.execute(schema)
    connection.commit()
    return connection
