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


class LoadIgnoredChatsTests(unittest.TestCase):
    def test_returns_empty_set_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "template.md"
            with patch.object(prompts, "TEMPLATE_PATH", missing_path):
                self.assertEqual(prompts.load_ignored_chats(), set())

    def test_parses_bullets_under_ignored_chats_heading(self) -> None:
        content = (
            "# AI Extraction Guidelines\n\n"
            "## Priorities\n"
            "- Badminton\n\n"
            "## Ignored chats\n"
            "Some explanatory paragraph that is not a bullet.\n"
            "- Laundry\n"
            "* Marketplace\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                result = prompts.load_ignored_chats()

        self.assertEqual(result, {"laundry", "marketplace"})
        self.assertNotIn("badminton", result)

    def test_stops_at_next_heading(self) -> None:
        content = "## Ignored chats\n- Laundry\n\n## Style preferences\n- Keep it short\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                result = prompts.load_ignored_chats()

        self.assertEqual(result, {"laundry"})

    def test_no_ignored_chats_section_returns_empty_set(self) -> None:
        content = "## Priorities\n- Badminton\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                self.assertEqual(prompts.load_ignored_chats(), set())


class IsChatIgnoredTests(unittest.TestCase):
    def test_matches_case_insensitive_substring(self) -> None:
        self.assertTrue(prompts.is_chat_ignored("Helix Laundry Room", {"laundry"}))
        self.assertTrue(prompts.is_chat_ignored("LAUNDRY updates", {"laundry"}))

    def test_no_match_returns_false(self) -> None:
        self.assertFalse(prompts.is_chat_ignored("Helix Badminton", {"laundry"}))

    def test_empty_ignore_set_never_matches(self) -> None:
        self.assertFalse(prompts.is_chat_ignored("Laundry", set()))

    def test_none_chat_name_returns_false(self) -> None:
        self.assertFalse(prompts.is_chat_ignored(None, {"laundry"}))

    def test_matches_on_topic_name_when_chat_name_does_not_match(self) -> None:
        self.assertTrue(
            prompts.is_chat_ignored("Helixians AY26/27", {"laundry"}, topic_name="Laundry")
        )

    def test_unmatched_chat_and_topic_returns_false(self) -> None:
        self.assertFalse(
            prompts.is_chat_ignored("Helixians AY26/27", {"laundry"}, topic_name="General")
        )

    def test_topic_name_none_does_not_error(self) -> None:
        self.assertFalse(prompts.is_chat_ignored("Helix Badminton", {"laundry"}, topic_name=None))


class LoadTargetFoldersTests(unittest.TestCase):
    def test_returns_empty_list_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "template.md"
            with patch.object(prompts, "TEMPLATE_PATH", missing_path):
                self.assertEqual(prompts.load_target_folders(), [])

    def test_returns_empty_list_when_no_section(self) -> None:
        content = "## Ignored chats\n- Laundry\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                self.assertEqual(prompts.load_target_folders(), [])

    def test_preserves_order_and_exact_case(self) -> None:
        content = "## Folders to query\n- Helix House\n- NUS Modules\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                self.assertEqual(prompts.load_target_folders(), ["Helix House", "NUS Modules"])

    def test_deduplicates_preserving_first_occurrence(self) -> None:
        content = "## Folders to query\n- Helix House\n- NUS Modules\n- Helix House\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                self.assertEqual(prompts.load_target_folders(), ["Helix House", "NUS Modules"])

    def test_stops_at_next_heading(self) -> None:
        content = "## Folders to query\n- Helix House\n\n## Ignored chats\n- Laundry\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "template.md"
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts, "TEMPLATE_PATH", path):
                self.assertEqual(prompts.load_target_folders(), ["Helix House"])


if __name__ == "__main__":
    unittest.main()
