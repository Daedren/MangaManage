import os
from pathlib import Path
import shutil
from enum import Enum
import re
from cross.decorators import Logger


class FilesystemInterface:
    def deleteArchive(self, anilistId, chapterNumber): pass
    def deleteFolder(self, location: str): pass
    def quarantineSeries(self, anilistId: str): pass
    def restoreQuarantinedArchive(self, anilistId: str): pass
    def getQuarantinedSeries(self): pass
    def saveFile(self, stringData: str, filepath: Path): pass

class FilesystemFakeGateway(FilesystemInterface):
    def deleteArchive(self, anilistId, chapterNumber): pass

    def deleteFolder(self, location: str):
        if not os.path.exists(location):
            print("source chapter doesn't exist")
            print(location)
            return
        print(f'WOULD delete recursive directory at {location}')


@Logger
class FilesystemGateway(FilesystemInterface):
    def __init__(self, sourceFolder: str, archiveFolder: str, quarantineFolder: str) -> None:
        self.mangas = sourceFolder
        self.archiveRootPath = Path(archiveFolder)
        self.quarantineFolder = Path(quarantineFolder)

        self.archiveRootPath.mkdir(parents=True, exist_ok=True)
        self.quarantineFolder.mkdir(parents=True, exist_ok=True)
        super().__init__()

    def deleteArchive(self, anilistId, chapterNumber):
        archResult = self.__deleteChapter(self.archiveRootPath, anilistId, chapterNumber)
        quaraResult = self.__deleteChapter(self.quarantineFolder, anilistId, chapterNumber)
        
        if not archResult and not quaraResult:
            self.logger.debug(f"Couldn't delete archive for {anilistId} at {chapterNumber}")

    
    def __deleteChapter(self, rootPath, anilistId, chapterNumber) -> bool:
        archiveSeriesPath = Path.joinpath(rootPath, f"{anilistId}")
        if not archiveSeriesPath.exists():
            return False
        archiveChapterPath = Path.joinpath(
            archiveSeriesPath, f"{chapterNumber}.cbz")
        if archiveChapterPath.exists():
            archiveChapterPath.unlink()
        else:
            return False

        is_empty = not any(archiveSeriesPath.iterdir())
        if is_empty:
            archiveSeriesPath.rmdir()
        return True

    def deleteFolder(self, location: str):
        chapterPath = Path(location)
        seriesPath = chapterPath.parent
        if not chapterPath.exists():
            self.logger.debug("source chapter doesn't exist")
            self.logger.debug(location)
            return

        shutil.rmtree(location)

        # Parent
        if (seriesPath.exists) and (not any(seriesPath.iterdir())):
            shutil.rmtree(seriesPath.resolve())
    
    def quarantineSeries(self, anilistId: str):
        archiveSeriesPath = Path.joinpath(self.archiveRootPath, f"{anilistId}")
        quarantineSeriesPath = Path.joinpath(self.quarantineFolder, f"{anilistId}")
        
        quarantineSeriesPath.mkdir(parents=True, exist_ok=True)
        for file in archiveSeriesPath.iterdir():
            filename = file.name
            trg_path = quarantineSeriesPath.joinpath(filename)
            file.rename(trg_path)
        archiveSeriesPath.rmdir()


    def restoreQuarantinedArchive(self, anilistId: str):
        archiveSeriesPath = Path.joinpath(self.archiveRootPath, f"{anilistId}")
        quarantineSeriesPath = Path.joinpath(self.quarantineFolder, f"{anilistId}")
        
        archiveSeriesPath.mkdir(parents=True, exist_ok=True)
        for file in quarantineSeriesPath.iterdir():
            filename = file.name
            trg_path = archiveSeriesPath.joinpath(filename)
            file.rename(trg_path)
        quarantineSeriesPath.rmdir()
    
    def getQuarantinedSeries(self):
        quarantinedSeries = self.quarantineFolder.iterdir()
        trackerIds = list(map(lambda x: int(x.stem), quarantinedSeries))
        return trackerIds
    
    def saveFile(self, stringData: str, filepath: Path):
        with open(filepath.resolve(), 'wb') as file:
            file.write(stringData)
    