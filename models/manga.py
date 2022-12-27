from pathlib import Path


class SimpleChapter:
    def __init__(
        self,
        anilistId: int,
        chapterNumber: str,
    ):
        self.anilistId = anilistId
        self.chapterNumber = chapterNumber

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, SimpleChapter):
            return (
                self.anilistId == other.anilistId
                and self.chapterNumber == other.chapterNumber
            )
        return False

    def __hash__(self):
        return hash(self.anilistId) + hash(self.chapterNumber)


class Chapter(SimpleChapter):
    def __init__(
        self,
        anilistId: int,
        seriesName: str,
        chapterNumber: str,
        chapterName: str,
        sourcePath: Path,
        archivePath: Path
    ):
        self.anilistId = anilistId
        self.seriesName = seriesName
        self.chapterNumber = chapterNumber
        self.chapterName = chapterName
        self.sourcePath = sourcePath
        self.archivePath = archivePath

class MissingChapter:
    def __init__(
        self,
        tracker_id: str,
        series_name: str,
    ) -> None:
        self.tracker_id = tracker_id
        self.series_name = series_name
    
    def reasonToPrint(self):
        return f'{self.series_name} - Unknown reason'

class MissingTrackerChapter(MissingChapter):
    def __init__(
        self,
        tracker_id: str,
        series_name: str,
        stored_chapter: str,
        tracker_chapter: str,
    ) -> None:
        self.tracker_id = tracker_id
        self.series_name = series_name
        self.stored_chapter = stored_chapter
        self.tracker_chapter = tracker_chapter
    
    def reasonToPrint(self):
        return f"{self.series_name} - Last read {self.tracker_chapter} but stored {self.stored_chapter}"

class MissingConsecutiveChapter(MissingChapter):
    def __init__(
        self,
        tracker_id: str,
        series_name: str,
        first_chapter: str,
        second_chapter: str,
    ) -> None:
        self.tracker_id = tracker_id
        self.series_name = series_name
        self.first_chapter = first_chapter
        self.second_chapter = second_chapter
    
    def reasonToPrint(self):
        return f"{self.series_name} - Gap between {self.first_chapter} and {self.second_chapter}"