import sqlite3
from cross.decorators import Logger


@Logger
class DatabaseMigrations:
    def __init__(self):
        self.LATEST_DB_VERSION = 3

    def doMigrations(self, conn: sqlite3.Connection):
        version = -1
        self.logger.info("Checking database migrations to run")
        while version < self.LATEST_DB_VERSION:
            cur = conn.cursor()
            cur.execute("PRAGMA user_version;")
            version = cur.fetchone()[0]
            self.__executeMigration(conn, version)

    def __executeMigration(self, conn, currentVersion):
        if currentVersion == 0:
            self.__version0To1(conn)
        elif currentVersion == 1:
            self.__version1To2(conn)
        elif currentVersion == 2:
            self.__version2To3(conn)
        elif currentVersion > self.LATEST_DB_VERSION:
            self.logger.error(
                "This version of the application is too old to run this database"
            )
            exit(1)
            return

    def __version0To1(self, conn: sqlite3.Connection):
        self.logger.info("Executing migration version 0 -> 1")
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

    def __version1To2(self, conn: sqlite3.Connection):
        self.logger.info("Executing migration version 1 -> 2")
        query = """
             ALTER TABLE anilist ADD mangaUpdatesId integer;

             PRAGMA user_version = 2;
        """
        cur = conn.cursor()
        cur.executescript(query)

    def __version2To3(self, conn: sqlite3.Connection):
        self.logger.info("Executing migration version 2 -> 3")
        query = """
             ALTER TABLE manga ADD active integer DEFAULT 1;

             PRAGMA user_version = 3;
        """
        cur = conn.cursor()
        cur.executescript(query)