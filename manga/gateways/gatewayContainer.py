from .anilist import AnilistGateway
from .database import DatabaseGateway
from .pushover import PushoverGateway
from .mangaupd import MangaUpdatesGateway
from .filesystem import FilesystemGateway


class GatewayContainer:
    def __init__(self, configuration) -> None:
        self.config = configuration
        self.database = DatabaseGateway(self.config["database"]["sqlitelocation"])
        self.filesystem = FilesystemGateway(
            self.config["manga"]["sourcefolder"],
            self.config["manga"]["archivefolder"],
            self.config["manga"]["quarantinefolder"],
        )
        # self.filesystem = FilesystemFakeGateway()

        self.tracker = AnilistGateway(
            self.config["manga"]["anilisttoken"],
            self.config["manga"]["anilistuserid"],
        )
        
        self.mangaUpdates = MangaUpdatesGateway()
        # self.tracker = FakeAnilistGateway()

        self.push = PushoverGateway(
            tokenUser=self.config["push"]["pushoveruserkey"],
            tokenApp=self.config["push"]["pushoverappkey"],
        )
        pass
