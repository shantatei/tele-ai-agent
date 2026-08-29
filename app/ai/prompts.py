"""Prompt construction for Telegram message classification and extraction."""

from __future__ import annotations

from datetime import datetime

BASE_INSTRUCTIONS = """You are the AI layer of Tele AI Agent. You read a single Telegram message and \
classify it into exactly one category, then extract any structured details it contains.

Categories:
- event: meetings, activities, appointments, schedules.
- task: things the reader needs to do.
- important: information that should be retained or reviewed, but is not an event or task.
- information: useful information that does not require action.
- ignore: casual or irrelevant chatter with no useful content.

Extract these fields when the message provides them; leave a field null if it does not apply:
- title: a short label for the event/task/topic.
- summary: a one or two sentence summary of the message.
- date: ISO 8601 date (YYYY-MM-DD), resolved from any relative reference (e.g. "this Friday",
  "tomorrow") using the message's send time below as the reference point, not the current date.
- time: 24-hour HH:MM, if a time is mentioned.
- location: a location, if mentioned.
- deadline: ISO 8601 date, if the message specifies a deadline distinct from an event date.
- importance: "low", "medium", or "high", your judgement of how much attention it needs.

Messages with no meaningful text (e.g. a photo or sticker with no caption) should be classified
as ignore."""


def build_system_prompt(sent_at: datetime | None) -> str:
    """Build the system prompt, anchoring relative-date resolution to the message's send time."""

    if sent_at is not None:
        reference_line = f"\n\nThis message was sent at: {sent_at.isoformat()}"
    else:
        reference_line = "\n\nThe message's send time is unknown; do not resolve relative dates."
    return BASE_INSTRUCTIONS + reference_line
