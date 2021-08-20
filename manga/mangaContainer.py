from manga.gateways.filesystem import FilesystemInterface
from manga.gateways.anilist import AnilistGateway
from manga.gateways.database import DatabaseGateway
from manga.mangagetchapter import CalculateChapterName
from manga.updateAnilistIds import UpdateTrackerIds
from manga.missingChapters import CheckGapsInChapters
from manga.deleteReadAnilist import DeleteReadChapters
from manga.checkMissingSQL import CheckMissingChaptersInSQL
from manga.gateways.gatewayContainer import GatewayContainer


class MangaContainer:

    def __init__(self,
                config,
                 database: DatabaseGateway,
                 tracker: AnilistGateway,
                 filesystem: FilesystemInterface) -> None:
        self.config = config
        self.database = database
        self.tracker = tracker
        self.filesystem = filesystem

        self.checkMissingSQL = CheckMissingChaptersInSQL(self.database,
                                                         self.config["manga"]["sourcefolder"],
                                                         self.config["manga"]["archivefolder"]
                                                         )

        self.updateTrackerIds = UpdateTrackerIds(
            self.database,
            self.tracker
        )

        self.calculateChapterName = CalculateChapterName(self.tracker)

        self.deleteReadChapters = DeleteReadChapters(self.tracker,
                                                     self.filesystem,
                                                     self.database
                                                     )

        self.checkGapsInChapters = CheckGapsInChapters(self.database,
                                                       self.tracker)
        pass
