import datetime
from manga.gateways.anilist import AnilistGateway
from manga.gateways.database import DatabaseGateway
import os

class CheckGapsInChapters:
    '''Checks if we are missing chapters to read (e.g. Anilist last read is Ch.30, but we only have starting from Ch.34'''
    dir_path = os.path.dirname(os.path.realpath(__file__))
    parent = os.path.dirname(dir_path)

    def __init__(self, database: DatabaseGateway, anilist: AnilistGateway) -> None:
        self.database = database
        self.anilist = anilist
        pass


    # Since this checks Anilist individually for each series, it's important to use the date parameter to not get ratelimited
    #New
    def getGapsFromChaptersSince(self, date: datetime) -> str:
        dbresult = self.database.getLowestChapterForSeriesUpdatedSinceDate(date)
        toReturn = ''
        for row in dbresult:
            realProgress = self.anilist.getProgressFor(row[2])
            if realProgress is None:
                toReturn += "no progress in Anilist for %s \\n" % row[2]
                return
            if (float(realProgress)+1.0 < float(row[0])):
                toReturn += '{} - Last read at {}, but only {} is in DB \\n'.format(row[1], realProgress, row[0])
        return toReturn