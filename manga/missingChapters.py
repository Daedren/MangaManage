from typing import Optional, List
import datetime
from manga.gateways.anilist import AnilistGateway
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from models.manga import MissingChapter, MissingConsecutiveChapter, MissingTrackerChapter
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

    def getGapsFromChaptersSince(self, date: datetime) -> List[MissingChapter]:
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
        allQuarantineAnilist = list()

        for row in dbMapData.items():
            rowAnilistId = row[0]
            rowData = row[1]
            trackerData = trackerMapData.get(rowAnilistId)
            if trackerData is None:
                self.logger.error(f"{rowAnilistId} not in tracker.")
                return
            else:
                realProgress = trackerData.progress

            series_in_date: bool = (lastUpdatedMapData.get(rowAnilistId) is not None)
            if realProgress is None:
                self.logger.info("no progress in Anilist for %s \n" % row[0])
                return

            titles = trackerData.titles
            allChapters = list(map(lambda x: float(x["chapter"]), rowData))

            """Check for gap in chapters vs the tracker"""
            gap = self.__gapExistsInTrackerProgress(rowAnilistId, titles[0], realProgress, allChapters)
            if gap:
                if series_in_date:
                    newQuarantineList.append(gap)
                allQuarantineAnilist.append(rowAnilistId)
                continue

            """Check for gap in consecutive chapters"""
            gaps = self.__checkConsecutive(
                rowAnilistId, titles[0], allChapters
            )
            if gaps:
                allQuarantineAnilist.append(rowAnilistId)
                if series_in_date:
                    newQuarantineList.extend(gaps)
        
        for chapter in newQuarantineList:
            self.logger.info(chapter.reasonToPrint())

        self.__checkQuarantines(allQuarantineAnilist)

        for anilistId in allQuarantineAnilist:
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
        self, tracker_id: int, title: str, listToCheck: list,
    ) -> List[MissingConsecutiveChapter]:
        to_return = list()
        sortedChapters = sorted(listToCheck)
        lastChapter = None
        for chap in sortedChapters:
            if (lastChapter is not None) and (round(chap - lastChapter, 1) > 1.1):
                to_return.append(
                    MissingConsecutiveChapter(
                        tracker_id, title, lastChapter, chap
                    )
                )
            lastChapter = chap
        return to_return

    def __gapExistsInTrackerProgress(
        self, trackerId: int, title: str, trackerProgress: int, chapters: list
    ) -> Optional[MissingTrackerChapter]:
        """Checks if the lowest chapter we have
        is right after the last one in the tracker"""
        gapExists = round(trackerProgress - min(chapters), 1) < -1.1
        if gapExists:
            return MissingTrackerChapter(trackerId, title, min(chapters), trackerProgress)
        else:
            return None

    def __getNoLongerQuarantined(
        self, oldList: List[int], newList: List[int]
    ) -> List[int]:
        return list(set(oldList) - set(newList))

    def __getOnlyNewQuarantines(
        self, alreadyQuarantined: List[int], newQuarantines: List[int]
    ) -> List[int]:
        return list(set(newQuarantines) - set(alreadyQuarantined))
