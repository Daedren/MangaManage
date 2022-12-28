from pathlib import Path
import shutil
import io
import zipfile
import unittest
from manga.gateways.filesystem import FilesystemGateway


class TestFilesystemGateway(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree("/tmp/fstest/", ignore_errors=True)
        shutil.copytree("tests/resources/filesystemStub", "/tmp/fstest")
        self.sut = FilesystemGateway(
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
        # archive/seriesCbz - Empty by default. Test should fill it up
        # archive/series4 - ch1 in archive (ch2 is in quarantine)

        self.archiveSeries1 = Path("/tmp/fstest/archive/seriesOne")
        self.archiveSeries1Quarantine = Path("/tmp/fstest/quarantine/seriesOne")
        self.archiveSeries2 = Path("/tmp/fstest/archive/seriesTwo")
        self.archiveSeriesCbz = Path("/tmp/fstest/archive/seriesCbz")

        self.archiveSeries1Chapter1 = Path("/tmp/fstest/archive/seriesOne/1.cbz")
        self.archiveSeries2Chapter1 = Path("/tmp/fstest/archive/seriesTwo/1.cbz")
        self.archiveSeries2Chapter2 = Path("/tmp/fstest/archive/seriesTwo/2.cbz")
        self.archiveSeries4Chapter1 = Path("/tmp/fstest/archive/seriesFour/1.cbz")

        # source1/series1 - one chapter
        # source1/series2 - two chapters
        # source1/seriesCbz - one chapter in CBZ format
        # source2/series1 - one chapter

        self.source1Series1 = Path("/tmp/fstest/source/sourceOne/seriesOne")
        self.source1Series2 = Path("/tmp/fstest/source/sourceOne/seriesTwo")
        self.source1SeriesCbz = Path("/tmp/fstest/source/sourceOne/seriesCbz")
        self.source1Series4 = Path("/tmp/fstest/source/sourceOne/seriesFour")
        self.source2 = Path("/tmp/fstest/source/sourceTwo")
        self.source2Series1 = Path("/tmp/fstest/source/sourceTwo/seriesOne")

        self.source1Series1Chapter1 = Path(
            "/tmp/fstest/source/sourceOne/seriesOne/chapterOne"
        )
        self.source1SeriesCbzChapter1 = Path(
            "/tmp/fstest/source/sourceOne/seriesCbz/chapterOne.cbz"
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
        assert self.source1SeriesCbzChapter1.exists()

        return super().setUp()

    def tearDown(self) -> None:
        shutil.rmtree("/tmp/fstest/")
        return super().tearDown()

    def test_deleteSourceChapter_onechapter_deletesseries(self):
        """test_deleteSourceChapter_onechapter_deletesseries
        Deletes one chapter.
        Since the folder has no more chapters, it should be deleted
        """

        self.sut.deleteSourceChapter(self.source1Series1Chapter1)

        self.assertFalse(self.source1Series1Chapter1.exists())
        self.assertFalse(self.source1Series1.exists())
        self.assertTrue(self.source1Series2.exists())
        self.assertTrue(self.source2Series1Chapter1.exists())
        self.assertTrue(self.archiveSeries1Chapter1.exists())

        return

    def test_deleteSourceChapter_twochapters_deletechapter(self):
        """test_deleteSourceChapter_twochapters_deletechapter
        Deletes one chapter."""

        self.sut.deleteSourceChapter(self.source1Series2Chapter1)

        self.assertFalse(self.source1Series2Chapter1.exists())
        self.assertTrue(self.source1Series2Chapter2.exists())
        self.assertTrue(self.source1Series1Chapter1.exists())
        self.assertTrue(self.source2Series1Chapter1.exists())
        self.assertTrue(self.archiveSeries2Chapter1.exists())

        return

    def test_deleteSourceChapter_onechapter_deletesource(self):
        """test_deleteSourceChapter_onechapter_deletesource
        Deletes source if no more series inside."""

        self.sut.deleteSourceChapter(self.source2Series1Chapter1)

        self.assertFalse(self.source2.exists())
        return

    def test_deleteArchive_onechapterSeries_seriesDeleted(self):
        """test_deleteArchive_onechapterSeries_seriesDeleted"""
        self.sut.deleteArchive(self.series1, "1")

        self.assertFalse(self.archiveSeries1Chapter1.exists())
        self.assertFalse(self.archiveSeries1.exists())
        self.assertTrue(self.archiveSeries2Chapter1.exists())
        self.assertTrue(self.source1Series1Chapter1.exists())

    def test_quarantine_normal_move(self):
        """test_quarantine_normal_move"""
        self.sut.quarantineSeries(self.series1)
        self.assertTrue(self.archiveSeries1Quarantine.exists())
        self.assertFalse(self.archiveSeries1.exists())
        self.assertTrue(self.archiveSeries1Quarantine.joinpath("1.cbz").exists())

    def test_quarantine_mixed_merge(self):
        """test_quarantine_mixed_merge
        In case the series was already quarantined
        don't delete existing qt chapters when doing it for other chapters"""
        self.sut.quarantineSeries(self.series4)
        self.assertTrue(self.archiveSeries4QuarantineChapter2.exists())
        self.assertTrue(self.archiveSeries4QuarantineChapter1.exists())
        self.assertFalse(self.archiveSeries4Chapter1.exists())

    def test_movesourcecbztoarchive_success(self):
        """test_movesourcecbztoarchive_success"""
        archiveCbzChapter = self.archiveSeriesCbz.joinpath(self.source1SeriesCbzChapter1.name)
        self.sut.move_source_cbz_to_archive(archiveCbzChapter, self.source1SeriesCbzChapter1)
        self.assertTrue(self.archiveSeriesCbz.exists())
        self.assertEqual(self.source1SeriesCbzChapter1.name, str(next(self.archiveSeriesCbz.iterdir()).name))
    
    def test_putcomicinfoincbz_success(self):
        """test_putcomicinfoincbz_success"""
        # Uh, is our chapter iterator finding these?
        comicinfo = Path("tests/resources/createMetadata_1.xml")
        cbz = self.source1SeriesCbzChapter1
        self.sut.put_comicinfo_in_cbz(comicinfo, cbz)
        with zipfile.ZipFile(cbz) as zf:
            files = zf.namelist()
        print(files)
        self.assertTrue('ComicInfo.xml' in files)
        self.assertTrue(len(files) > 1)
