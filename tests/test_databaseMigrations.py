import unittest
from manga.gateways.databaseMigrations import DatabaseMigrations
import sqlite3

class TestFilesystemGateway(unittest.TestCase):
    def setUp(self) -> None:
        self.fakeDb = sqlite3.connect(":memory:")
        self.sut = DatabaseMigrations()
        
    def test_version0to1_success(self):
        self.sut.LATEST_DB_VERSION = 1
        self.sut.doMigrations(self.fakeDb)
        
        cursor = self.fakeDb.cursor()
        cursor.execute("PRAGMA user_version;")
        version = cursor.fetchone()[0]
        self.assertEqual(version, 1)
