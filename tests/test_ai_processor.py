"""Unit tests that use fakes and never contact the Gemini API."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from google.genai import errors

from app.ai.processor import AIProcessorError, UsageTotals, classify_message, create_ai_client
from app.ai.schemas import MessageClassification


class FakeUsageMetadata:
    def __init__(self, prompt_token_count: int, candidates_token_count: int) -> None:
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


class FakeResponse:
    def __init__(self, parsed: object, usage_metadata: FakeUsageMetadata | None = None) -> None:
        self.parsed = parsed
        self.usage_metadata = usage_metadata


class FakeModels:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.last_call: dict[str, object] | None = None

    def generate_content(self, **kwargs: object) -> object:
        self.last_call = kwargs
        if self._error is not None:
            raise self._error
        return self._result


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.models = models


def make_message(text: str) -> dict[str, object]:
    return {
        "message_id": 1,
        "chat_name": "Example Chat",
        "sender_name": "Ada",
        "message_text": text,
        "timestamp": datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
    }


def make_api_error(exc_type: type[errors.APIError], status_code: int) -> errors.APIError:
    return exc_type(code=status_code, response_json={"error": {"message": "boom"}})


class CreateAIClientTests(unittest.TestCase):
    def test_raises_when_api_key_missing(self) -> None:
        with self.assertRaises(AIProcessorError):
            create_ai_client(None)

    def test_raises_when_api_key_empty(self) -> None:
        with self.assertRaises(AIProcessorError):
            create_ai_client("")


class ClassifyMessageTests(unittest.TestCase):
    def test_no_text_content_skips_api_call(self) -> None:
        client = FakeClient(FakeModels())
        message = make_message("[No text content]")

        result = classify_message(client, message)

        self.assertEqual(result.classification, "ignore")
        self.assertIsNone(client.models.last_call)

    def test_missing_text_skips_api_call(self) -> None:
        client = FakeClient(FakeModels())
        message = make_message("")

        result = classify_message(client, message)

        self.assertEqual(result.classification, "ignore")
        self.assertIsNone(client.models.last_call)

    def test_successful_classification_returns_parsed_output(self) -> None:
        expected = MessageClassification(
            classification="event",
            title="Club Meeting",
            date="2026-08-21",
            importance="high",
        )
        models = FakeModels(result=FakeResponse(expected))
        client = FakeClient(models)
        message = make_message("Meeting this Friday at 7pm.")

        result = classify_message(client, message)

        self.assertIs(result, expected)
        self.assertEqual(models.last_call["contents"], "Meeting this Friday at 7pm.")
        self.assertIn("2026-08-21T12:00:00", models.last_call["config"].system_instruction)
        self.assertIs(models.last_call["config"].response_schema, MessageClassification)

    def test_raises_when_response_not_parsed(self) -> None:
        models = FakeModels(result=FakeResponse(parsed=None))
        client = FakeClient(models)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))

    def test_authentication_error_is_wrapped(self) -> None:
        models = FakeModels(error=make_api_error(errors.ClientError, 401))
        client = FakeClient(models)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))

    def test_rate_limit_error_is_wrapped(self) -> None:
        models = FakeModels(error=make_api_error(errors.ClientError, 429))
        client = FakeClient(models)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))

    def test_generic_client_error_is_wrapped(self) -> None:
        models = FakeModels(error=make_api_error(errors.ClientError, 400))
        client = FakeClient(models)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))

    def test_server_error_is_wrapped(self) -> None:
        models = FakeModels(error=make_api_error(errors.ServerError, 500))
        client = FakeClient(models)

        with self.assertRaises(AIProcessorError):
            classify_message(client, make_message("hello"))


class UsageTotalsTests(unittest.TestCase):
    def test_add_accumulates_across_calls(self) -> None:
        totals = UsageTotals()

        totals.add(FakeUsageMetadata(prompt_token_count=100, candidates_token_count=20))
        totals.add(FakeUsageMetadata(prompt_token_count=50, candidates_token_count=10))

        self.assertEqual(totals.input_tokens, 150)
        self.assertEqual(totals.output_tokens, 30)

    def test_classify_message_records_usage_when_tracker_given(self) -> None:
        expected = MessageClassification(classification="task", title="Do the thing")
        usage_metadata = FakeUsageMetadata(prompt_token_count=200, candidates_token_count=40)
        models = FakeModels(result=FakeResponse(expected, usage_metadata=usage_metadata))
        client = FakeClient(models)
        totals = UsageTotals()

        classify_message(client, make_message("Remember to do the thing."), totals)

        self.assertEqual(totals.input_tokens, 200)
        self.assertEqual(totals.output_tokens, 40)


if __name__ == "__main__":
    unittest.main()
