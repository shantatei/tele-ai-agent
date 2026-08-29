"""Unit tests that use fakes and never contact Telegram."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from app.telegram.folders import TelegramFolderError, get_folder_chats


class FakeDialogFilter:
    def __init__(self, title: object, include_peers: list[object]) -> None:
        self.title = title
        self.include_peers = include_peers


class FakeFiltersResult:
    def __init__(self, filters: list[object]) -> None:
        self.filters = filters


class FakeClient:
    def __init__(self, filters_result: object, entities_by_peer: dict[object, object]) -> None:
        self.filters_result = filters_result
        self.entities_by_peer = entities_by_peer

    async def __call__(self, request: object) -> object:
        return self.filters_result

    async def get_entity(self, peer: object) -> object:
        return self.entities_by_peer[peer]


class FolderResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_chats_for_matching_folder_case_insensitive(self) -> None:
        chat_a = SimpleNamespace(id=1, title="Helix Badminton")
        chat_b = SimpleNamespace(id=2, title="Helix Gym")
        target_filter = FakeDialogFilter(title="Helix House", include_peers=["peer_a", "peer_b"])
        other_filter = FakeDialogFilter(title="NUS", include_peers=["peer_c"])
        client = FakeClient(
            FakeFiltersResult([other_filter, target_filter]),
            {"peer_a": chat_a, "peer_b": chat_b},
        )

        chats = await get_folder_chats(client, "helix house")

        self.assertEqual(chats, [chat_a, chat_b])

    async def test_handles_rich_text_title_object(self) -> None:
        rich_title = SimpleNamespace(text="Helix House")
        target_filter = FakeDialogFilter(title=rich_title, include_peers=[])
        client = FakeClient(FakeFiltersResult([target_filter]), {})

        chats = await get_folder_chats(client, "Helix House")

        self.assertEqual(chats, [])

    async def test_raises_when_folder_not_found(self) -> None:
        client = FakeClient(FakeFiltersResult([FakeDialogFilter(title="Other", include_peers=[])]), {})

        with self.assertRaises(TelegramFolderError):
            await get_folder_chats(client, "Missing Folder")

    async def test_raises_on_empty_folder_name(self) -> None:
        client = FakeClient(FakeFiltersResult([]), {})

        with self.assertRaises(TelegramFolderError):
            await get_folder_chats(client, "")


if __name__ == "__main__":
    unittest.main()
