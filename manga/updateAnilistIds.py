from typing import Optional, Tuple
from cross.decorators import Logger
from manga.gateways.database import DatabaseGateway
from manga.gateways.anilist import AnilistGateway
from models.tracker import TrackerSeries
from .utils.pylev import levenschtein


@Logger
class UpdateTrackerIds:
    """Updates local DB with tracker's IDs"""

    def __init__(self, database: DatabaseGateway, anilist: AnilistGateway) -> None:
        self.anilist = anilist
        self.database = database

    def __tryTuple(
        self, entry: TrackerSeries, series: str, force=False, interactive=False
    ) -> Optional[Tuple[str, str]]:
        series_to_match = series.lower()
        bestMatch = ""
        bestMatchDistance = 999

        for tracker_title in entry.titles:
            prepped_title = tracker_title.lower()
            rdistance = levenschtein(series_to_match, prepped_title)
            if rdistance < bestMatchDistance:
                bestMatch = prepped_title
                bestMatchDistance = rdistance

        if force:
            return (series, entry.tracker_id)

        if bestMatchDistance <= 4:
            self.logger.info(f'found "{bestMatch}"')
            return (series, entry.tracker_id)
        elif bestMatchDistance < 10:
            self.logger.info(
                f"possible match at {bestMatchDistance} - {bestMatch} [{entry.tracker_id}]"
            )
            if interactive:
                userValue = input("Enter Anilist ID: ")
                return (series, userValue)
        return None

    def updateFor(self, series, interactive=False) -> Optional[str]:
        self.logger.info("Updating for " + series)
        entries = self.anilist.getAllEntries()
        for entry in entries:
            result = self.__tryTuple(entry, series, interactive=interactive)
            if result is not None:
                self.database.insertTracking(result[0], result[1])
                return result[1]

    def manualUpdateFor(self, series, anilistId):
        self.database.insertTracking(series, anilistId)

    def updateAll(self):
        """Updates all series in DB that don't have tracker IDs"""
        entries = self.anilist.getAllEntries()

        rows = self.database.getAllSeriesWithoutTrackerIds()

        toadd = list()

        for entry in entries:
            for row in rows:
                result = self.__tryTuple(entry, row["chapter"])
                if result is not None:
                    toadd.append(result)

        for newtuple in toadd:
            self.database.insertTracking(seriesName=newtuple[0], anilistId=newtuple[1])
