from manga.gateways.mangaupd import MangaUpdatesGateway
from manga.gateways.database import DatabaseGateway
from manga.gateways.anilist import TrackerGatewayInterface
from cross.decorators import Logger 


@Logger
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
        self.mangaUpdatesGateway.resetBackoffBudget()
        allTrackerEntries = self.tracker.getAllEntries(reading_only=True)
        dbTracker = self.database.getHighestChapterAndLastUpdatedForSeries()

        for anilistId, trackerData in allTrackerEntries.items():
            row = dbTracker.get(anilistId)
            if row is not None and row['mangaUpdatesId'] is not None:
                continue
            mangaUpdId = self.mangaUpdatesGateway.searchForSeries(trackerData.titles)
            if mangaUpdId is None:
                self.logger.warning("No MangaUpdates match for %s", trackerData.titles)
                continue
            self.database.insertMangaUpdt(anilistId, mangaUpdatesId=mangaUpdId)
    
    def checkForUpdates(self):
        self.mangaUpdatesGateway.resetBackoffBudget()
        allTrackerEntries = self.tracker.getAllEntries(reading_only=True).values() # For checking if the series is actually running
        dbTracker = self.database.getHighestChapterAndLastUpdatedForSeries()

        # allTrackerEntries = filter(lambda x: x.tracker_id == 44685, allTrackerEntries)

        for series in allTrackerEntries: 
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
            has_manga_updates_url = bool(dbInfo["mangaUpdatesUrl"])
            if (has_manga_updates_url and latestInMangaUpd > latestInDb
                    and series.progress < latestInMangaUpd):
                self.__log_update(series, latestInDb, latestInMangaUpd)
                continue
            latestChapter, mangaUpdatesUrl = (
                self.mangaUpdatesGateway.getSeriesDetailsForId(mangaUpdId)
            )
            if latestChapter is not None or mangaUpdatesUrl is not None:
                self.database.updateMangaUpdtLatestChapter(
                    mangaUpdId, latestChapter, mangaUpdatesUrl
                )
            if latestChapter is None:
                continue
            if latestChapter > latestInDb and series.progress < latestChapter:
                self.__log_update(series, latestInDb, latestChapter)
    
    def __log_update(self, series, latestInDb, latestInMangaUpd):
        self.logger.info(
            "%s (%s) | %s in DB. Last read %s. Latest chapter is %s",
            series.titles[0],
            series.tracker_id,
            latestInDb,
            series.progress,
            latestInMangaUpd,
        )
