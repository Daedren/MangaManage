import unittest
from unittest.mock import MagicMock
from pathlib import Path
import tempfile

from mainRunner import MainRunner
from models.manga import Chapter, MissingTrackerChapter

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
            "missingSeries - Last read 12 but stored 32"
        )
        push = PushServiceInterface()
        push.sendPush = MagicMock()
        sut = self.createSut(push=push)

        chapters = [self.chapterStub()]
        gaps = [MissingTrackerChapter(1, "missingSeries", 32, 12)]
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

    def test_execute_discardsOnePageMangaDexChapter_andContinues(self):
        with tempfile.TemporaryDirectory() as source_folder:
            mangaDex_chapter = Path(source_folder, "Tachiyomi MangaDex", "series", "1")
            other_chapter = Path(source_folder, "Other source", "series", "2")
            mangaDex_chapter.mkdir(parents=True)
            other_chapter.mkdir(parents=True)

            filesystem = MagicMock()
            filesystem.count_source_images.side_effect = lambda path: (
                1 if path == mangaDex_chapter else 2
            )
            push = MagicMock()
            database = MagicMock()
            database.getAnilistIDForSeries.return_value = 1
            database.doesExistChapterAndAnilist.return_value = False
            calc_chapter_name = MagicMock()
            calc_chapter_name.execute.return_value = "2"
            delete_read_chapters = MagicMock()
            delete_read_chapters.execute.return_value = []
            sut = self.createSut(
                sourceFolder=source_folder,
                filesystem=filesystem,
                push=push,
                database=database,
                calcChapterName=calc_chapter_name,
                deleteReadChapters=delete_read_chapters,
            )

            sut.execute()

        filesystem.deleteSourceChapter.assert_any_call(location=str(mangaDex_chapter))
        push.sendPush.assert_any_call(
            "Discarded one-page MangaDex chapter: series 1"
        )
        filesystem.compress_chapter.assert_called_once()
        database.insertChapter.assert_called_once()

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
