import os
import zipfile
from pathlib import Path
import shutil
from cross.decorators import Logger
from typing import BinaryIO


class FilesystemInterface:
    def deleteArchive(self, anilistId, chapterNumber):
        pass

    def deleteSourceChapter(self, location: str):
        pass

    def quarantineSeries(self, anilistId: str):
        pass

    def restoreQuarantinedArchive(self, anilistId: str):
        pass

    def getQuarantinedSeries(self):
        pass

    def saveFileToPath(self, stringData: str, filepath: Path):
        pass

    def saveFile(self, stringData: str, file: BinaryIO):
        pass

    def compress_chapter(self, archive_path: Path, source_path: Path):
        '''Compresses chapter at source_path with destination archive_path'''
        pass

    def move_source_cbz_to_archive(self, archive_path: Path, source_path: Path):
        '''In this case, both source and archive paths must be the CBZ paths'''
        pass

    def put_comicinfo_in_cbz(self, comicinfo: Path, cbz: Path):
        pass


class FilesystemFakeGateway(FilesystemInterface):
    def deleteArchive(self, anilistId, chapterNumber):
        pass

    def deleteSourceChapter(self, location: str):
        if not os.path.exists(location):
            print("source chapter doesn't exist")
            print(location)
            return
        print(f"WOULD delete recursive directory at {location}")


@Logger
class FilesystemGateway(FilesystemInterface):
    def __init__(
        self, archiveFolder: str, quarantineFolder: str
    ) -> None:
        self.archiveRootPath = Path(archiveFolder)
        self.quarantineFolder = Path(quarantineFolder)

        self.archiveRootPath.mkdir(parents=True, exist_ok=True)
        self.quarantineFolder.mkdir(parents=True, exist_ok=True)
        super().__init__()

    def deleteArchive(self, anilistId, chapterNumber):
        archResult = self.__deleteChapter(
            self.archiveRootPath, anilistId, chapterNumber
        )
        quaraResult = self.__deleteChapter(
            self.quarantineFolder, anilistId, chapterNumber
        )

        if not archResult and not quaraResult:
            self.logger.debug(
                f"Couldn't delete archive for {anilistId} at {chapterNumber}"
            )

    def __deleteChapter(self, rootPath, anilistId, chapterNumber) -> bool:
        archiveSeriesPath = Path.joinpath(rootPath, f"{anilistId}")
        if not archiveSeriesPath.exists():
            return False
        archiveChapterPath = Path.joinpath(archiveSeriesPath, f"{chapterNumber}.cbz")
        if archiveChapterPath.exists():
            archiveChapterPath.unlink()
        else:
            return False

        is_empty = not any(archiveSeriesPath.iterdir())
        if is_empty:
            archiveSeriesPath.rmdir()
        return True

    def deleteSourceChapter(self, location: str):
        chapterPath = Path(location)
        seriesPath = chapterPath.parent
        sourcePath = seriesPath.parent
        
        if chapterPath.exists():
            if chapterPath.is_dir():
                shutil.rmtree(location)
            else:
                chapterPath.unlink()

        # Parent - Series
        if (seriesPath.exists) and (not any(seriesPath.iterdir())):
            shutil.rmtree(seriesPath.resolve())

        # Grandparent - Source
        if (sourcePath.exists) and (not any(sourcePath.iterdir())):
            shutil.rmtree(sourcePath.resolve())

    def quarantineSeries(self, anilistId: str):
        archiveSeriesPath = Path.joinpath(self.archiveRootPath, f"{anilistId}")

        quarantineSeriesPath = Path.joinpath(self.quarantineFolder, f"{anilistId}")

        if not archiveSeriesPath.exists():
            return

        if quarantineSeriesPath.exists():
            self.logger.info(f"Updating {anilistId} in quarantine")
        else:
            self.logger.info(f"Adding {anilistId} to quarantine")
            quarantineSeriesPath.mkdir(parents=True)

        for file in archiveSeriesPath.iterdir():
            filename = file.name
            trg_path = quarantineSeriesPath.joinpath(filename)
            file.rename(trg_path)
        archiveSeriesPath.rmdir()

    def restoreQuarantinedArchive(self, anilistId: str):
        archiveSeriesPath = Path.joinpath(self.archiveRootPath, f"{anilistId}")
        quarantineSeriesPath = Path.joinpath(self.quarantineFolder, f"{anilistId}")

        self.logger.info(f"Removing {anilistId} from quarantine")
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

    def saveFileToPath(self, stringData: str, filepath: Path):
        with open(filepath.resolve(), "wb") as file:
            file.write(stringData)

    def saveFile(self, stringData: str, file: BinaryIO):
        file.write(stringData)
        file.flush()

    def compress_chapter(self, archive_path: Path, source_path: Path):
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        destination = archive_path.resolve()
        ziphandler = zipfile.ZipFile(destination, "w", zipfile.ZIP_STORED)
        path = source_path.resolve()
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.startswith("."):
                    continue
                ziphandler.write(os.path.join(root, file), file)
        ziphandler.close()
        
    def move_source_cbz_to_archive(self, archive_path: Path, source_path: Path):
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.resolve().replace(archive_path.resolve())
        
    def put_comicinfo_in_cbz(self, comicinfo: Path, cbz: Path):
        with zipfile.ZipFile(cbz.resolve(), 'a') as zip_file:
            zip_file.write(comicinfo.resolve(), 'ComicInfo.xml')
