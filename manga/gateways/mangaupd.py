import pymanga


class MangaUpdatesGateway:
    def searchForSeries(self, name: str):
        try:
            return pymanga.api.search(name)["series"][0]["id"]
        except IndexError:
            return None

    def latestReleaseForId(self, id: int):
        try:
            return pymanga.api.releases(id)[0]['chapter']
        except IndexError:
            return None
