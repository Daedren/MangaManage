import unittest
from manga.missingChapters import CheckGapsInChapters
from unittest.mock import MagicMock


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
