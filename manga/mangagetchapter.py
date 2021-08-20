from manga.gateways.anilist import TrackerGatewayInterface
import os
from pathlib import Path
import re
import glob

exRegex = r'^\#?ex\ .*?([0-9]+)'
chRegex = r'Ch\.\ ?([0-9]+\.?[0-9]*)'
largeNumRegex = r'[0-9]+\.?[0-9]*'

class CalculateChapterName:
    def __init__(self, anilist: TrackerGatewayInterface) -> None:
        self.anilist = anilist
        pass

    def __formatNumber(self, num: float):
        if num % 1 == 0:
            return int(num)
        else:
            return num

    def _getNewestFileIn(self, folder):
        list_of_files = glob.glob(folder+'/*') # * means all if need specific format then *.csv
        latest_file = max(list_of_files, key=os.path.getctime)
        return Path(latest_file).stem

    def _getNewestChAnilistFor(self, anilistId):
        progress = self.anilist.getProgressFor(int(anilistId))
        return progress

    ''' Infers the chapter number from a chapter name'''
    def execute(self, chapterName,anilistId):
        matchObj = re.search(exRegex, chapterName)
        if matchObj:
            #return "ex"+matchObj.group(1)
            result = self._getNewestChAnilistFor(anilistId)
            if result:
                return str(result)+'.8'

        matchObj = re.search(chRegex, chapterName)
        if matchObj:
            return matchObj.group(1).lstrip('0') or "0"

        matchObj = re.findall(largeNumRegex, chapterName)
        if matchObj:
            intMatch = map(lambda x: float(x), matchObj)
            result = sorted(intMatch, reverse=True) 
            bestValue = result[0]
            roundedValue = self.__formatNumber(bestValue)
            return str(roundedValue)

        if anilistId:
            # - get closest filemod, add .8
            # - get latest read and add .8
            # - 1
            #print('find '+sourcePath+' \! -newer "'+chapterName+'" -printf "%T@ %p\n" | sort -rn | head -2 | tail -1')
            #cmd = subprocess.run('find '+sourcePath+' \! -newer "'+chapterName+'" -printf "%T@ %p\n" | sort -rn | head -2 | tail -1', shell=True, capture_output=True)
            #return cmd
            #getAnilist.execute()

            # O problema é que o deleteChapter vai apagar isto se for 1, ou abaixo do num. mais recente no anilist
            #result = getNewestFileIn(archivePath)
            result = self._getNewestChAnilistFor(anilistId)
            if result:
                return str(result)+'.8'

        return '1.8'