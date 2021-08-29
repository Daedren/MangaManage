from typing import Optional


class AnilistSeries:
    def __init__(self, anilistId: int, seriesName: str, mangaUpdatesId: Optional[int]):
        self.anilistId = anilistId
        self.seriesName = seriesName
        self.mangaUpdatesId = mangaUpdatesId
