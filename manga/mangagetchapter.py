from typing import Optional
from decimal import Decimal
from manga.gateways.anilist import TrackerGatewayInterface
import os
from pathlib import Path
import re
import glob


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
        list_of_files = glob.glob(
            folder + "/*"
        )
        latest_file = max(list_of_files, key=os.path.getctime)
        return Path(latest_file).stem

    def _getNewestChAnilistFor(self, anilistId):
        progress = self.anilist.getProgressFor(int(anilistId))
        return progress

    def execute(self, chapterName, anilistId) -> str:
        """ Infers the chapter number from a chapter name
            (chapter, volume, volChapter)
        """

        detectedChapter: Optional[str] = None

        chapterFunctions = [
            self.__exNotation,
            self.__mangaUpdNotation,
            self.__defaultChapterNotation,
            self.__anyOtherNumberNotation,
        ]

        for func in chapterFunctions:
            detectedChapter = func(chapterName, anilistId)
            if detectedChapter is not None:
                break
            
        # Cleans up. Adds leading zero. Catches errors. etc.
        to_return = Decimal(detectedChapter)
        return str(to_return)

    def __exNotation(self, chapterName: str, anilistId: int) -> Optional[str]:
        exRegex = r"^(\w*_|\#)?ex\ -\ .*?([0-9]+)?"
        matchObj = re.search(exRegex, chapterName)
        if matchObj:
            result = self._getNewestChAnilistFor(anilistId)
            if result:
                return str(result) + ".8"
        return None

    def __defaultChapterNotation(self,
                                 chapterName: str,
                                 anilistId: int) -> Optional[str]:
        chRegex = r"Ch\.\ ?([0-9]+\.?[0-9]*)"
        matchObj = re.search(chRegex, chapterName)
        if matchObj:
            return matchObj.group(1).lstrip("0") or "0"
        return None

    def __anyOtherNumberNotation(self,
                                 chapterName: str,
                                 anilistId: int) -> Optional[str]:
        largeNumRegex = r"[0-9]+\.?[0-9]*"
        matchObj = re.findall(largeNumRegex, chapterName)
        if matchObj:
            intMatch = map(lambda x: float(x), matchObj)
            result = sorted(intMatch, reverse=True)
            bestValue = result[0]
            roundedValue = self.__formatNumber(bestValue)
            return str(roundedValue)
        return None

    def __mangaUpdNotation(self,
                                 chapterName: str,
                                 anilistId: int) -> Optional[str]:
        regex = r"c\.([0-9]+\.?[0-9]*)\-?([0-9]+\.?[0-9]*)?"
        matchObj = re.search(regex, chapterName)
        if matchObj:
            non_none_groups = list(filter(lambda x: x is not None, matchObj.groups()))
            return non_none_groups[-1]
        return None

    def __latestAnilistNumber(self, chapterName: str, anilistId: int) -> Optional[str]:
        if anilistId:
            result = self._getNewestChAnilistFor(anilistId)
            if result:
                return str(result) + ".8"
        return None
