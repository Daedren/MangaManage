from .anilist import AnilistGateway
from .database import DatabaseGateway
from .pushover import PushoverGateway
from .mangaupd import MangaUpdatesGateway
from .filesystem import FilesystemGateway
from .suwayomi import SuwayomiGateway


class GatewayContainer:
    def __init__(self, configuration) -> None:
        self.config = configuration
        self.database = DatabaseGateway(self.config["database"]["sqlitelocation"])
        self.filesystem = FilesystemGateway(
            self.config["manga"]["archivefolder"],
            self.config["manga"]["quarantinefolder"],
        )
        # self.filesystem = FilesystemFakeGateway()

        self.tracker = AnilistGateway(
            self.config["tracker"]["anilisttoken"],
            self.config["tracker"]["anilistuserid"],
            self.config["tracker"]["anilistclientid"],
        )

        self.mangaUpdates = MangaUpdatesGateway()
        self.suwayomi = SuwayomiGateway(
            base_url=self.config.get("suwayomi", "baseurl", fallback=""),
            web_url=self.config.get("suwayomi", "weburl", fallback=""),
            username=self.config.get("suwayomi", "username", fallback=""),
            password=self.config.get("suwayomi", "password", fallback=""),
            token=self.config.get("suwayomi", "token", fallback=""),
            migration_languages=self.config.get("suwayomi", "migration_languages", fallback="en"),
        )
        # self.tracker = FakeAnilistGateway()

        self.push = PushoverGateway(
            tokenUser=self.config["push"]["pushoveruserkey"],
            tokenApp=self.config["push"]["pushoverappkey"],
        )
        pass
