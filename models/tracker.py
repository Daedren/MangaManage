from typing import Optional


class TrackerSeries:
    def __init__(
        self,
        tracker_id: int,
        titles: [str],
        status: str,
        # Chapters is null if an ongoing series
        chapters: Optional[int],
        country_of_origin: str,
        progress: int,
    ):
        self.tracker_id = tracker_id
        self.titles = titles
        self.status = status
        self.chapters = chapters
        self.country_of_origin = country_of_origin
        self.progress = progress
