from cross.decorators import Logger
from manga.gateways.utils.databaseModels import AnilistSeries
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from manga.gateways.anilist import AnilistGateway
import sys

sys.path = [""] + sys.path


@Logger
class DeleteReadChapters:
    ''' Deletes stored manga that has been marked as read on Anilist'''
    def __init__(
        self,
        anilist: AnilistGateway,
        filesystem: FilesystemInterface,
        database: DatabaseGateway,
    ) -> None:
        self.anilist = anilist
        self.filesystem = filesystem
        self.database = database
        pass

    def execute(self):
        entries = self.anilist.getAllEntries()
        series = dict()
        for entry in entries:
            series[entry["media"]["id"]] = entry
        # Remember that anilist only stores integers for chapter numbers!
        rows = self.database.getAllSeriesWithLocalFiles()
        row: AnilistSeries
        for row in rows:
            dbSeries = row.seriesName
            dbAnilistId = row.anilistId
            anilistSeries = series.get(dbAnilistId)
            if anilistSeries is None:
                self.logger.error("No series in anilist for %s" % dbAnilistId)
                continue
            lastReadChapter = series[dbAnilistId][
                "progress"
            ]  # Progress at anilist of series.
            lastReleasedChapter = series[dbAnilistId]["media"]["chapters"]
            if (
                lastReleasedChapter == lastReadChapter
            ):  # Chapter is null if series is still releasing
                lastReadChapter += 30
            chaptersToDelete = self.database.getChaptersForSeriesBeforeNumber(
                dbAnilistId, lastReadChapter
            )
            # Reminder: file deletion will only be permenant if they're synced
            for chap in chaptersToDelete:
                chapterToDelete = chap["chapter"]
                self.logger.info(
                    "Deleting "
                    + dbSeries
                    + " - ("
                    + str(chapterToDelete)
                    + " <= "
                    + str(lastReadChapter)
                    + ")"
                )
                self.filesystem.deleteArchive(dbAnilistId, chapterToDelete)
                # self.filesystem.deleteOriginal(dbSeries, chapterToDelete)
                self.database.deleteChapter(dbAnilistId, chapterToDelete)
