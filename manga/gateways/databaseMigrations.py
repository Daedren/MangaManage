import sqlite3
from cross.decorators import Logger


@Logger
class DatabaseMigrations:
    def __init__(self):
        self.conversions = {
            0: self.__version0To1,
            1: self.__version1To2,
            2: self.__version2To3,
            3: self.__version3To4,
            4: self.__version4To5,
        }
        self.LATEST_DB_VERSION = max(self.conversions.keys()) + 1

    def doMigrations(self, conn: sqlite3.Connection):
        version = -1
        self.logger.info("Checking database migrations to run")
        while version < self.LATEST_DB_VERSION:
            cur = conn.cursor()
            cur.execute("PRAGMA user_version;")
            version = cur.fetchone()[0]
            self.__executeMigration(conn, version)

    def __executeMigration(self, conn, currentVersion):

        for version, func in self.conversions.items():
            if version == currentVersion:
                func(conn)

        if currentVersion > self.LATEST_DB_VERSION:
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

    def __version3To4(self, conn: sqlite3.Connection):
        self.logger.info("Executing migration version 3 -> 4")
        query = """
             ALTER TABLE manga ADD last_active timestamp;

             PRAGMA user_version = 4;
        """
        cur = conn.cursor()
        cur.executescript(query)

    def __version4To5(self, conn: sqlite3.Connection):
        self.logger.info("Executing migration version 4 -> 5")
        cur = conn.cursor()
        cur.execute("CREATE TABLE mangaupd(id integer primary key, mangaUpdatesId integer unique, anilistId integer unique, latestChapter integer null)")
        # Ids changed anyway, no point in copying them over
        # cur.execute("ALTER TABLE anilist DROP COLUMN mangaUpdatesId")
        cur.execute("CREATE TABLE anilist_temp(id integer primary key, series text unique, anilistId integer)")
        cur.execute("INSERT INTO anilist_temp SELECT id, series, anilistId FROM anilist")
        cur.execute("DROP TABLE anilist")
        cur.execute("ALTER TABLE anilist_temp RENAME TO anilist")
        cur.execute("PRAGMA user_version = 5")
        conn.commit()