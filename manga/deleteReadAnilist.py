from models.manga import SimpleChapter
from cross.decorators import Logger
from manga.gateways.utils.databaseModels import AnilistSeries
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from manga.gateways.anilist import AnilistGateway
import sys

sys.path = [""] + sys.path


@Logger
class DeleteReadChapters:
    """Deletes stored manga that has been marked as read on Anilist"""

    def __init__(
        self,
        anilist: AnilistGateway,
        filesystem: FilesystemInterface,
        database: DatabaseGateway,
    ) -> None:
        self.anilist = anilist
        self.filesystem = filesystem
        self.database = database

    def execute(self):
        series = self.anilist.getAllEntries()

        deleted_chapters: [SimpleChapter] = []

        rows = self.database.getAllSeriesWithLocalFiles()
        row: AnilistSeries
        for row in rows:
            completion = False
            dbSeries = row.seriesName
            dbAnilistId = row.anilistId
            anilistSeries = series.get(dbAnilistId)
            if anilistSeries is None:
                self.logger.error("No series in anilist for %s" % dbAnilistId)
                continue
            # Progress at anilist of series.
            lastReadChapter = anilistSeries.progress
            lastReleasedChapter = anilistSeries.chapters
            if lastReleasedChapter == lastReadChapter:
                completion = True
                lastReadChapter += 30 # Making sure to delete all stored chapters
            chaptersToDelete = self.database.getChaptersForSeriesBeforeNumber(
                dbAnilistId, lastReadChapter
            )
            for chap in chaptersToDelete:
                chapterToDelete = chap["chapter"]
                deleted_chapters.append(SimpleChapter(dbAnilistId, chapterToDelete))
                self.logger.info(
                    "Deleting "
                    + dbSeries
                    + " - ("
                    + str(chapterToDelete)
                    + " <= "
                    + ("Completion" if completion else str(lastReadChapter))
                    + ")"
                )
                self.filesystem.deleteArchive(dbAnilistId, chapterToDelete)
                self.database.deleteChapter(dbAnilistId, chapterToDelete)
        return deleted_chapters
