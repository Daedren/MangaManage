from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from manga.checkForUpdates import CheckForUpdates


class TestCheckForUpdates(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.database = MagicMock()
        self.tracker = MagicMock()
        self.series = SimpleNamespace(tracker_id=42, titles=["Series"], progress=5)
        self.tracker.getAllEntries.return_value = {42: self.series}
        self.row = {"mangaUpdatesId": 123, "max_chapter": 8, "latestChapter": 8}
        self.database.getHighestChapterAndLastUpdatedForSeries.return_value = {
            42: self.row,
        }
        self.sut = CheckForUpdates(self.gateway, self.database, self.tracker)

    def test_linkingPreservesExistingMapping(self):
        self.sut.updateLocalIds()
        self.gateway.resetBackoffBudget.assert_called_once()
        self.gateway.searchForSeries.assert_not_called()
        self.database.insertMangaUpdt.assert_not_called()

    def test_linkingStoresNumericIdDirectly(self):
        self.row["mangaUpdatesId"] = None
        self.gateway.searchForSeries.return_value = 456
        self.sut.updateLocalIds()
        self.database.insertMangaUpdt.assert_called_once_with(42, mangaUpdatesId=456)
        self.gateway.searchForSeries.assert_called_once_with(["Series"])

    def test_linkingWithoutDatabaseRow(self):
        self.database.getHighestChapterAndLastUpdatedForSeries.return_value = {}
        self.gateway.searchForSeries.return_value = 456
        self.sut.updateLocalIds()
        self.database.insertMangaUpdt.assert_called_once_with(42, mangaUpdatesId=456)

    def test_noSearchMatchDoesNotInsert(self):
        self.row["mangaUpdatesId"] = None
        self.gateway.searchForSeries.return_value = None
        self.sut.updateLocalIds()
        self.database.insertMangaUpdt.assert_not_called()

    def test_checkerCachesDirectLatestChapterAndLogsUpdate(self):
        self.gateway.getLatestChapterForId.return_value = 10
        with self.assertLogs("CheckForUpdates", level="INFO") as logs:
            self.sut.checkForUpdates()
        self.gateway.resetBackoffBudget.assert_called_once()
        self.gateway.getLatestChapterForId.assert_called_once_with(123)
        self.database.updateMangaUpdtLatestChapter.assert_called_once_with(123, 10)
        self.assertIn("Latest chapter is 10", logs.output[0])

    def test_zeroIsCached(self):
        self.gateway.getLatestChapterForId.return_value = 0
        self.sut.checkForUpdates()
        self.database.updateMangaUpdtLatestChapter.assert_called_once_with(123, 0)

    def test_unknownChapterLeavesCacheUnchanged(self):
        self.gateway.getLatestChapterForId.return_value = None
        self.sut.checkForUpdates()
        self.database.updateMangaUpdtLatestChapter.assert_not_called()

    def test_requestFailureLeavesCacheUnchangedAndPropagates(self):
        self.gateway.getLatestChapterForId.side_effect = RuntimeError("request failed")
        with self.assertRaisesRegex(RuntimeError, "request failed"):
            self.sut.checkForUpdates()
        self.database.updateMangaUpdtLatestChapter.assert_not_called()

    def test_cachedUnreadUpdateAvoidsRequest(self):
        self.row["latestChapter"] = 10
        with self.assertLogs("CheckForUpdates", level="INFO"):
            self.sut.checkForUpdates()
        self.gateway.getLatestChapterForId.assert_not_called()

    def test_unlinkedOrMissingRowsAreSkipped(self):
        for rows in ({}, {42: {**self.row, "mangaUpdatesId": None}}):
            with self.subTest(rows=rows):
                lookup = self.database.getHighestChapterAndLastUpdatedForSeries
                lookup.return_value = rows
                self.sut.checkForUpdates()
                self.gateway.getLatestChapterForId.assert_not_called()

    def test_alreadyReadChapterDoesNotLogUpdate(self):
        self.series.progress = 10
        self.gateway.getLatestChapterForId.return_value = 10
        with self.assertNoLogs("CheckForUpdates", level="INFO"):
            self.sut.checkForUpdates()
