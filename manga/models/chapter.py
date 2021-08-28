from pathlib import Path


class Chapter:
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
