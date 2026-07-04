import sqlite3
import os
import logging
from pathlib import Path
from anilist.database import getAnilistIDForSeries


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

archivePath = "/mdata/archive"
newArchivePath = "/mdata/newarchive"

conn = sqlite3.connect('./manga.db')

if __name__ == "__main__":
    archiveFolder = Path(archivePath)
    archiveGlob = Path(archivePath).glob('*')
    for file in archiveGlob:
        folderName = Path(file).name
        logger.info(folderName)
        anilistId = getAnilistIDForSeries(folderName)
        if anilistId:
            logger.info(anilistId)
            newName = Path.joinpath(Path(newArchivePath), f"{anilistId}")
            os.rename(file, newName)
