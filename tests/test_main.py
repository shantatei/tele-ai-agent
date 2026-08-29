"""Tests for app.main's default message-lookback resolution."""

from __future__ import annotations

import argparse
import unittest
from datetime import datetime, timedelta, timezone

from app.main import resolve_after_timestamp


def make_args(after_id=None, after_timestamp=None) -> argparse.Namespace:
    return argparse.Namespace(after_id=after_id, after_timestamp=after_timestamp)


class ResolveAfterTimestampTests(unittest.TestCase):
    def test_defaults_to_last_24_hours_when_nothing_given(self):
        before_call = datetime.now(timezone.utc)
        result = resolve_after_timestamp(make_args())
        after_call = datetime.now(timezone.utc)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result, before_call - timedelta(days=1, seconds=1))
        self.assertLessEqual(result, after_call - timedelta(days=1) + timedelta(seconds=1))

    def test_leaves_explicit_after_timestamp_untouched(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(resolve_after_timestamp(make_args(after_timestamp=ts)), ts)

    def test_leaves_after_timestamp_none_when_only_after_id_given(self):
        self.assertIsNone(resolve_after_timestamp(make_args(after_id=42)))


if __name__ == "__main__":
    unittest.main()
