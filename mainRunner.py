from cross.decorators import Logger
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
import datetime

# for each folder in sources
# databas -> select anilist id where series=x
# getChapter -> title


@Logger
class MainRunner:
    def __init__(
        self,
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

    def execute(self, interactive=False):
        numberOfNewChapters = 0
        dateScriptStart = datetime.datetime.now()
        # Globs chapters
        for chapterPathStr in glob.iglob(f"{self.sourceFolder}/*/*/*"):
            self.logger.debug(f"Parsing: {chapterPathStr}")
            # Inferring information from files
            chapterPath = Path(chapterPathStr)
            chapterName = html.unescape(chapterPath.name)
            seriesName = html.unescape(chapterPath.parent.name)
            anilistId = self.database.getAnilistIDForSeries(seriesName)
            chapterNumber = self.calcChapterName.execute(chapterName, anilistId)
            estimatedArchivePath = self.generateArchivePath(anilistId, chapterNumber)
            chapterData = Chapter(
                anilistId,
                seriesName,
                chapterNumber,
                chapterName,
                chapterPath,
                estimatedArchivePath,
            )
            self.logger.debug(f"Already had tracker ID: {anilistId}")

            isChapterOnDB = self.database.doesExistChapterAndAnilist(
                anilistId, chapterNumber
            )
            if not anilistId or anilistId is None:
                foundAnilistId = self.findAnilistIdForSeries(seriesName, interactive=interactive)
                estimatedArchivePath = self.generateArchivePath(
                    foundAnilistId, chapterNumber
                )
                chapterData.archivePath = estimatedArchivePath
                if not foundAnilistId or foundAnilistId is None:
                    self.logger.error(f"No anilistId for {chapterData.seriesName}")
                    return
                chapterData.anilistId = foundAnilistId
            if not isChapterOnDB:
                self.setupMetadata(chapterData)
                self.compressChapter(chapterData)
                self.insertInDatabase(chapterData)
                numberOfNewChapters += 1
                self.filesystem.deleteFolder(location=chapterPathStr)
            else:
                self.logger.info("Source exists but chapter's already in db")
                self.filesystem.deleteFolder(location=chapterPathStr)
        if numberOfNewChapters > 0:
            self.missingChapters.getGapsFromChaptersSince(dateScriptStart)
            self.pushNotification.sendPush(
                f"{numberOfNewChapters} new chapters downloaded"
            )
        self.deleteReadChapters.execute()

    def generateArchivePath(self, anilistId, chapterNumber):
        return Path(self.archiveFolder).joinpath(f"{anilistId}/{chapterNumber}.cbz")

    def findAnilistIdForSeries(self, series: str, interactive=False) -> Optional[str]:
        return self.updateTrackerIds.updateFor(series, interactive=interactive)

    def setupMetadata(self, chapter: Chapter):
        self.createMetadata.execute(chapter)

    def compressChapter(self, chapter: Chapter):
        self.filesystem.compress_chapter(chapter.archivePath, chapter.sourcePath)

    def insertInDatabase(self, chapter: Chapter):
        self.database.insertChapter(
            chapter.seriesName,
            chapter.chapterNumber,
            str(chapter.archivePath.resolve()),
            str(chapter.sourcePath.resolve()),
        )
