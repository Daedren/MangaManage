from typing import Optional, List
import datetime
from manga.gateways.anilist import AnilistGateway
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from models.manga import MissingChapter
from cross.decorators import Logger
import os


@Logger
class CheckGapsInChapters:
    """Checks if we are missing chapters to read
    (e.g. Anilist last read is Ch.30, but we only have starting from Ch.34)
    Chapters with gaps are quarantined until the gap is filled.
    This allows you to read the archive with confidence.
    """

    dir_path = os.path.dirname(os.path.realpath(__file__))
    parent = os.path.dirname(dir_path)

    def __init__(
        self,
        database: DatabaseGateway,
        filesystem: FilesystemInterface,
        anilist: AnilistGateway,
    ) -> None:
        self.database = database
        self.anilist = anilist
        self.filesystem = filesystem
        pass

    def getGapsFromChaptersSince(self, date: datetime):
        dbresult = self.database.getAllChapters()
        # dbresult = self.database.getAllChaptersOfSeriesUpdatedAfter(date)
        lastUpdatedSeries = self.database.getSeriesLastUpdatedSince(date)
        trackerMapData = self.anilist.getAllEntries()

        lastUpdatedMapData = dict((v["anilistId"], v) for v in lastUpdatedSeries)
        dbMapData = dict()
        for i in dbresult:
            if not i["anilistId"] in dbMapData:
                dbMapData[i["anilistId"]] = [i]
            else:
                dbMapData[i["anilistId"]].append(i)

        newQuarantineList = list()
        newQuarantineAnilist = list()

        for row in dbMapData.items():
            rowAnilistId = row[0]
            rowData = row[1]
            trackerData = trackerMapData.get(rowAnilistId)
            if trackerData is None:
                self.logger.error(f"{rowAnilistId} not in tracker")
                return
            else:
                realProgress = trackerData.progress

            shouldLog: bool = (lastUpdatedMapData.get(rowAnilistId) is not None)
            if realProgress is None:
                self.logger.info("no progress in Anilist for %s \n" % row[0])
                return

            titles = trackerData.titles
            allChapters = list(map(lambda x: float(x["chapter"]), rowData))
            current_series = MissingChapter(
                rowAnilistId, titles[0], min(allChapters), realProgress)

            if self.__gapExistsInTrackerProgress(realProgress, allChapters):
                if shouldLog:
                    self.logger.info(
                        "{} - Last read at {}, but only {} is in DB".format(
                            titles, realProgress, min(allChapters)
                        )
                    )
                newQuarantineAnilist.append(rowAnilistId)
                newQuarantineList.append(current_series)
                continue

            noGapsInChapters = self.__checkConsecutive(
                allChapters, titlesForLogging=titles, shouldLog=shouldLog
            )
            if not noGapsInChapters:
                newQuarantineAnilist.append(rowAnilistId)
                newQuarantineList.append(current_series)

        self.__checkQuarantines(newQuarantineAnilist)

        for anilistId in newQuarantineAnilist:
            self.filesystem.quarantineSeries(anilistId=anilistId)

        # limitedByDate = filter(lambda x: x[3] > datetime, newQuarantineList)
        return newQuarantineList

    def __checkQuarantines(self, newQuarantineList: list):
        "If a series isn't listed in the updated quarantine list. Remove it"
        quarantinedSeries = self.filesystem.getQuarantinedSeries()
        noLongerQuarantined = self.__getNoLongerQuarantined(
            quarantinedSeries, newQuarantineList
        )
        for anilistId in noLongerQuarantined:
            self.filesystem.restoreQuarantinedArchive(anilistId)
        return

    def __checkConsecutive(
        self, listToCheck: list, titlesForLogging: Optional[str] = None, shouldLog=True
    ) -> bool:
        sortedChapters = sorted(listToCheck)
        lastChapter = None
        found_gap = False
        for chap in sortedChapters:
            if (lastChapter is not None) and (round(chap - lastChapter, 1) > 1.1):
                found_gap = True
                if titlesForLogging is not None and shouldLog:
                    self.logger.info(
                        f"{titlesForLogging} - Gap between {lastChapter} and {chap}"
                    )
            lastChapter = chap
        return not found_gap

    def __gapExistsInTrackerProgress(
        self, trackerProgress: int, chapters: list
    ) -> bool:
        "Checks if the lowest chapter we have is right after the last one in the tracker"
        return round(trackerProgress - min(chapters), 1) < -1.1

    def __getNoLongerQuarantined(
        self, oldList: List[int], newList: List[int]
    ) -> List[int]:
        return list(set(oldList) - set(newList))

    def __getOnlyNewQuarantines(
        self, alreadyQuarantined: List[int], newQuarantines: List[int]
    ) -> List[int]:
        return list(set(newQuarantines) - set(alreadyQuarantined))
