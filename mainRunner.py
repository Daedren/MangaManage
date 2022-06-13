import datetime
import glob
import html
import tempfile
from typing import List, Optional, Set, BinaryIO
from pathlib import Path
from cross.decorators import Logger
from manga.updateAnilistIds import UpdateTrackerIds
from manga.mangagetchapter import CalculateChapterName
from manga.deleteReadAnilist import DeleteReadChapters
from manga.missingChapters import CheckGapsInChapters
from manga.createMetadata import CreateMetadataInterface
from manga.gateways.pushover import PushServiceInterface
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from models.manga import Chapter, MissingChapter

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
        try:
            new_chapters: Set[Chapter] = set()
            dateScriptStart = datetime.datetime.now()
            # Globs chapters
            for chapterPathStr in glob.iglob(f"{self.sourceFolder}/*/*/*"):
                self.logger.info(f"Parsing: {chapterPathStr}")
                # Inferring information from files
                chapterPath = Path(chapterPathStr)
                chapterName = html.unescape(chapterPath.stem)
                seriesName = html.unescape(chapterPath.parent.stem)
                anilistId = self.database.getAnilistIDForSeries(seriesName)
                chapterNumber = self.calcChapterName.execute(chapterName, anilistId)
                estimatedArchivePath = self.generateArchivePath(
                    anilistId, chapterNumber
                )
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
                    foundAnilistId = self.findAnilistIdForSeries(
                        seriesName, interactive=interactive
                    )
                    estimatedArchivePath = self.generateArchivePath(
                        foundAnilistId, chapterNumber
                    )
                    chapterData.archivePath = estimatedArchivePath
                    if not foundAnilistId or foundAnilistId is None:
                        self.logger.error(f"No anilistId for {chapterData.seriesName}")
                        return
                    chapterData.anilistId = foundAnilistId
                if not isChapterOnDB:
                    # Creates temporary place to store metadata before putting in CBZ
                    with tempfile.NamedTemporaryFile() as metadata_file:
                        self.setupMetadata(chapterData, output=metadata_file)
                        self.prepareChapterCBZ(chapterData, Path(metadata_file.name))
                        self.insertInDatabase(chapterData)
                        new_chapters.add(chapterData)
                        self.filesystem.deleteFolder(location=chapterPathStr)
                else:
                    self.logger.info("Source exists but chapter's already in db")
                    self.filesystem.deleteFolder(location=chapterPathStr)
            deleted_chapters = self.deleteReadChapters.execute()
            for deleted_chapter in deleted_chapters:
                if deleted_chapter in new_chapters:
                    new_chapters.remove(deleted_chapter)

            if len(new_chapters) > 0:
                gaps = self.missingChapters.getGapsFromChaptersSince(dateScriptStart)
                self.send_push(new_chapters, gaps)
        except Exception as thrown_exception:
            self.logger.error("Exception thrown")
            self.logger.error(str(thrown_exception))
            self.send_error(thrown_exception)

    def generateArchivePath(self, anilistId, chapterNumber):
        return Path(self.archiveFolder).joinpath(f"{anilistId}/{chapterNumber}.cbz")

    def findAnilistIdForSeries(self, series: str, interactive=False) -> Optional[str]:
        return self.updateTrackerIds.updateFor(series, interactive=interactive)

    def setupMetadata(self, chapter: Chapter, output: BinaryIO):
        self.createMetadata.execute(chapter, output)

    def prepareChapterCBZ(self, chapter: Chapter, metadata: Path):
        # Source file is CBZ or a folder?
        if chapter.sourcePath.is_file():
            self.filesystem.move_source_cbz_to_archive(
                chapter.archivePath, chapter.sourcePath
            )
        else:
            self.filesystem.compress_chapter(
                archive_path=chapter.archivePath, source_path=chapter.sourcePath
            )
        self.filesystem.put_comicinfo_in_cbz(
            cbz=chapter.archivePath, comicinfo=metadata
        )

    def insertInDatabase(self, chapter: Chapter):
        self.database.insertChapter(
            chapter.seriesName,
            chapter.chapterNumber,
            str(chapter.archivePath.resolve()),
            str(chapter.sourcePath.resolve()),
        )

    def send_push(self, chapters: Set[Chapter], gaps: List[MissingChapter]):
        chapters_plural = "chapters" if len(chapters) > 1 else "chapter"

        base = f"{len(chapters)} new {chapters_plural} downloaded\n\n"

        titles = map(lambda x: f"{x.seriesName} {x.chapterNumber}", chapters)
        sorted_titles = sorted(titles)

        chapters_body = "\n".join(sorted_titles)

        if len(gaps) > 0:
            missing_title = "Updated in quarantine:"
            missing_chapters = map(lambda x: f"{x.series_name}", gaps)
            missing_body = "\n".join(missing_chapters)
            chapters_body += "\n\n" + missing_title + "\n" + missing_body

        self.pushNotification.sendPush(base + chapters_body)

    def send_error(self, value: Exception):
        self.pushNotification.sendPush(str(value))
