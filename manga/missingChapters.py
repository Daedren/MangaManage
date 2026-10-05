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
                self.logger.info(f"{rowAnilistId} not in tracker.")
                continue
            else:
                realProgress = trackerData.progress

            series_in_date: bool = (lastUpdatedMapData.get(rowAnilistId) is not None)
            if realProgress is None:
                self.logger.info("no progress in Anilist for %s \n" % row[0])
                return

            titles = trackerData.titles
            allChapters = list(map(lambda x: float(x["chapter"]), rowData))

            gaps = self.getGapsForChapters(rowAnilistId, titles[0], realProgress, allChapters)
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

    def getGapsForChapters(self, tracker_id, title, progress, chapters) -> List[MissingChapter]:
        """Read-only rules shared with the quarantine workflow (tracker gap takes priority)."""
        if not chapters:
            return []
        gap = self.checkTrackerGap(tracker_id, title, progress, chapters)
        return [gap] if gap else self.checkConsecutiveGaps(tracker_id, title, chapters)

    def getQuarantineDetails(self, tracker_id: int):
        """Check just one series without moving files or changing quarantine state."""
        chapters = self.database.getActiveChaptersForAnilist(tracker_id)
        if not chapters:
            return {"status": "no_active_chapters", "reasons": []}
        progress = self.anilist.getProgressFor(tracker_id)
        if progress is None:
            return {"status": "tracker_unavailable", "reasons": []}
        gaps = self.getGapsForChapters(
            tracker_id, chapters[0]["series"], progress,
            [float(chapter["chapter"]) for chapter in chapters],
        )
        reasons = []
        for gap in gaps:
            if isinstance(gap, MissingTrackerChapter):
                reasons.append({"type": "tracker_gap", "last_read": gap.tracker_chapter,
                                "first_stored": gap.stored_chapter})
            else:
                reasons.append({"type": "consecutive_gap", "before": gap.first_chapter,
                                "after": gap.second_chapter})
        return {"status": "gaps_found" if reasons else "no_gaps", "reasons": reasons}

    def __checkQuarantines(self, newQuarantineList: list):
        "If a series isn't listed in the updated quarantine list. Remove it"
        quarantinedSeries = self.filesystem.getQuarantinedSeries()
        noLongerQuarantined = self.__getNoLongerQuarantined(
            quarantinedSeries, newQuarantineList
        )
        for anilistId in noLongerQuarantined:
            self.filesystem.restoreQuarantinedArchive(anilistId)
        return

    def checkConsecutiveGaps(
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

    def checkTrackerGap(
        self, trackerId: int, title: str, trackerProgress: int, chapters: list
    ) -> Optional[MissingTrackerChapter]:
        """Checks if the lowest chapter we have
        is right after the last one in the tracker"""
        if not chapters:
            return None
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
