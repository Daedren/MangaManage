import xml.etree.ElementTree as ET
from typing import BinaryIO
from models.manga import Chapter
from cross.decorators import Logger
from manga.gateways.filesystem import FilesystemInterface
from pathlib import Path


class CreateMetadataInterface:
    def execute(self, chapter: Chapter, output: BinaryIO) -> Path:
        """Creates a ComicInfo.xml for the given chapter.
        Writes the data into the output parameter
        """
        pass


@Logger
class CreateMetadata(CreateMetadataInterface):
    """ElementTree implementation of CreateMetadataInterface.
    Use CreateMetadata2 if possible."""

    def __init__(self, filesystem: FilesystemInterface()):
        self.filesystem = filesystem

    def executeToString(self, chapter: Chapter) -> str:
        tree = self.__generateMetadata(chapter)
        root = tree.getroot()
        xmlstr = ET.tostring(root, encoding="utf8", method="xml")
        self.logger.info(xmlstr)
        return xmlstr

    def execute(self, chapter: Chapter, output: BinaryIO) -> Path:
        tree = self.__generateMetadata(chapter)
        tree.write(output, encoding="utf8", xml_declaration=True)

    def __generateMetadata(self, chapter: Chapter) -> ET.ElementTree:
        root = ET.Element("ComicInfo")
        ET.SubElement(root, "Series").text = chapter.seriesName
        ET.SubElement(root, "Title").text = chapter.chapterName
        ET.SubElement(root, "Number").text = chapter.chapterNumber

        tree = ET.ElementTree(root)
        return tree
