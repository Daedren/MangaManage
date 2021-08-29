import unittest
from manga.gateways.databaseMigrations import DatabaseMigrations
import sqlite3


class TestFilesystemGateway(unittest.TestCase):
    def setUp(self) -> None:
        self.fakeDb = sqlite3.connect(":memory:")
        self.sut = DatabaseMigrations()

    def test_allMigrations_success(self):
        self.sut.doMigrations(self.fakeDb)

        cursor = self.fakeDb.cursor()
        cursor.execute("PRAGMA user_version;")
        version = cursor.fetchone()[0]
        self.assertEqual(version, self.sut.LATEST_DB_VERSION)
