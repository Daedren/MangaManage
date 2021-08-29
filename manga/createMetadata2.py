from manga.models.chapter import Chapter
from cross.decorators import Logger
from manga.gateways.filesystem import FilesystemInterface
from .createMetadata import CreateMetadataInterface
from lxml import etree


@Logger
class CreateMetadata2(CreateMetadataInterface):
    """lxml implementation of CreateMetadataInterface."""

    def __init__(self, filesystem: FilesystemInterface()):
        self.filesystem = filesystem

    def execute(self, chapter: Chapter):
        result = self.__generateMetadata(chapter)
        destination = chapter.sourcePath.joinpath("ComicInfo.xml")
        self.filesystem.saveFile(stringData=result, filepath=destination)

    def __generateMetadata(self, chapter: Chapter) -> str:
        root = etree.Element("ComicInfo")
        etree.SubElement(root, "Title").text = chapter.chapterName
        etree.SubElement(root, "Series").text = chapter.seriesName
        etree.SubElement(root, "Number").text = chapter.chapterNumber
        if chapter.countryOfOrigin == "JP":
            etree.SubElement(root, "Manga").text = "YesAndRightToLeft"
        return etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="utf-8"
        )
        # xmlAsStr =  etree.tostring(root, pretty_print=True, encoding=str)
        # return f'<?xml version="1.0" encoding="utf-8"?>\n{xmlAsStr}'
