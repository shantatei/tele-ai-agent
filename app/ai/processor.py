"""Claude-based classification and structured extraction for Telegram messages."""

from __future__ import annotations

from typing import Any

import anthropic

from app.ai.prompts import build_system_prompt
from app.ai.schemas import MessageClassification

MODEL = "claude-sonnet-5"
NO_TEXT_PLACEHOLDER = "[No text content]"

# USD price per 1M tokens, (input, output), for models this app may use.
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


class AIProcessorError(RuntimeError):
    """Raised when a message cannot be classified."""


class UsageTotals:
    """Accumulates token usage across classification calls to estimate spend."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0

    def add(self, usage: Any) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0

    def estimated_cost_usd(self, model: str = MODEL) -> float | None:
        pricing = PRICING_PER_MTOK.get(model)
        if pricing is None:
            return None
        input_price, output_price = pricing
        return (self.input_tokens / 1_000_000) * input_price + (self.output_tokens / 1_000_000) * output_price


def create_ai_client(api_key: str | None) -> anthropic.Anthropic:
    """Create the Claude client, failing clearly if no API key is configured."""

    if not api_key:
        raise AIProcessorError(
            "ANTHROPIC_API_KEY is required for the AI filter. Add it to .env or your environment."
        )
    return anthropic.Anthropic(api_key=api_key)


def classify_message(
    client: anthropic.Anthropic,
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
        response = client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
            output_format=MessageClassification,
        )
    except anthropic.AuthenticationError as exc:
        raise AIProcessorError("Anthropic authentication failed. Check ANTHROPIC_API_KEY.") from exc
    except anthropic.RateLimitError as exc:
        raise AIProcessorError("Anthropic rate limit hit. Try again shortly.") from exc
    except anthropic.APIStatusError as exc:
        raise AIProcessorError(f"Anthropic API error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AIProcessorError("Could not reach the Anthropic API. Check your network.") from exc

    if usage_totals is not None:
        usage_totals.add(response.usage)

    return response.parsed_output
