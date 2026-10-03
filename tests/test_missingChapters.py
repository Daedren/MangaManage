import unittest
from manga.missingChapters import CheckGapsInChapters
from unittest.mock import MagicMock
from types import SimpleNamespace
from datetime import datetime


class TestCalculateChapterName(unittest.TestCase):
    def setUp(self) -> None:
        self.sut = CheckGapsInChapters(MagicMock(), MagicMock(), MagicMock())
        return super().setUp()

    def test_checkConsecutive_123_True(self):
        stub = [1, 2, 3]
        result = self.sut._CheckGapsInChapters__checkConsecutive(13300, 'title name', stub)
        self.assertEqual(result, [])

    def test_checkConsecutive_321_True(self):
        stub = [3, 2, 1]
        result = self.sut._CheckGapsInChapters__checkConsecutive(13300, 'title name', stub)
        self.assertEqual(result, [])

    def test_checkConsecutive_0d5Gap_True(self):
        stub = [1, 1.5, 2]
        result = self.sut._CheckGapsInChapters__checkConsecutive(13300, 'title name', stub)
        self.assertEqual(result, [])

    def test_checkConsecutive_1d5Gap_False(self):
        stub = [1, 2, 3.5]
        result = self.sut._CheckGapsInChapters__checkConsecutive(13300, 'title name', stub)
        self.assertNotEqual(result, [])

    def test_checkConsecutive_1d1Gap_True(self):
        """Some manga have fractional chapters, generally splitting one into two (40.1, 40.2)
        Which means we can have a jump from Ch39 to Ch40.1"""
        stub = [40.0, 41.1]
        result = self.sut._CheckGapsInChapters__checkConsecutive(13300, 'title name', stub)
        self.assertEqual(result, [])

    def test_gapExistsInTrackerProgress_35prog37min_True(self):
        stub = [37.0, 38.0]
        result = self.sut._CheckGapsInChapters__gapExistsInTrackerProgress(13300, 'title name', 35, stub)
        self.assertIsNotNone(result)

    def test_gapExistsInTrackerProgress_38prog35min_True(self):
        # Deleting already read manga isn't this class's responsibility
        stub = [35.0, 36.0]
        result = self.sut._CheckGapsInChapters__gapExistsInTrackerProgress(13300, 'title name', 38, stub)
        self.assertIsNone(result)

    def test_gapExistsInTrackerProgress_34prog35min_True(self):
        stub = [35.0, 36.0]
        result = self.sut._CheckGapsInChapters__gapExistsInTrackerProgress(13300, 'title name', 34, stub)
        self.assertIsNone(result)

    def test_gapExistsInTrackerProgress_35d2Prog36d1min_False(self):
        """Some manga have fractional chapters, generally splitting one into two (40.1, 40.2)
        Which means we can have a jump from Ch39 to Ch40.1"""
        stub = [41.1, 41.2]
        result = self.sut._CheckGapsInChapters__gapExistsInTrackerProgress(13300, 'title name', 40.0, stub)
        self.assertIsNone(result)

    def test_getNoLongerQuarantined_oneNoLongerQ_KeepEverythingElse(self):
        alreadyQuarantined = [1234, 3245]
        newQuarantine = [1234]
        result = self.sut._CheckGapsInChapters__getNoLongerQuarantined(
            alreadyQuarantined, newQuarantine
        )
        self.assertEqual(result, [3245])

    def test_getNoLongerQuarantined_newQ_ignoreItReturnOthers(self):
        """New quarantines aren't dealt with here.
        We just want to see who we can unquarantine"""
        alreadyQuarantined = [1234]
        newQuarantine = [1234, 3245]
        result = self.sut._CheckGapsInChapters__getNoLongerQuarantined(
            alreadyQuarantined, newQuarantine
        )
        self.assertEqual(result, [])

    def test_getNoLongerQuarantined_sameAsLast_returnSame(self):
        """Since we only want those to unquarantine, this must
        return empty"""
        alreadyQuarantined = [3245, 1234]
        newQuarantine = [1234, 3245]
        result = self.sut._CheckGapsInChapters__getNoLongerQuarantined(
            alreadyQuarantined, newQuarantine
        )
        self.assertEqual(result, [])

    def test_getOnlyNewQuarantines_oneNoLongerQ_KeepEverythingElse(self):
        alreadyQuarantined = [1234, 3245]
        newQuarantine = [1234]
        result = self.sut._CheckGapsInChapters__getOnlyNewQuarantines(
            alreadyQuarantined, newQuarantine
        )
        self.assertEqual(result, [])

    def test_getOnlyNewQuarantines__newQ_ignoreItReturnOthers(self):
        alreadyQuarantined = [1234]
        newQuarantine = [1234, 3245]
        result = self.sut._CheckGapsInChapters__getOnlyNewQuarantines(
            alreadyQuarantined, newQuarantine
        )
        self.assertEqual(result, [3245])

    def test_getOnlyNewQuarantines_sameAsLast_returnSame(self):
        alreadyQuarantined = [3245, 1234]
        newQuarantine = [1234, 3245]
        result = self.sut._CheckGapsInChapters__getOnlyNewQuarantines(
            alreadyQuarantined, newQuarantine
        )
        self.assertEqual(result, [])

    def test_details_return_all_consecutive_gaps(self):
        self.sut.database.getActiveChaptersForAnilist.return_value = [
            {"series": "Alpha", "chapter": chapter} for chapter in ("40", "43", "46")
        ]
        self.sut.anilist.getProgressFor.return_value = 39
        self.assertEqual(self.sut.getQuarantineDetails(42), {
            "status": "gaps_found", "reasons": [
                {"type": "consecutive_gap", "before": 40, "after": 43},
                {"type": "consecutive_gap", "before": 43, "after": 46},
            ],
        })
        self.sut.filesystem.quarantineSeries.assert_not_called()
        self.sut.filesystem.restoreQuarantinedArchive.assert_not_called()

    def test_tracker_gap_preserves_workflow_priority(self):
        gaps = self.sut.getGapsForChapters(42, "Alpha", 35, [37, 40])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].reasonToPrint(), "Alpha - Last read 35 but stored 37")

    def test_details_no_active_chapters(self):
        self.sut.database.getActiveChaptersForAnilist.return_value = []
        self.assertEqual(self.sut.getQuarantineDetails(42), {"status": "no_active_chapters", "reasons": []})
        self.sut.anilist.getProgressFor.assert_not_called()

    def test_details_missing_tracker_is_not_no_gaps(self):
        self.sut.database.getActiveChaptersForAnilist.return_value = [{"series": "Alpha", "chapter": "1"}]
        self.sut.anilist.getProgressFor.return_value = None
        self.assertEqual(self.sut.getQuarantineDetails(42), {"status": "tracker_unavailable", "reasons": []})

    def test_details_accept_zero_progress_and_fractional_chapters(self):
        self.sut.database.getActiveChaptersForAnilist.return_value = [
            {"series": "Alpha", "chapter": chapter} for chapter in ("1.1", "1.2", "2")
        ]
        self.sut.anilist.getProgressFor.return_value = 0
        self.assertEqual(self.sut.getQuarantineDetails(42), {"status": "no_gaps", "reasons": []})

    def test_workflow_uses_shared_rules_and_still_updates_quarantine(self):
        self.sut.database.getAllChapters.return_value = [
            {"anilistId": 42, "chapter": "37"}, {"anilistId": 42, "chapter": "40"},
        ]
        self.sut.database.getSeriesLastUpdatedSince.return_value = [{"anilistId": 42}]
        self.sut.anilist.getAllEntries.return_value = {
            42: SimpleNamespace(progress=35, titles=["Alpha"]),
        }
        self.sut.filesystem.getQuarantinedSeries.return_value = [42, 43]
        gaps = self.sut.getGapsFromChaptersSince(datetime(2026, 1, 1))
        self.assertEqual([gap.reasonToPrint() for gap in gaps], ["Alpha - Last read 35 but stored 37.0"])
        self.sut.filesystem.quarantineSeries.assert_called_once_with(anilistId=42)
        self.sut.filesystem.restoreQuarantinedArchive.assert_called_once_with(43)
        self.sut.anilist.getProgressFor.assert_not_called()
