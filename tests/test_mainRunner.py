
import unittest
from unittest.mock import MagicMock

from mainRunner import MainRunner
from manga.gateways.pushover import PushServiceInterface
from models.manga import Chapter, MissingChapter


class TestMainRunner(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def test_sendPush_multipleChapters(self):
        expectation = ("2 new chapters downloaded\n"
                       "\n"
                       "name 12\n"
                       "name 13"
                       )
        push = PushServiceInterface()
        push.sendPush = MagicMock()
        sut = MainRunner("", "", MagicMock(), MagicMock(
        ), push, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        chapters = [Chapter(1, "name", "12", "chName", "", ""),
                    Chapter(1, "name", "13", "chName", "", "")]
        gaps = []
        sut.send_push(chapters, gaps)
        push.sendPush.assert_called_with(expectation)

    def test_sendPush_singleChapter(self):
        expectation = ("1 new chapter downloaded\n"
                       "\n"
                       "name 12"
                       )
        push = PushServiceInterface()
        push.sendPush = MagicMock()
        sut = MainRunner("", "", MagicMock(), MagicMock(
        ), push, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        chapters = [Chapter(1, "name", "12", "chName", "", "")]
        gaps = []
        sut.send_push(chapters, gaps)
        push.sendPush.assert_called_with(expectation)

    def test_sendPush_gaps_addedToMessage(self):
        expectation = ("1 new chapter downloaded\n"
                       "\n"
                       "name 12\n"
                       "\n"
                       "Updated in quarantine:\n"
                       "missingSeries"
                       )
        push = PushServiceInterface()
        push.sendPush = MagicMock()
        sut = MainRunner("", "", MagicMock(), MagicMock(
        ), push, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        chapters = [Chapter(1, "name", "12", "chName", "", "")]
        gaps = [MissingChapter(1, "missingSeries", 12, 10)]
        sut.send_push(chapters, gaps)
        push.sendPush.assert_called_with(expectation)
