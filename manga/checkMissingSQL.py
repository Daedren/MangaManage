from pathlib import Path
from .gateways.database import DatabaseGateway
from cross.decorators import Logger
import zipfile
import uuid


@Logger
class CheckMissingChaptersInSQL:
    """Detects chapters in filesystem that aren't in SQL"""

    def __init__(
        self,
        database: DatabaseGateway,
        sourceFolder: str,
        archiveFolder: str,
    ) -> None:
        self.sourcesRootPath = Path(sourceFolder)
        self.archiveRootPath = Path(archiveFolder)
        self.database = database
        pass

    def execute(self, fixAfter=False):
        archiveChapterGlob = self.archiveRootPath.glob("*/*.cbz")
        self.logger.info("checking")
        for file in archiveChapterGlob:
            chapterNumber = file.stem
            anilistId = file.parent.name
            chapExistsInSQL = self.database.doesExistChapterAndAnilist(
                anilistId, chapterNumber
            )
            if not chapExistsInSQL:
                self.logger.info("File exist in disk, not in SQL")
                self.logger.info(file)
                if fixAfter:
                    self.__fixChapterTwo(file, chapterNumber, anilistId)
                self.logger.info("----")

    def __fixChapter(self, filePath, chapterNumber, anilistId):
        seriesName = self.database.getSeriesForAnilist(anilistId)
        # make series folder if needed
        sourceSeriesFolder = Path.joinpath(self.sourcesRootPath, seriesName)
        sourceChapterFolder = Path.joinpath(sourceSeriesFolder, chapterNumber)
        # make chapter folder
        Path.mkdir(sourceChapterFolder, parents=True, exist_ok=True)
        # unzip there
        with zipfile.ZipFile(filePath, "r") as zip_ref:
            zip_ref.extractall(sourceChapterFolder)

    def __fixChapterTwo(self, filePath, chapterNumber, anilistId):
        # Just insert into SQL
        # we have archivePath, chapterNumber, anilistId and now seriesName
        seriesName = self.database.getSeriesForAnilist(anilistId)
        self.logger.info(seriesName)
        sourceFake = str(uuid.uuid4())
        self.database.insertChapter(
            seriesName, str(chapterNumber), str(filePath), sourceFake
        )
