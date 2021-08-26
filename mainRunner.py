from manga.updateAnilistIds import UpdateTrackerIds
import html
from manga.mangagetchapter import CalculateChapterName
from manga.deleteReadAnilist import DeleteReadChapters
from manga.missingChapters import CheckGapsInChapters
from manga.createMetadata import CreateMetadataInterface
from manga.gateways.pushover import PushServiceInterface
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from manga.models.chapter import Chapter
from typing import Optional
import glob
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import datetime

# for each folder in sources
# databas -> select anilist id where series=x
# getChapter -> title

class MainRunner:
    def __init__(self,
                 sourceFolder: str,
                 archiveFolder: str,
                 database: DatabaseGateway,
                 filesystem: FilesystemInterface,
                 push: PushServiceInterface,
                 missingChapters: CheckGapsInChapters,
                 deleteReadChapters: DeleteReadChapters,
                 calcChapterName: CalculateChapterName,
                 updateTrackerIds: UpdateTrackerIds,
                 createMetadata: CreateMetadataInterface,
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
        self.createMetadata = createMetadata

    def execute(self):
        numberOfNewChapters = 0
        dateScriptStart = datetime.datetime.now()
        # Globs chapters
        for chapterPathStr in glob.iglob(f'{self.sourceFolder}/*/*/*'):
            print(chapterPathStr)
            # Inferring information from files
            chapterPath = Path(chapterPathStr)
            chapterName = html.unescape(chapterPath.name)
            seriesName = html.unescape(chapterPath.parent.name)
            anilistId = self.database.getAnilistIDForSeries(seriesName)
            chapterNumber = self.calcChapterName.execute(chapterName, anilistId)
            estimatedArchivePath = self.generateArchivePath(anilistId, chapterNumber)
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
                estimatedArchivePath = self.generateArchivePath(foundAnilistId, chapterNumber)
                chapterData.archivePath = estimatedArchivePath
                if not foundAnilistId or foundAnilistId is None:
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
            print("Chapter gaps ---")
            print(self.missingChapters.getGapsFromChaptersSince(dateScriptStart))
            print("---")
            self.pushNotification.sendPush(
                f'{numberOfNewChapters} new chapters downloaded')
        self.deleteReadChapters.execute()
    
    def generateArchivePath(self, anilistId, chapterNumber):
        return Path(self.archiveFolder).joinpath(
                f'{anilistId}/{chapterNumber}.cbz')

    def findAnilistIdForSeries(self, series: str) -> Optional[str]:
        return self.updateTrackerIds.updateFor(series)

    def setupMetadata(self, chapter: Chapter):
        self.createMetadata.execute(chapter)

    def compressChapter(self, chapter: Chapter):
        destination = chapter.archivePath.resolve()
        ziphandler = zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED)
        path = chapter.sourcePath.resolve()
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.startswith('.'):
                    continue
                ziphandler.write(os.path.join(root, file),
                                 file)
        ziphandler.close()

    def insertInDatabase(self, chapter: Chapter):
        self.database.insertChapter(
            chapter.seriesName,
            chapter.chapterNumber,
            str(chapter.archivePath.resolve()),
            str(chapter.sourcePath.resolve()))
