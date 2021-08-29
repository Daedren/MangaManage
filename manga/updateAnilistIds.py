from manga.gateways.database import DatabaseGateway
from manga.gateways.anilist import AnilistGateway
from typing import Optional, Tuple
from .utils.pylev import levenschtein


class UpdateTrackerIds:
    """Updates local DB with tracker's IDs"""

    def __init__(self, database: DatabaseGateway, anilist: AnilistGateway) -> None:
        self.anilist = anilist
        self.database = database
        pass

    def __tryTuple(self, entry, series, force=False) -> Optional[Tuple[str, str]]:
        allDistancesText = ["", "", ""]
        edistance = 999
        sdistance = 999

        lowerRow = series.lower()
        lowerR = entry["media"]["title"]["romaji"].lower()
        rdistance = levenschtein(lowerRow, lowerR)
        allDistancesText[0] = lowerR

        if entry["media"]["title"]["english"] is not None:
            lowerE = entry["media"]["title"]["english"].lower()
            allDistancesText[1] = lowerE
            edistance = levenschtein(lowerRow, lowerE)

        if entry["media"]["synonyms"]:
            for synonym in entry["media"]["synonyms"]:
                lowerS = synonym.lower()
                temp = min(sdistance, levenschtein(lowerRow, lowerS))
                if temp < sdistance:
                    sdistance = temp
                    allDistancesText[2] = synonym

        allDistances = [rdistance, edistance, sdistance]

        if force:
            return (series, entry["media"]["id"])

        if min(allDistances) <= 4:
            rightName = allDistancesText[allDistances.index(min(allDistances))]
            print("found " + series + " - " + str(rightName))
            return (series, entry["media"]["id"])
        elif min(allDistances) < 10:
            print(
                "possible match ("
                + str(min(allDistances))
                + ") "
                + series
                + " - "
                + str(allDistancesText)
                + " "
                + str(entry["media"]["id"])
            )
            return None

    def updateFor(self, series) -> Optional[str]:
        print("Updating for " + series)
        entries = self.anilist.getAllEntries()
        for entry in entries:
            result = self.__tryTuple(entry, series)
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
