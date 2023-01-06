import pymanga
import urllib.request
from typing import List
from lxml import etree
from bs4 import BeautifulSoup
from cross.decorators import Logger
import re


@Logger
class MangaUpdatesGateway:
    def searchForSeries(self, names: List[str]):
        try:
            name = self.__getMostSearchableTitle(names)
            series = pymanga.api.search(name)["series"]
            self.logger.debug(f'Fetching data for {name}')
            no_novels_series = list(
                filter(lambda x: ('(Novel)' not in x['name']) and not (x['id'].endswith('-novel')), series))
            found_series = no_novels_series[0]
            self.logger.debug(f"Found {found_series['name']}")
            return found_series["id"]
        except IndexError:
            return None

    def getSeriesId(self, url: str):
        result = urllib.request.urlopen(url)

        soup = BeautifulSoup(result.read(), 'html.parser')
        links = soup.find_all('a')
        apis = filter(lambda x: x['href'].startswith(
            'https://api.mangaupdates.com/'), links)
        return next(apis)['href'].split('/')[-2]

    def latestReleasesForId(self, id: int):
        url = self.__getRSS(id)
        chapters = self.__getLatestChaptersFromRSS(url)
        return chapters

    def __getRSS(self, id: int):
        rss = f"https://api.mangaupdates.com/v1/series/{id}/rss"
        self.logger.debug(rss)
        return rss

    def __getLatestChaptersFromRSS(self, url):
        feed = urllib.request.urlopen(url)
        feed = etree.parse(feed)
        root = feed.getroot()
        try:
            self.logger.debug(root.find('channel').find('title').text)
            chapters = list(map(lambda x: x.getchildren()[0].text, root.findall(".//item")))
            # Lots of stuff we don't care about in there.
            valid_chapters = list(filter(lambda x: re.search("c\.([0-9]+\.?[0-9]*)\-?([0-9]+\.?[0-9]*)?", x), chapters))
            return valid_chapters
        except StopIteration:
            print(f"No chapters found")
            return None

    def __getMostSearchableTitle(self, titles: List[str]):
        return max(titles, key=lambda s: sum(c.isascii() for c in s))
