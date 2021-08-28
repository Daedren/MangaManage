import sqlite3
from cross.decorators import Logger


@Logger
class DatabaseMigrations:
    def __init__(self):
        self.LATEST_DB_VERSION = 1

    def doMigrations(self, conn: sqlite3.Connection):
        version = -1
        self.logger.debug("Checking database migrations to run")
        while version < self.LATEST_DB_VERSION:
            cur = conn.cursor()
            cur.execute("PRAGMA user_version;")
            version = cur.fetchone()[0]
            self.__executeMigration(conn, version)

    def __executeMigration(self, conn, currentVersion):
        if currentVersion == 0:
            self.__version0To1(conn)
        elif currentVersion > self.LATEST_DB_VERSION:
            self.logger.error(
                "This version of the application is too old to run this database"
            )
            return

    def __version0To1(self, conn: sqlite3.Connection):
        self.logger.debug("Executing migration version 0 -> 1")
        query = """
            CREATE TABLE anilist(id integer primary key,
             series text unique, anilistId int);

            CREATE TABLE manga(id integer primary key,
             archive text unique,
             source text unique,
             chapter text,
             series text,
             creation_date datetime default CURRENT_TIMESTAMP);

             PRAGMA user_version = 1;
        """
        cur = conn.cursor()
        cur.executescript(query)
