from manga.gateways.mangaupd import MangaUpdatesGateway
import unittest
from unittest.mock import MagicMock


class TestMangaUpdates(unittest.TestCase):
    def setUp(self) -> None:
        self.sut = MangaUpdatesGateway()
        return super().setUp()

    def test_mostSearchableTitle_CodeBreaker(self):
        result = self.sut._MangaUpdatesGateway__getMostSearchableTitle(
            ['CØDE:BREAKER', 'Code:Breaker', 'コード:ブレイカー']
        )
        self.assertEqual(result, "Code:Breaker")
