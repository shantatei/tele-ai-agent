"""Gemini-based classification and structured extraction for Telegram messages."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import errors, types

from app.ai.prompts import build_system_prompt
from app.ai.schemas import MessageClassification

MODEL = "gemini-3.5-flash-lite"
NO_TEXT_PLACEHOLDER = "[No text content]"


class AIProcessorError(RuntimeError):
    """Raised when a message cannot be classified."""


class UsageTotals:
    """Accumulates token usage across classification calls."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0

    def add(self, usage_metadata: Any) -> None:
        self.input_tokens += getattr(usage_metadata, "prompt_token_count", 0) or 0
        self.output_tokens += getattr(usage_metadata, "candidates_token_count", 0) or 0


def create_ai_client(api_key: str | None) -> genai.Client:
    """Create the Gemini client, failing clearly if no API key is configured."""

    if not api_key:
        raise AIProcessorError(
            "GEMINI_API_KEY is required for the AI filter. Add it to .env or your environment."
        )
    return genai.Client(api_key=api_key)


def classify_message(
    client: genai.Client,
    message: dict[str, Any],
    usage_totals: UsageTotals | None = None,
) -> MessageClassification:
    """Classify one structured Telegram message and extract its structured details.

    Messages with no real text (photos/stickers with no caption) are classified as
    ``ignore`` locally without an API call, since there is nothing to extract.
    """

    text = message.get("message_text")
    if not text or text == NO_TEXT_PLACEHOLDER:
        return MessageClassification(classification="ignore")

    system_prompt = build_system_prompt(sent_at=message.get("timestamp"))
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=MessageClassification,
            ),
        )
    except errors.ClientError as exc:
        if exc.code in (401, 403):
            raise AIProcessorError("Gemini authentication failed. Check GEMINI_API_KEY.") from exc
        if exc.code == 429:
            raise AIProcessorError("Gemini rate limit hit. Try again shortly.") from exc
        raise AIProcessorError(f"Gemini API error ({exc.code}): {exc.message}") from exc
    except errors.ServerError as exc:
        raise AIProcessorError(f"Gemini server error ({exc.code}): {exc.message}") from exc

    if usage_totals is not None and response.usage_metadata is not None:
        usage_totals.add(response.usage_metadata)

    parsed = response.parsed
    if not isinstance(parsed, MessageClassification):
        raise AIProcessorError("Gemini did not return a valid structured classification.")
    return parsed
