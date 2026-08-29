"""Structured output schema for AI-classified Telegram messages."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Classification = Literal["event", "task", "important", "information", "ignore"]
Importance = Literal["low", "medium", "high"]


class MessageClassification(BaseModel):
    """The AI layer's structured judgement about a single Telegram message."""

    classification: Classification
    title: str | None = None
    summary: str | None = None
    date: str | None = None
    time: str | None = None
    location: str | None = None
    deadline: str | None = None
    importance: Importance | None = None
