import pymanga


class MangaUpdatesGateway:
    def searchForSeries(self, name: str):
        return pymanga.api.search(name)["series"][0]["id"]

    def latestReleaseForId(self, id: int):
        return pymanga.api.releases(id)[0]['chapter']
