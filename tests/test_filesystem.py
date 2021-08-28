from pathlib import Path
import shutil
import unittest
from manga.gateways.filesystem import FilesystemGateway


class TestFilesystemGateway(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree("/tmp/fstest/", ignore_errors=True)
        shutil.copytree("tests/resources/filesystemStub", "/tmp/fstest")
        self.sut = FilesystemGateway(
            sourceFolder="/tmp/fstest/source",
            archiveFolder="/tmp/fstest/archive",
            quarantineFolder="/tmp/fstest/quarantine",
        )

        self.series1 = "seriesOne"
        self.series4 = "seriesFour"

        # quarantine/series3 - one chapter
        # quarantine/series4 - ch2 in quarantine
        self.archiveSeries3Quarantine = Path("/tmp/fstest/quarantine/seriesThree")
        self.archiveSeries4Quarantine = Path("/tmp/fstest/quarantine/seriesFour")
        self.archiveSeries4QuarantineChapter2 = Path(
            "/tmp/fstest/quarantine/seriesFour/2.cbz"
        )
        self.archiveSeries4QuarantineChapter1 = Path(
            "/tmp/fstest/quarantine/seriesFour/1.cbz"
        )

        # archive/series1 - one chapter
        # archive/series2 - two chapters
        # archive/series4 - ch1 in archive (ch2 is in quarantine)

        self.archiveSeries1 = Path("/tmp/fstest/archive/seriesOne")
        self.archiveSeries1Quarantine = Path("/tmp/fstest/quarantine/seriesOne")
        self.archiveSeries2 = Path("/tmp/fstest/archive/seriesTwo")

        self.archiveSeries1Chapter1 = Path("/tmp/fstest/archive/seriesOne/1.cbz")
        self.archiveSeries2Chapter1 = Path("/tmp/fstest/archive/seriesTwo/1.cbz")
        self.archiveSeries2Chapter2 = Path("/tmp/fstest/archive/seriesTwo/2.cbz")
        self.archiveSeries4Chapter1 = Path("/tmp/fstest/archive/seriesFour/1.cbz")

        # source1/series1 - one chapter
        # source1/series2 - two chapters
        # source2/series1 - one chapter

        self.source1Series1 = Path("/tmp/fstest/source/sourceOne/seriesOne")
        self.source1Series2 = Path("/tmp/fstest/source/sourceOne/seriesTwo")
        self.source1Series4 = Path("/tmp/fstest/source/sourceOne/seriesFour")
        self.source2Series1 = Path("/tmp/fstest/source/sourceTwo/seriesOne")

        self.source1Series1Chapter1 = Path(
            "/tmp/fstest/source/sourceOne/seriesOne/chapterOne"
        )
        self.source1Series2Chapter1 = Path(
            "/tmp/fstest/source/sourceOne/seriesTwo/chapterOne"
        )
        self.source1Series2Chapter2 = Path(
            "/tmp/fstest/source/sourceOne/seriesTwo/chapterTwo"
        )
        self.source2Series1Chapter1 = Path(
            "/tmp/fstest/source/sourceTwo/seriesOne/chapterOne"
        )

        assert self.archiveSeries3Quarantine.exists()
        assert self.archiveSeries4QuarantineChapter2.exists()
        assert self.archiveSeries1.exists()
        assert self.archiveSeries2.exists()
        assert self.archiveSeries1Chapter1.exists()
        assert self.archiveSeries2Chapter1.exists()
        assert self.archiveSeries2Chapter2.exists()
        assert self.archiveSeries4Chapter1.exists()
        assert self.source1Series1.exists()
        assert self.source1Series2.exists()
        assert self.source2Series1.exists()
        assert self.source1Series1Chapter1.exists()
        assert self.source1Series2Chapter1.exists()
        assert self.source1Series2Chapter2.exists()
        assert self.source2Series1Chapter1.exists()

        return super().setUp()

    def tearDown(self) -> None:
        shutil.rmtree("/tmp/fstest/")
        return super().tearDown()

    def test_deleteFolder_onechapter_deletesseries(self):
        """Deletes one chapter.
        Since the folder has no more chapters, it should be deleted
        """

        self.sut.deleteFolder(self.source1Series1Chapter1)

        self.assertFalse(self.source1Series1Chapter1.exists())
        self.assertFalse(self.source1Series1.exists())
        self.assertTrue(self.source1Series2.exists())
        self.assertTrue(self.source2Series1Chapter1.exists())
        self.assertTrue(self.archiveSeries1Chapter1.exists())

        return

    def test_deleteFolder_twochapters_deletechapter(self):
        """Deletes one chapter."""

        self.sut.deleteFolder(self.source1Series2Chapter1)

        self.assertFalse(self.source1Series2Chapter1.exists())
        self.assertTrue(self.source1Series2Chapter2.exists())
        self.assertTrue(self.source1Series1Chapter1.exists())
        self.assertTrue(self.source2Series1Chapter1.exists())
        self.assertTrue(self.archiveSeries2Chapter1.exists())

        return

    def test_deleteArchive_onechapterSeries_seriesDeleted(self):
        self.sut.deleteArchive(self.series1, "1")

        self.assertFalse(self.archiveSeries1Chapter1.exists())
        self.assertFalse(self.archiveSeries1.exists())
        self.assertTrue(self.archiveSeries2Chapter1.exists())
        self.assertTrue(self.source1Series1Chapter1.exists())

    def test_quarantine_normal_move(self):
        self.sut.quarantineSeries(self.series1)
        self.assertTrue(self.archiveSeries1Quarantine.exists())
        self.assertFalse(self.archiveSeries1.exists())
        self.assertTrue(self.archiveSeries1Quarantine.joinpath("1.cbz").exists())

    def test_quarantine_mixed_merge(self):
        """In case the series was already quarantined
        don't delete existing qt chapters when doing it for other chapters"""
        self.sut.quarantineSeries(self.series4)
        self.assertTrue(self.archiveSeries4QuarantineChapter2.exists())
        self.assertTrue(self.archiveSeries4QuarantineChapter1.exists())
        self.assertFalse(self.archiveSeries4Chapter1.exists())
