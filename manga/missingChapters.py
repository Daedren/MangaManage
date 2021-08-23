from typing import Optional, List
import datetime
from manga.gateways.anilist import AnilistGateway
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from cross.decorators import Logger
import os


@Logger
class CheckGapsInChapters:
    '''Checks if we are missing chapters to read (e.g. Anilist last read is Ch.30, but we only have starting from Ch.34)
       Chapters with gaps are quarantined until the gap is filled. This allows you to read the archive with confidence.
    '''
    dir_path = os.path.dirname(os.path.realpath(__file__))
    parent = os.path.dirname(dir_path)

    def __init__(self, database: DatabaseGateway, filesystem: FilesystemInterface,
                 anilist: AnilistGateway) -> None:
        self.database = database
        self.anilist = anilist
        self.filesystem = filesystem
        pass

    def getGapsFromChaptersSince(self, date: datetime):
        dbresult = self.database.getAllChapters()
        trackerData = self.anilist.getAllEntries()
        trackerMapData = dict((v["media"]["id"], v) for v in trackerData)
        dbMapData = dict()
        for i in dbresult:
            if not i[1] in dbMapData:
                dbMapData[i[1]] = [i]
            else:
                dbMapData[i[1]].append(i)

        newQuarantineList = list()
        newQuarantineAnilist = list()

        for row in dbMapData.items():
            rowAnilistId = row[0]
            rowData = row[1]
            realProgress = trackerMapData[rowAnilistId]["progress"]
            if realProgress is None:
                self.logger.debug("no progress in Anilist for %s \n" % row[0])
                return

            titles = trackerMapData[rowAnilistId]["media"]["title"]

            allChapters = list(map(lambda x: float(x[0]), rowData))
            if self.__gapExistsInTrackerProgress(realProgress, allChapters):
                self.logger.debug(
                    '{} - Last read at {}, but only {} is in DB'.format(titles, realProgress, min(allChapters)))
                newQuarantineAnilist.append(rowAnilistId)
                newQuarantineList.append(row)
                continue
                
            noGapsInChapters = self.__checkConsecutive(allChapters, titlesForLogging=titles)
            if not noGapsInChapters:
                newQuarantineAnilist.append(rowAnilistId)
                newQuarantineList.append(row)

        self.__checkQuarantines(newQuarantineAnilist)
        toQuarantine = self.__getOnlyNewQuarantines(self.filesystem.getQuarantinedSeries(), newQuarantineAnilist)
        for anilistId in toQuarantine:
            self.logger.debug(f"Adding {anilistId} to quarantine")
            self.filesystem.quarantineSeries(anilistId=anilistId)

        #limitedByDate = filter(lambda x: x[3] > datetime, newQuarantineList)
        return newQuarantineAnilist
        
    def __checkQuarantines(self, newQuarantineList: list):
        '''If a series isn't listed in the updated quarantine list. Remove it '''
        quarantinedSeries = self.filesystem.getQuarantinedSeries()
        noLongerQuarantined = self.__getNoLongerQuarantined(quarantinedSeries, newQuarantineList)
        for anilistId in noLongerQuarantined:
            self.logger.debug(f"Removing {anilistId} from quarantine")
            self.filesystem.restoreQuarantinedArchive(anilistId)
        return
        
    def __checkConsecutive(self, l: list, titlesForLogging: Optional[str] = None) -> bool:
        sortedChapters = sorted(l)
        lastChapter = None
        found_gap = False
        for chap in sortedChapters:
            if (lastChapter is not None) and (round(chap - lastChapter, 1) > 1.1):
                found_gap = True
                if titlesForLogging is not None:
                    self.logger.debug(f'{titlesForLogging} - Gap between {lastChapter} and {chap}')
            lastChapter = chap
        return not found_gap

    def __gapExistsInTrackerProgress(self, trackerProgress: int, chapters: list) -> bool:
        return round(trackerProgress - min(chapters), 1) < -1.1
    
    def __getNoLongerQuarantined(self, oldList: List[int], newList: List[int]) -> List[int]:
        return list(set(oldList) - set(newList))

    def __getOnlyNewQuarantines(self, alreadyQuarantined: List[int], newQuarantines: List[int]) -> List[int]:
        return list(set(newQuarantines) - set(alreadyQuarantined))