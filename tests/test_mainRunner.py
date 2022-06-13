import unittest
from unittest.mock import MagicMock
from pathlib import Path
import tempfile

from mainRunner import MainRunner
from models.manga import Chapter, MissingChapter

from manga.updateAnilistIds import UpdateTrackerIds
from manga.mangagetchapter import CalculateChapterName
from manga.deleteReadAnilist import DeleteReadChapters
from manga.missingChapters import CheckGapsInChapters
from manga.createMetadata import CreateMetadataInterface
from manga.gateways.pushover import PushServiceInterface
from manga.gateways.database import DatabaseGateway
from manga.gateways.filesystem import FilesystemInterface


class TestMainRunner(unittest.TestCase):
    def test_sendPush_multipleChapters(self):
        expectation = "2 new chapters downloaded\n" "\n" "name 12\n" "name 13"
        push = PushServiceInterface()
        push.sendPush = MagicMock()
        sut = self.createSut(push=push)

        chapters = [
            self.chapterStub(chapterNumber=12),
            self.chapterStub(chapterNumber=13),
        ]
        gaps = []
        sut.send_push(chapters, gaps)
        push.sendPush.assert_called_with(expectation)

    def test_sendPush_singleChapter(self):
        expectation = "1 new chapter downloaded\n" "\n" "name 12"
        push = PushServiceInterface()
        push.sendPush = MagicMock()
        sut = self.createSut(push=push)

        chapters = [self.chapterStub()]
        gaps = []
        sut.send_push(chapters, gaps)
        push.sendPush.assert_called_with(expectation)

    def test_sendPush_gaps_addedToMessage(self):
        expectation = (
            "1 new chapter downloaded\n"
            "\n"
            "name 12\n"
            "\n"
            "Updated in quarantine:\n"
            "missingSeries"
        )
        push = PushServiceInterface()
        push.sendPush = MagicMock()
        sut = self.createSut(push=push)

        chapters = [self.chapterStub()]
        gaps = [MissingChapter(1, "missingSeries", 12, 10)]
        sut.send_push(chapters, gaps)
        push.sendPush.assert_called_with(expectation)

    def test_prepareChapterCBZ_sourceIsCBZ_moveIt(self):
        filesystem = FilesystemInterface()
        filesystem.move_source_cbz_to_archive = MagicMock()
        filesystem.put_comicinfo_in_cbz = MagicMock()
        sut = self.createSut(filesystem=filesystem)

        with tempfile.NamedTemporaryFile() as fake_file:
            sut.prepareChapterCBZ(
                self.chapterStub(sourcePath=Path(fake_file.name)), metadata=Path("")
            )
        filesystem.move_source_cbz_to_archive.assert_called_once()

    def test_prepareChapterCBZ_sourceIsNotCBZ_createCBZ(self):
        filesystem = FilesystemInterface()
        filesystem.compress_chapter = MagicMock()
        filesystem.put_comicinfo_in_cbz = MagicMock()
        sut = self.createSut(filesystem=filesystem)

        sut.prepareChapterCBZ(
            self.chapterStub(sourcePath=Path(tempfile.gettempdir())), Path("")
        )
        filesystem.compress_chapter.assert_called_once()

    def chapterStub(
        self,
        anilistId: int = 1,
        seriesName: str = "name",
        chapterNumber: str = "12",
        chapterName: str = "chName",
        sourcePath: Path = Path(tempfile.gettempdir()),
        archivePath: Path = Path(""),
    ):
        return Chapter(
            anilistId, seriesName, chapterNumber, chapterName, sourcePath, archivePath
        )

    def createSut(
        self,
        sourceFolder: str = "",
        archiveFolder: str = "",
        database: DatabaseGateway = MagicMock(),
        filesystem: FilesystemInterface = MagicMock(),
        push: PushServiceInterface = MagicMock(),
        missingChapters: CheckGapsInChapters = MagicMock(),
        deleteReadChapters: DeleteReadChapters = MagicMock(),
        calcChapterName: CalculateChapterName = MagicMock(),
        updateTrackerIds: UpdateTrackerIds = MagicMock(),
        createMetadata: CreateMetadataInterface = MagicMock(),
    ) -> MainRunner:
        return MainRunner(
            sourceFolder,
            archiveFolder,
            database,
            filesystem,
            push,
            missingChapters,
            deleteReadChapters,
            calcChapterName,
            updateTrackerIds,
            createMetadata,
        )
