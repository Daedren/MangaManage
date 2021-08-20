from manga.updateAnilistIds import UpdateTrackerIds
from manga.mangagetchapter import CalculateChapterName
from manga.deleteReadAnilist import DeleteReadChapters
from manga.missingChapters import CheckGapsInChapters
from manga.gateways.pushover import PushServiceInterface
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemGateway
from typing import Optional
import glob
import os
from dependency_injector import containers, providers
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import datetime

# for each folder in sources
# databas -> select anilist id where series=x
# getChapter -> title


class Chapter:
    def __init__(self,
                 anilistId: int,
                 seriesName: str,
                 chapterNumber: str,
                 chapterName: str,
                 sourcePath: Path,
                 archivePath: Path):
        self.anilistId = anilistId
        self.seriesName = seriesName
        self.chapterNumber = chapterNumber
        self.chapterName = chapterName
        self.sourcePath = sourcePath
        self.archivePath = archivePath


class MainRunner:
    def __init__(self,
                 sourceFolder: str,
                 archiveFolder: str,
                 database: DatabaseGateway,
                 filesystem: FilesystemGateway,
                 push: PushServiceInterface,
                 missingChapters: CheckGapsInChapters,
                 deleteReadChapters: DeleteReadChapters,
                 calcChapterName: CalculateChapterName,
                 updateTrackerIds: UpdateTrackerIds
                 ) -> None:
        self.database = database
        self.pushNotification = push
        self.filesystem = filesystem
        self.sourceFolder = sourceFolder
        self.archiveFolder = archiveFolder
        self.missingChapters = missingChapters
        self.deleteReadChapters = deleteReadChapters
        self.calcChapterName = calcChapterName
        self.updateTrackerIds = updateTrackerIds

    def execute(self):
        numberOfNewChapters = 0
        dateScriptStart = datetime.datetime.now()
        # Globs chapters
        for chapterPathStr in glob.iglob(f'{self.sourceFolder}/*/*/*'):
            print(chapterPathStr)
            # Inferring information from files
            chapterPath = Path(chapterPathStr)
            chapterName = chapterPath.name
            seriesName = chapterPath.parent.name
            anilistId = self.database.getAnilistIDForSeries(seriesName)
            chapterNumber = self.calcChapterName.execute(chapterName, anilistId)
            estimatedArchivePath = Path(self.archiveFolder).joinpath(
                f'{anilistId}/{chapterNumber}.cbz')
            chapterData = Chapter(anilistId, seriesName, chapterNumber,
                                  chapterName, chapterPath, estimatedArchivePath)
            print(seriesName)
            print(chapterName)
            print(anilistId)
            print(chapterNumber)
            print(estimatedArchivePath)

            isChapterOnDB = self.database.doesExistChapterAndAnilist(
                anilistId, chapterNumber)
            if not anilistId or anilistId is None:
                foundAnilistId = self.findAnilistIdForSeries(seriesName)
                if foundAnilistId is None:
                    print(f'No anilistId for {chapterData.seriesName}')
                    return
                chapterData.anilistId = foundAnilistId
            if not isChapterOnDB:
                chapterData.archivePath.parent.mkdir(
                    parents=True, exist_ok=True)
                self.setupMetadata(chapterData)
                self.compressChapter(chapterData)
                self.insertInDatabase(chapterData)
                numberOfNewChapters += 1
                self.filesystem.deleteFolder(
                    location=chapterPathStr)
            else:
                print(f'Source exists but already in db')
            print("***")
        if numberOfNewChapters > 0:
            self.missingChapters.getGapsFromChaptersSince(dateScriptStart)
            self.pushNotification.sendPush(
                f'{numberOfNewChapters} new chapters downloaded')
        self.deleteReadChapters.execute()

    def findAnilistIdForSeries(self, series: str) -> Optional[str]:
        return self.updateTrackerIds.updateFor(series)

    def setupMetadata(self, chapter: Chapter):
        root = ET.Element("ComicInfo")
        ET.SubElement(root, "Series").text = chapter.seriesName
        ET.SubElement(root, "Title").text = chapter.chapterName
        ET.SubElement(root, "Number").text = chapter.chapterNumber
        ET.SubElement(root, "Manga").text = "YesAndRightToLeft"
        tree = ET.ElementTree(root)
        destination = chapter.sourcePath.joinpath('ComicInfo.xml')
        tree.write(destination.resolve(),
                   encoding='utf8', xml_declaration=True)

    def compressChapter(self, chapter: Chapter):
        destination = chapter.archivePath.resolve()
        ziphandler = zipfile.ZipFile(destination, 'w', zipfile.ZIP_LZMA)
        path = chapter.sourcePath.resolve()
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.startswith('.'):
                    continue
                ziphandler.write(os.path.join(root, file),
                                 file)
                #os.path.relpath(os.path.join(root, file),
                #                os.path.join(path, '..')))
        ziphandler.close()

    def insertInDatabase(self, chapter: Chapter):
        self.database.insertChapter(
            chapter.seriesName,
            chapter.chapterNumber,
            str(chapter.archivePath.resolve()),
            str(chapter.sourcePath.resolve()))

    if __name__ == "__main__":
        print(execute())
