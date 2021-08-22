from pathlib import Path
import shutil
import unittest
from unittest.mock import MagicMock
from manga.gateways.filesystem import FilesystemGateway

class TestFilesystemGateway(unittest.TestCase):
    def setUp(self) -> None:
        '''Creates two series with one chapter each for basic tests'''
        self.sut = FilesystemGateway(sourceFolder='', archiveFolder='', quarantineFolder='')
        self.series1 = "/tmp/fstest/seriesone"
        self.series1Path = Path(self.series1)
        self.series1chapter1 = "/tmp/fstest/seriesone/chapterone"
        self.series1chapter1Path = Path(self.series1chapter1)
        self.series1chapter1Path.mkdir(parents=True, exist_ok=False)
        tmpFile = self.series1chapter1Path.joinpath('l1.txt')
        open(tmpFile.resolve(), 'w').close()

        self.series2 = "/tmp/fstest/seriestwo"
        self.series2Path = Path(self.series2)
        self.series2chapter1 = "/tmp/fstest/seriestwo/chapterone"
        self.series2chapter1Path = Path(self.series2chapter1)
        self.series2chapter1Path.mkdir(parents=True, exist_ok=False)
        tmpFile = self.series2chapter1Path.joinpath('l1.txt')
        open(tmpFile.resolve(), 'w').close()

        return super().setUp()

    def tearDown(self) -> None:
        shutil.rmtree('/tmp/fstest/')
        return super().tearDown()
    
    def test_deleteFolder_onechapter_deletesseries(self):
        '''Deletes one chapter. Since the folder has no more chapters, it should be deleted'''

        self.sut.deleteFolder(self.series1chapter1Path)

        assert not self.series1chapter1Path.exists()
        assert not self.series1Path.exists()
        assert self.series2Path.exists()

        return

    def test_deleteFolder_twochapters_deletechapter(self):
        '''Deletes one chapter. '''

        series1chapter2 = "/tmp/fstest/seriesone/chaptertwo"
        series1chapter2Path = Path(series1chapter2)
        series1chapter2Path.mkdir(parents=True, exist_ok=False)
        tmpFile = series1chapter2Path.joinpath('l1.txt')
        open(tmpFile.resolve(), 'w').close()

        assert tmpFile.exists()

        self.sut.deleteFolder(self.series1chapter1Path)

        assert not self.series1chapter1Path.exists()
        assert self.series1Path.exists()
        assert self.series2Path.exists()
        assert series1chapter2Path.exists()

        return
    
    def test_deleteArchive_normal_delete(self):
        chapter = '54'
        anilistId = 98563
        self.sut.deleteArchive(anilistId, chapter)