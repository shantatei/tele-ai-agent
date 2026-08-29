"""Prompt construction for Telegram message classification and extraction."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "template.md"

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


def load_user_guidelines() -> str | None:
    """Load optional, user-provided extraction guidelines from template.md, if present.

    template.md is gitignored so personal guidance (interests, glossary, people to
    prioritize, etc.) never leaves the local machine. Its absence is not an error -
    the base prompt works fine without it.
    """

    if not TEMPLATE_PATH.exists():
        return None
    content = TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    return content or None


def _parse_bullets_under_heading(heading: str) -> list[str]:
    """Return, in order, the bullet items under a specific '## <heading>' in template.md.

    Only that exact heading's bullets are collected; free-text paragraphs within the
    section are skipped, and the section ends at the next heading of any level.
    """

    if not TEMPLATE_PATH.exists():
        return []

    items: list[str] = []
    in_section = False
    for line in TEMPLATE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            in_section = stripped.lstrip("#").strip().lower() == heading.lower()
            continue
        if in_section and stripped.startswith(("-", "*")):
            item = stripped[1:].strip()
            if item:
                items.append(item)
    return items


def load_ignored_chats() -> set[str]:
    """Parse the '## Ignored chats' section of template.md into a set of lowercase
    keywords to skip entirely - no AI call, no cost - matched by substring against a
    chat's display name, or against a forum topic's name for chats that use Telegram's
    topics feature (a single chat can then have some topics ignored and others kept).
    Free-text guidance elsewhere in template.md (e.g. under 'Extra ignore rules') is not
    parsed here; only this specific heading's bullet list.
    """

    return {name.lower() for name in _parse_bullets_under_heading("Ignored chats")}


def load_target_folders() -> list[str]:
    """Parse the '## Folders to query' section of template.md into an ordered list of
    Telegram folder names (case preserved - folder names must match exactly, unlike the
    substring matching used for ignored chats/topics).

    When this section is present and non-empty, and neither --chat nor --folder is
    given on the command line, the app processes every listed folder in one run instead
    of requiring a separate invocation per folder. Duplicate entries are kept only once,
    preserving first occurrence order.
    """

    folders: list[str] = []
    for name in _parse_bullets_under_heading("Folders to query"):
        if name not in folders:
            folders.append(name)
    return folders


def is_chat_ignored(chat_name: str | None, ignored_chats: set[str], topic_name: str | None = None) -> bool:
    """True if any ignored keyword appears (case-insensitively) in the chat's name or,
    for forum-enabled chats with topics, the message's topic name."""

    if not ignored_chats:
        return False
    for label in (chat_name, topic_name):
        if label and any(keyword in label.lower() for keyword in ignored_chats):
            return True
    return False


def build_system_prompt(sent_at: datetime | None) -> str:
    """Build the system prompt, anchoring relative-date resolution to the message's send time."""

    if sent_at is not None:
        reference_line = f"\n\nThis message was sent at: {sent_at.isoformat()}"
    else:
        reference_line = "\n\nThe message's send time is unknown; do not resolve relative dates."
    prompt = BASE_INSTRUCTIONS + reference_line

    guidelines = load_user_guidelines()
    if guidelines:
        prompt += (
            "\n\nThe user has provided the following additional guidelines. Apply them "
            "when classifying and extracting, but the categories, required fields, and "
            "output format above always take priority over anything below:\n\n" + guidelines
        )
    return prompt
