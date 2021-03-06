# -*- coding: UTF-8 -*-
import unittest
from manga.createMetadata2 import CreateMetadata2
from unittest.mock import MagicMock
from models.manga import Chapter
from models.tracker import TrackerSeries
from manga.gateways.anilist import TrackerGatewayInterface
from lxml.doctestcompare import LXMLOutputChecker, PARSE_XML
from lxml import etree


class TestCreateMetadata(unittest.TestCase):
    def setUp(self) -> None:
        self.filesystem = MagicMock()
        self.tracker = TrackerGatewayInterface()
        self.sut = CreateMetadata2(filesystem=self.filesystem, anilist=self.tracker)

        self.baseFake = Chapter(
            33194,
            "seriesN",
            "15",
            "chName",
            "/tmp/fstest/origin",
            "/tmp/fstest/destination",
        )
        return super().setUp()

    def __assertXmlEqual(self, got, want):
        checker = LXMLOutputChecker()
        self.assertTrue(checker.check_output(want, got, PARSE_XML))

    def __assertXmlMatchesComicInfo(self, result):
        matches = False
        with open("tests/resources/ComicInfo.xsd", "rb") as xsd_file:
            schemaContent = xsd_file.read()
            root = etree.XML(schemaContent)
            schema = etree.XMLSchema(root)
            parser = etree.XMLParser(schema=schema)
            matches = etree.fromstring(result, parser) is not None
        self.assertTrue(matches)

    def test_executeToString_default(self):
        fake = self.baseFake
        stub = TrackerSeries(
            fake.anilistId, [fake.seriesName], "FINISHED", 30, "JP", 17
        )
        self.tracker.getAllEntries = MagicMock(return_value={fake.anilistId: stub})

        result = self.sut._CreateMetadata2__generateMetadata(fake)
        with open("tests/resources/createMetadata_1.xml", "rb") as xml_file:
            comparison = xml_file.read()
            self.__assertXmlEqual(result, comparison)
            self.__assertXmlMatchesComicInfo(result)

    def test_executeToString_KRRegion_NoMangaField(self):
        fake = self.baseFake
        stub = TrackerSeries(
            fake.anilistId, [fake.seriesName], "FINISHED", 30, "KR", 17
        )
        self.tracker.getAllEntries = MagicMock(return_value={fake.anilistId: stub})

        result = self.sut._CreateMetadata2__generateMetadata(fake)
        with open("tests/resources/createMetadata_2.xml", "rb") as xml_file:
            comparison = xml_file.read()
            self.__assertXmlEqual(result, comparison)
            self.__assertXmlMatchesComicInfo(result)

    def test_executeToString_otherTitlesExist_altSeriesIsSet(self):
        second_series_name = "other series"

        fake = self.baseFake

        stub = TrackerSeries(
            fake.anilistId, [fake.seriesName,
                             second_series_name], "FINISHED", 30, "KR", 17
        )
        self.tracker.getAllEntries = MagicMock(return_value={fake.anilistId: stub})

        result = self.sut._CreateMetadata2__generateMetadata(fake)
        with open("tests/resources/createMetadata_3.xml", "rb") as xml_file:
            comparison = xml_file.read()
            self.__assertXmlEqual(result, comparison)
            self.__assertXmlMatchesComicInfo(result)

    def test_getAltSeriesForChapter_differentCase_dontMatch(self):
        fake = self.baseFake
        different_case_series = "seriesn"
        second_series_name = "other series"

        stub = TrackerSeries(
            fake.anilistId, [different_case_series,
                             second_series_name], "FINISHED", 30, "KR", 17
        )
        self.tracker.getAllEntries = MagicMock(return_value={fake.anilistId: stub})

        result = self.sut._CreateMetadata2__getAltSeriesForChapter(fake)

        self.assertEqual(result, second_series_name)

    def test_getAltSeriesForChapter_differentPunctuation_dontMatch(self):
        fake = self.baseFake
        different_case_series = "series N"
        second_series_name = "other series"

        fake.seriesName = "series.N"

        stub = TrackerSeries(
            fake.anilistId, [different_case_series,
                             second_series_name], "FINISHED", 30, "KR", 17
        )
        self.tracker.getAllEntries = MagicMock(return_value={fake.anilistId: stub})

        result = self.sut._CreateMetadata2__getAltSeriesForChapter(fake)

        self.assertEqual(result, second_series_name)

    def test_getAltSeriesForChapter_differentWhitespace_dontMatch(self):
        fake = self.baseFake
        different_case_series = " series N"
        second_series_name = "other series"

        fake.seriesName = "series N"

        stub = TrackerSeries(
            fake.anilistId, [different_case_series,
                             second_series_name], "FINISHED", 30, "KR", 17
        )
        self.tracker.getAllEntries = MagicMock(return_value={fake.anilistId: stub})

        result = self.sut._CreateMetadata2__getAltSeriesForChapter(fake)

        self.assertEqual(result, second_series_name)
