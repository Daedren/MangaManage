# -*- coding: UTF-8 -*-
from manga.gateways.anilist import TrackerGatewayInterface
import unittest
from manga.mangagetchapter import CalculateChapterName
from unittest.mock import MagicMock


class TestCalculateChapterName(unittest.TestCase):
    def setUp(self) -> None:
        self.mockTracker = TrackerGatewayInterface()
        self.sut = CalculateChapterName(self.mockTracker)
        return super().setUp()

    def test_calculatechaptername_Ch107Room203_107(self):
        result = self.sut.execute(
            "Vol. 13 Ch. 107 - The Girlfriend, and Room 203", 99943
        )
        self.assertEqual(result, "107")

    def test_calculatechaptername_Ch99d3_99d3(self):
        result = self.sut.execute("Ch. 99.3 - Heat Up (Ch 99 Redrawn by Murata)", 99943)
        self.assertEqual(result, "99.3")

    def test_calculatechaptername_Ch119_119(self):
        result = self.sut.execute("Ch. 119 - A Glimpse Behind The Scenes", 99943)
        self.assertEqual(result, "119")

    def test_calculatechaptername_Chd065_65(self):
        result = self.sut.execute(
            "Eden's Zero Ch.065 - The Swordswoman Can’t Move", 99943
        )
        self.assertEqual(result, "65")

    def test_calculatechaptername_exname2_ex2(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("ex - SHORT MISSION 2", 108556)
        self.assertEqual(result, "15.8")

    def test_calculatechaptername_exname1_ex(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute(
            "#ex - Record #18 Flowers That Bloom On Hitogashima", 102989
        )
        self.assertEqual(result, "15.8")

    def test_calculatechaptername_Ch108WithNumberAtEnd_108(self):
        result = self.sut.execute(
            "Vol.13 Ch.108 - Bloody War!! High Waves at the Senkaku Islands!! 33",
            102989,
        )
        self.assertEqual(result, "108")

    def test_calculatechaptername_Ch29d2WithNumberAtEnd_29d2(self):
        result = self.sut.execute("Ch.29.2 - Syphilis (Part 2)", 102989)
        self.assertEqual(result, "29.2")

    # Mangaplus
    def test_calculatechaptername_ex_ex(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("ex - EXTRA _THE DAY BEFORE THE VISIT_", 106683)
        self.assertEqual(result, "15.8")

    def test_calculatechaptername_006_6(self):
        result = self.sut.execute("#006 - #6. Flames", 115106)
        self.assertEqual(result, "6")

    # Webtoon
    def test_calculatechaptername_S3Ep79Ch496_496(self):
        result = self.sut.execute("_[Season 3] Ep. 79 Ch. 496", 85143)
        self.assertEqual(result, "496")

    # Mangaplus
    def test_calculatechaptername_ShueishaEx_ex(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("Shueisha_ex - ONE-SHOT_ Profoundly Mysterious Kick-the-Can-Battle!", 132029)
        self.assertEqual(result, "15.8")

    # Mangaplus
    def test_calculatechaptername_NoPrefixEx_ex(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("_ex - ONE-SHOT_ Profoundly Mysterious Kick-the-Can-Battle!", 132029)
        self.assertEqual(result, "15.8")

    def test_calculatechaptername_noLeadingZero_AddLeadingZero(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("CClaw Translation_Ch.0.1 - YouTube Oneshot 2", 130837)
        self.assertEqual(result, "0.1")

    # MangaUpdates
    def test_calculatechaptername_v60c34_34(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("v.60 c.34.5", 130837)
        self.assertEqual(result, "34.5")

    def test_calculatechaptername_c3738_35(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("c.37-38", 130837)
        self.assertEqual(result, "38")

    def test_calculatechaptername_c37a_37(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("c.37a", 130837)
        self.assertEqual(result, "37")

    def test_calculatechaptername_c37v2_37(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("c.37v2", 130837)
        self.assertEqual(result, "37")

    def test_calculatechaptername_c23end_23(self):
        self.mockTracker.getProgressFor = MagicMock(return_value=15)
        result = self.sut.execute("Mismarca Koukoku Monogatari v.4 c.23 (end)", 130837)
        self.assertEqual(result, "23")