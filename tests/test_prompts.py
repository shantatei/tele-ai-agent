"""Unit tests for prompt construction. Uses a patched TEMPLATE_PATH, never the real
(gitignored) template.md, so results don't depend on local personal customization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.ai import prompts


class LoadUserGuidelinesTests(unittest.TestCase):
    def test_returns_none_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "template.md"
            with patch.object(prompts, "TEMPLATE_PATH", missing_path):
                self.assertIsNone(prompts.load_user_guidelines())

    def test_returns_none_for_whitespace_only_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text("   \n\n  ", encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                self.assertIsNone(prompts.load_user_guidelines())

    def test_returns_stripped_content_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text("\n  Prioritize badminton events.  \n", encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                self.assertEqual(prompts.load_user_guidelines(), "Prioritize badminton events.")


class BuildSystemPromptTests(unittest.TestCase):
    def test_prompt_excludes_guidelines_section_when_no_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "template.md"
            with patch.object(prompts, "TEMPLATE_PATH", missing_path):
                result = prompts.build_system_prompt(sent_at=None)

        self.assertNotIn("additional guidelines", result)
        self.assertIn(prompts.BASE_INSTRUCTIONS, result)

    def test_prompt_includes_template_content_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text("Assume Singapore time (UTC+8).", encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                result = prompts.build_system_prompt(sent_at=datetime(2026, 8, 21, tzinfo=timezone.utc))

        self.assertIn("additional guidelines", result)
        self.assertIn("Assume Singapore time (UTC+8).", result)
        # Base categories/schema instructions must still be present and come first.
        self.assertLess(result.index("Categories:"), result.index("additional guidelines"))


if __name__ == "__main__":
    unittest.main()
