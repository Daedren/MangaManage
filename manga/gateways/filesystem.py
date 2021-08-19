import os
from pathlib import Path
import shutil
from enum import Enum
import re

class FilesystemGateway:
    def __init__(self, sourceFolder: str, archiveFolder: str) -> None:
        self.mangas = sourceFolder
        self.archiveRootPath = archiveFolder
        super().__init__()

    def deleteArchive(self, anilistId, chapterNumber):
        archiveSeriesPath = Path.joinpath(self.archiveRootPath, f"{anilistId}")
        if not archiveSeriesPath.exists():
                print("archive folder doesn't exist")
                print(archiveSeriesPath)
                return
        archiveChapterPath = Path.joinpath(archiveSeriesPath, f"{chapterNumber}.cbz")
        if archiveChapterPath.exists():
                archiveChapterPath.unlink()
        else:
                print("archive chapter doesn't exist")
                print(archiveChapterPath)
                return
    
        is_empty = not any(archiveSeriesPath.iterdir())
        if is_empty:
                archiveSeriesPath.rmdir()
    
    
    def deleteFolder(self, location: str):
        if not os.path.exists(location):
                print("source chapter doesn't exist")
                print(location)
                return
        shutil.rmtree(location)
        if (os.path.exists(location)) and (not os.listdir(location)):
                shutil.rmtree(location)
    