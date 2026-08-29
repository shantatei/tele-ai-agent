"""Unit tests that use fakes and never contact the Anthropic API."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

import anthropic
import httpx

from app.ai.processor import AIProcessorError, UsageTotals, classify_message, create_ai_client
from app.ai.schemas import MessageClassification


class FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeParsedResponse:
    def __init__(self, parsed_output: MessageClassification, usage: FakeUsage | None = None) -> None:
        self.parsed_output = parsed_output
        self.usage = usage


class FakeMessages:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.last_call: dict[str, object] | None = None

    def parse(self, **kwargs: object) -> object:
        self.last_call = kwargs
        if self._error is not None:
            raise self._error
        return self._result


class FakeClient:
    def __init__(self, messages: FakeMessages) -> None:
        self.messages = messages


def make_message(text: str) -> dict[str, object]:
    return {
        "message_id": 1,
        "chat_name": "Example Chat",
        "sender_name": "Ada",
        "message_text": text,
        "timestamp": datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
    }


def make_http_error(exc_type: type[Exception], status_code: int) -> Exception:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=status_code, request=request, json={"error": {"message": "boom"}})
    return exc_type("boom", response=response, body=None)


class CreateAIClientTests(unittest.TestCase):
    def test_raises_when_api_key_missing(self) -> None:
        with self.assertRaises(AIProcessorError):
            create_ai_client(None)

    def test_raises_when_api_key_empty(self) -> None:
        with self.assertRaises(AIProcessorError):
            create_ai_client("")


class ClassifyMessageTests(unittest.TestCase):
    def test_no_text_content_skips_api_call(self) -> None:
        client = FakeClient(FakeMessages())
        message = make_message("[No text content]")

        result = classify_message(client, message)

        self.assertEqual(result.classification, "ignore")
        self.assertIsNone(client.messages.last_call)

    def test_missing_text_skips_api_call(self) -> None:
        client = FakeClient(FakeMessages())
        message = make_message("")

        result = classify_message(client, message)

        self.assertEqual(result.classification, "ignore")
        self.assertIsNone(client.messages.last_call)

    def test_successful_classification_returns_parsed_output(self) -> None:
        expected = MessageClassification(
            classification="event",
            title="Club Meeting",
            date="2026-08-21",
            importance="high",
        )
        messages = FakeMessages(result=FakeParsedResponse(expected))
        client = FakeClient(messages)
        message = make_message("Meeting this Friday at 7pm.")

        result = classify_message(client, message)

        self.assertIs(result, expected)
        self.assertEqual(messages.last_call["messages"][0]["content"], "Meeting this Friday at 7pm.")
        self.assertIn("2026-08-21T12:00:00", messages.last_call["system"])

    def test_authentication_error_is_wrapped(self) -> None:
        messages = FakeMessages(error=make_http_error(anthropic.AuthenticationError, 401))
        client = FakeClient(messages)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))

    def test_rate_limit_error_is_wrapped(self) -> None:
        messages = FakeMessages(error=make_http_error(anthropic.RateLimitError, 429))
        client = FakeClient(messages)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))

    def test_generic_api_status_error_is_wrapped(self) -> None:
        messages = FakeMessages(error=make_http_error(anthropic.APIStatusError, 500))
        client = FakeClient(messages)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))

    def test_connection_error_is_wrapped(self) -> None:
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        messages = FakeMessages(error=anthropic.APIConnectionError(request=request))
        client = FakeClient(messages)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))


class UsageTotalsTests(unittest.TestCase):
    def test_add_accumulates_across_calls(self) -> None:
        totals = UsageTotals()

        totals.add(FakeUsage(input_tokens=100, output_tokens=20))
        totals.add(FakeUsage(input_tokens=50, output_tokens=10))

        self.assertEqual(totals.input_tokens, 150)
        self.assertEqual(totals.output_tokens, 30)

    def test_estimated_cost_uses_model_pricing(self) -> None:
        totals = UsageTotals()
        totals.add(FakeUsage(input_tokens=1_000_000, output_tokens=1_000_000))

        cost = totals.estimated_cost_usd(model="claude-opus-5")

        self.assertAlmostEqual(cost, 5.00 + 25.00)

    def test_estimated_cost_is_none_for_unknown_model(self) -> None:
        totals = UsageTotals()
        totals.add(FakeUsage(input_tokens=1000, output_tokens=1000))

        self.assertIsNone(totals.estimated_cost_usd(model="some-future-model"))

    def test_classify_message_records_usage_when_tracker_given(self) -> None:
        expected = MessageClassification(classification="task", title="Do the thing")
        messages = FakeMessages(result=FakeParsedResponse(expected, usage=FakeUsage(200, 40)))
        client = FakeClient(messages)
        totals = UsageTotals()

        classify_message(client, make_message("Remember to do the thing."), totals)

        self.assertEqual(totals.input_tokens, 200)
        self.assertEqual(totals.output_tokens, 40)


if __name__ == "__main__":
    unittest.main()
