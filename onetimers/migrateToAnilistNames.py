import sqlite3
import os
from pathlib import Path
from anilist.database import getAnilistIDForSeries

archivePath = "/mdata/archive"
newArchivePath = "/mdata/newarchive"

conn = sqlite3.connect('./manga.db')

if __name__ == "__main__":
    archiveFolder = Path(archivePath)
    archiveGlob = Path(archivePath).glob('*')
    for file in archiveGlob:
        folderName = Path(file).name
        print(folderName)
        anilistId = getAnilistIDForSeries(folderName)
        if anilistId:
            print(anilistId)
            newName = Path.joinpath(Path(newArchivePath), f"{anilistId}")
            os.rename(file, newName)
