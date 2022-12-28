from typing import Optional
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

    class FoundEntry:
        "Model to hold find results"
        def __init__(self, series_name: str, tracker_entry: TrackerSeries):
            self.series_name = series_name
            self.tracker_entry = tracker_entry


    def __findTrackerForSeries(
        self, tracker_entries: [TrackerSeries], series: str, force=False, interactive=False
    ) -> FoundEntry:
        series_to_match = series.lower()
        bestMatch: Optional[TrackerSeries] = None
        bestMatchDistance = 999
        
        for tracker_entry in tracker_entries:
            for tracker_title in tracker_entry.titles:
                prepped_title = tracker_title.lower()
                rdistance = levenschtein(series_to_match, prepped_title)
                if rdistance < bestMatchDistance:
                    bestMatch = tracker_entry
                    bestMatchDistance = rdistance
                if rdistance < 10:
                    self.logger.info(
                        (f"possible match <{prepped_title}>"
                         f" - dist {rdistance} | id [{tracker_entry.tracker_id}]")
                    )

        if interactive:
            self.logger.info(f"Best match at distance {bestMatchDistance} | {bestMatch.tracker_id}")
            userValue = input("Enter Anilist ID: ")
            return self.FoundEntry(series, userValue)
        elif bestMatchDistance < 4:
            return self.FoundEntry(series, bestMatch.tracker_id)
        return None

    def updateFor(self, series, interactive=False) -> Optional[str]:
        self.logger.info("Updating for " + series)
        entries = self.anilist.getAllEntries()
        result = self.__findTrackerForSeries(entries.values(), series, interactive=interactive)

        # If not in our tracker, search for it. Add as planning to read.
        if result is None:
            entries = self.anilist.searchMediaBy(series)
            result = self.__findTrackerForSeries(entries.values(), series, interactive=interactive)
            if result is not None:
                self.logger.info(f"Adding '{series} ({result.tracker_entry})' to plan to read")
                self.anilist.addPlanToRead(result.tracker_entry)

        if result is not None:
            self.database.insertTracking(result.series_name, result.tracker_entry)
            return result.tracker_entry

    def manualUpdateFor(self, series, anilistId):
        self.database.insertTracking(series, anilistId)

    def updateAll(self):
        """Updates all series in DB that don't have tracker IDs"""
        entries = self.anilist.getAllEntries()

        rows = self.database.getAllSeriesWithoutTrackerIds()

        toadd = list()

        for row in rows:
            result = self.__findTrackerForSeries(entries, row["series"])
            if result is not None:
                toadd.append(result)

        for newtuple in toadd:
            self.database.insertTracking(seriesName=newtuple.series_name, anilistId=newtuple.tracker_entry)
