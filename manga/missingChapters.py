import datetime
from manga.gateways.anilist import AnilistGateway
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface
from cross.decorators import Logger
import os


@Logger
class CheckGapsInChapters:
    '''Checks if we are missing chapters to read (e.g. Anilist last read is Ch.30, but we only have starting from Ch.34
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
                self.logger.debug("no progress in Anilist for %s \n" % row[2])
                return

            allChapters = list(map(lambda x: float(x[0]), rowData))
            if self.__gapExistsInTrackerProgress(realProgress, allChapters):
                self.logger.debug(
                    '{} - Last read at {}, but only {} is in DB'.format(row[1], realProgress, row[0]))
                newQuarantineAnilist.append(rowAnilistId)
                newQuarantineList.append(row)
                
            noGapsInChapters = self.__checkConsecutive(allChapters)
            if not noGapsInChapters:
                self.logger.debug(f"in {rowAnilistId}")
                newQuarantineAnilist.append(rowAnilistId)
                newQuarantineList.append(row)

        self.__checkQuarantines(newQuarantineAnilist)
        for anilistId in newQuarantineAnilist:
            self.filesystem.quarantineSeries(anilistId=anilistId)

        #limitedByDate = filter(lambda x: x[3] > datetime, newQuarantineList)
        return newQuarantineAnilist
        
    def __checkQuarantines(self, newQuarantineList: list):
        '''If a series isn't listed in the updated quarantine list. Remove it '''
        quarantinedSeries = self.filesystem.getQuarantinedSeries()
        noLongerQuarantined = list(set(quarantinedSeries) - set(newQuarantineList))
        for anilistId in noLongerQuarantined:
            self.filesystem.restoreQuarantinedArchive(anilistId)
        return
        
    def __checkConsecutive(self, l: list) -> bool:
        sortedChapters = sorted(l)
        lastChapter = None
        for chap in sortedChapters:
            if lastChapter is None:
                lastChapter = chap
            elif (chap - lastChapter) > 1:
                self.logger.debug(f'Gap between {lastChapter} and {chap}')
                return False
            else:
                lastChapter = chap
        return True

    def __gapExistsInTrackerProgress(self, trackerProgress: int, chapters: list) -> bool:
        return (trackerProgress - min(chapters)) < 1