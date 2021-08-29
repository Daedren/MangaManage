
from manga.mangaContainer import MangaContainer
from manga.gateways.gatewayContainer import GatewayContainer
from mainRunner import MainRunner


class ApplicationContainer():
    def __init__(self, configuration) -> None:
        self.config = configuration
        self.gateways = GatewayContainer(self.config)
        self.manga = MangaContainer(self.config,
                                    self.gateways.database,
                                    self.gateways.tracker,
                                    self.gateways.filesystem,
                                    self.gateways.mangaUpdates)
        self.mainRunner = MainRunner(
            self.config["manga"]["sourcefolder"],
            self.config["manga"]["archivefolder"],
            self.gateways.database,
            self.gateways.filesystem,
            self.gateways.push,
            self.manga.checkGapsInChapters,
            self.manga.deleteReadChapters,
            self.manga.calculateChapterName,
            self.manga.updateTrackerIds,
            self.manga.createMetadata
        )
        pass
