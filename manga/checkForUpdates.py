import time
from decimal import Decimal
from manga.gateways.mangaupd import MangaUpdatesGateway
from manga.gateways.database import DatabaseGateway
from manga.gateways.anilist import TrackerGatewayInterface
from manga.mangagetchapter import CalculateChapterName
from cross.decorators import Logger 


@Logger
class CheckForUpdates:
    def __init__(
        self,
        mangaUpdatesGateway: MangaUpdatesGateway,
        database: DatabaseGateway,
        tracker: TrackerGatewayInterface,
        calculate_chapter_name: CalculateChapterName,
    ):
        self.mangaUpdatesGateway = mangaUpdatesGateway
        self.database = database
        self.tracker = tracker
        self.calculate_chapter_name = calculate_chapter_name

    def updateLocalIds(self):
        allTrackerEntries = self.tracker.getAllEntries(reading_only=True)
        dbTracker = self.database.getHighestChapterAndLastUpdatedForSeries()

        for anilistId, trackerData in allTrackerEntries.items():
            row = dbTracker.get(anilistId)
            if row is not None and row['mangaUpdatesId'] is not None:
                continue
            mangaUpdUrl = self.mangaUpdatesGateway.searchForSeries(trackerData.titles)
            mangaUpdId = self.mangaUpdatesGateway.getSeriesId(mangaUpdUrl)
            self.database.insertMangaUpdt(anilistId, mangaUpdatesId=mangaUpdId)
            time.sleep(2)
    
    def checkForUpdates(self):
        allTrackerEntries = self.tracker.getAllEntries(reading_only=True).values() # For checking if the series is actually running
        dbTracker = self.database.getHighestChapterAndLastUpdatedForSeries()

        # allTrackerEntries = filter(lambda x: x.tracker_id == 44685, allTrackerEntries)

        for series in allTrackerEntries: 
            time.sleep(2)
            anilistId = series.tracker_id
            dbInfo = dbTracker.get(anilistId)
            self.logger.debug('----------')
            self.logger.debug(series.titles[0])

            if not dbInfo:
                self.logger.debug('Nothing in DB')
                continue
            mangaUpdId = dbInfo["mangaUpdatesId"]
            latestInDb = dbInfo["max_chapter"] or 0
            latestInMangaUpd = dbInfo["latestChapter"] or 0
            if not dbInfo["mangaUpdatesId"]:
                continue
            if latestInMangaUpd > latestInDb and series.progress < latestInMangaUpd:
                self.__print(series, latestInDb, latestInMangaUpd)
                continue
            releaseTitles = self.mangaUpdatesGateway.latestReleasesForId(mangaUpdId)
            if releaseTitles is None or len(releaseTitles) == 0:
                continue

            # Most recent doesn't necessarily mean it's the highest chapter
            releaseNum = max(map(lambda x: Decimal(self.calculate_chapter_name.execute(x, anilistId)), releaseTitles))
            if latestInDb is None:
                latestInDb = 0
            if releaseNum is None:
                continue
            try:
                intReleaseNum = int(releaseNum)
                self.database.updateMangaUpdtLatestChapter(mangaUpdId, intReleaseNum)
                if intReleaseNum > latestInDb and series.progress < intReleaseNum:
                    self.__print(series, latestInDb, intReleaseNum)
            except ValueError:
                continue
    
    def __print(self, series, latestInDb, latestInMangaUpd):
        print(
            (
                f"{series.titles[0]} ({series.tracker_id})",
                f"{latestInDb} in DB. Last read {series.progress}. ",
                f"Latest chapter is {latestInMangaUpd}",
            )
        )
