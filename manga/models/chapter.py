from pathlib import Path


class SimpleChapter:
    def __init__(
        self,
        anilistId: int,
        chapterNumber: str,
    ):
        self.anilistId = anilistId
        self.chapterNumber = chapterNumber

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, SimpleChapter):
            return (
                self.anilistId == other.anilistId
                and self.chapterNumber == other.chapterNumber
            )
        return False

    def __hash__(self):
        return hash(self.anilistId) + hash(self.chapterNumber)


class Chapter(SimpleChapter):
    def __init__(
        self,
        anilistId: int,
        seriesName: str,
        chapterNumber: str,
        chapterName: str,
        sourcePath: Path,
        archivePath: Path,
        countryOfOrigin: str = "JP",
    ):
        self.anilistId = anilistId
        self.seriesName = seriesName
        self.chapterNumber = chapterNumber
        self.chapterName = chapterName
        self.sourcePath = sourcePath
        self.archivePath = archivePath
        self.countryOfOrigin = countryOfOrigin
