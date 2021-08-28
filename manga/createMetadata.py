import xml.etree.ElementTree as ET
from manga.models.chapter import Chapter
from cross.decorators import Logger
from manga.gateways.filesystem import FilesystemInterface


class CreateMetadataInterface:
    def execute(self, chapter: Chapter):
        pass


@Logger
class CreateMetadata(CreateMetadataInterface):
    def __init__(self, filesystem: FilesystemInterface()):
        self.filesystem = filesystem

    def executeToString(self, chapter: Chapter) -> str:
        tree = self.__generateMetadata(chapter)
        root = tree.getroot()
        xmlstr = ET.tostring(root, encoding="utf8", method="xml")
        self.logger.info(xmlstr)
        return xmlstr

    def execute(self, chapter: Chapter):
        tree = self.__generateMetadata(chapter)
        destination = chapter.sourcePath.joinpath("ComicInfo.xml")

        tree.write(destination.resolve(), encoding="utf8", xml_declaration=True)

    def __generateMetadata(self, chapter: Chapter) -> ET.ElementTree:
        root = ET.Element("ComicInfo")
        ET.SubElement(root, "Series").text = chapter.seriesName
        ET.SubElement(root, "Title").text = chapter.chapterName
        ET.SubElement(root, "Number").text = chapter.chapterNumber

        if chapter.countryOfOrigin == "JP":
            ET.SubElement(root, "Manga").text = "YesAndRightToLeft"

        tree = ET.ElementTree(root)
        return tree
