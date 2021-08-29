from manga.gateways.mangaupd import MangaUpdatesGateway
from manga.gateways.database import DatabaseGateway
from manga.gateways.anilist import TrackerGatewayInterface
import time


class CheckForUpdates:
    def __init__(
        self,
        mangaUpdatesGateway: MangaUpdatesGateway,
        database: DatabaseGateway,
        tracker: TrackerGatewayInterface,
    ):
        self.mangaUpdatesGateway = mangaUpdatesGateway
        self.database = database
        self.tracker = tracker

    def updateLocalIds(self):
        allLocalSeries = self.database.getAllSeries()

        allLocalSeriesWithoutIds = filter(
            lambda x: x.mangaUpdatesId is None, allLocalSeries
        )

        for row in allLocalSeriesWithoutIds:
            mangaUpdId = self.mangaUpdatesGateway.searchForSeries(row.seriesName)
            self.database.insertMangaUpdt(row.anilistId, mangaUpdatesId=mangaUpdId)
            time.sleep(5)

    def checkForUpdates(self):
        # This isn't checking:
        # - Series that were never in db (not in anilist)
        allTrackerEntries = self.tracker.getAllEntries()

        runningSeries = filter(
            lambda x: x["media"]["chapters"] is None, allTrackerEntries
        )

        # Perhaps should get anilistIDs from db, rather than API
        for series in runningSeries:
            time.sleep(5)
            anilistId = series["media"]["id"]
            dbInfo = self.database.getHighestChapterAndLastUpdatedForSeries(anilistId)
            if not dbInfo:
                continue
            if not dbInfo["mangaUpdatesId"]:
                continue
            releaseNum = self.mangaUpdatesGateway.latestReleaseForId(
                dbInfo["mangaUpdatesId"]
            )
            latestInDb = dbInfo["max_chapter"]
            if latestInDb is None:
                latestInDb = 0
            try:
                intReleaseNum = int(releaseNum)
                if latestInDb < intReleaseNum:
                    print(
                        f"{dbInfo['series']} - has {latestInDb} in DB. Latest chapter is {intReleaseNum}"
                    )
            except ValueError:
                continue
