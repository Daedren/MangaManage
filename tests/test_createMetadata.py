# -*- coding: UTF-8 -*-
import unittest
from manga.createMetadata2 import CreateMetadata2
from unittest.mock import MagicMock
from manga.models.chapter import Chapter
from lxml.doctestcompare import LXMLOutputChecker, PARSE_XML
from lxml import etree


class TestCreateMetadata(unittest.TestCase):
    def setUp(self) -> None:
        filesystem = MagicMock()
        self.sut = CreateMetadata2(filesystem=filesystem)
        return super().setUp()

    def __assertXmlEqual(self, got, want):
        checker = LXMLOutputChecker()
        self.assertTrue(checker.check_output(want, got, PARSE_XML))

    def __assertXmlMatchesComicInfo(self, result):
        with open("tests/resources/ComicInfo.xsd", "rb") as xsd_file:
            schemaContent = xsd_file.read()
            root = etree.XML(schemaContent)
            schema = etree.XMLSchema(root)
            parser = etree.XMLParser(schema=schema)
            return etree.fromstring(result, parser)
        return False

    def test_executeToString_default(self):
        fake = Chapter(
            1000,
            "seriesN",
            "15",
            "chName",
            "/tmp/fstest/origin",
            "/tmp/fstest/destination",
        )
        result = self.sut._CreateMetadata2__generateMetadata(fake)
        with open("tests/resources/createMetadata_1.xml", "rb") as xml_file:
            comparison = xml_file.read()
            self.__assertXmlEqual(result, comparison)
            self.__assertXmlMatchesComicInfo(result)

    def test_executeToString_KRRegion_NoMangaField(self):
        fake = Chapter(
            1000,
            "seriesN",
            "15",
            "chName",
            "/tmp/fstest/origin",
            "/tmp/fstest/destination",
            countryOfOrigin="KR",
        )
        result = self.sut._CreateMetadata2__generateMetadata(fake)
        with open("tests/resources/createMetadata_2.xml", "rb") as xml_file:
            comparison = xml_file.read()
            self.__assertXmlEqual(result, comparison)
            self.__assertXmlMatchesComicInfo(result)
