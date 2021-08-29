import sqlite3
from typing import List
from .utils.databaseModels import AnilistSeries
from .databaseMigrations import DatabaseMigrations


class DatabaseGateway:
    def __init__(self, databaseLocation: str) -> None:
        self.conn = sqlite3.connect(databaseLocation)
        self.migrations = DatabaseMigrations()
        self.migrations.doMigrations(self.conn)
        self.conn.row_factory = sqlite3.Row
        super().__init__()

    def __getCursor(self):
        cur = self.conn.cursor()
        return cur

    def __dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def getAllChapters(self):
        cur = self.__getCursor()
        query = """
        SELECT chapter, anilistId, creation_date
        FROM manga
        INNER JOIN anilist
        ON manga.series = anilist.series
        """
        cur.execute(query)
        rows = cur.fetchall()
        return rows

    def getSeriesForAnilist(self, anilistId):
        cur = self.__getCursor()

        # Remember that anilist only stores integers for chapter numbers!
        query = """
        SELECT series
        FROM anilist
        WHERE anilistId = ?
        """
        cur.execute(query, (anilistId,))
        row = cur.fetchone()
        if isinstance(row, tuple):
            return row["series"]
        else:
            return row

    def getMangaUpdForTracker(self, trackerId):
        cur = self.__getCursor()

        query = """
        SELECT mangaUpdatesId
        FROM anilist
        WHERE anilistId = ?
        """
        cur.execute(query, (trackerId,))
        row = cur.fetchone()
        if isinstance(row, tuple):
            return row["mangaUpdatesId"]
        else:
            return row

    def doesExistChapterAndAnilist(self, anilistId, chapterNumber):
        cur = self.__getCursor()

        # Remember that anilist only stores integers for chapter numbers!
        query = """
        SELECT a.series
        FROM manga a
        INNER JOIN anilist b
        ON a.series = b.series
        WHERE chapter = ? AND anilistId = ?
        """
        cur.execute(query, (chapterNumber, anilistId))
        row = cur.fetchone()
        return row

    def deleteChapter(self, anilistId, chapterNumber):
        cur = self.__getCursor()

        # Remember that anilist only stores integers for chapter numbers!
        query = """
        DELETE FROM manga
        WHERE chapter = ?
        AND series IN ( SELECT series FROM anilist WHERE anilistId = ?)
        """
        cur.execute(query, (chapterNumber, anilistId))
        self.conn.commit()

    def insertChapter(self, seriesName, chapterNumber: str, archivePath, sourcePath):
        cur = self.__getCursor()

        query = """
        INSERT INTO manga(series, chapter, archive, source)
        VALUES(?,?,?,?)
        """
        cur.execute(query, (seriesName, chapterNumber, archivePath, sourcePath))
        self.conn.commit()

    def insertTracking(self, seriesName, anilistId: int):
        cur = self.__getCursor()

        query = """
        INSERT OR REPLACE INTO anilist(series, anilistId)
        VALUES(?, ?)
        """
        cur.execute(query, (seriesName, anilistId))
        self.conn.commit()

    def insertMangaUpdt(self, anilistId, mangaUpdatesId: int):
        cur = self.__getCursor()

        query = """
        UPDATE anilist
        SET mangaUpdatesId = ?
        WHERE anilistId = ?
        """
        cur.execute(query, (mangaUpdatesId, anilistId))
        self.conn.commit()

    def getAllSeriesWithLocalFiles(self) -> List[AnilistSeries]:
        cur = self.__getCursor()
        cur.execute(
            """SELECT DISTINCT b.anilistId AS anilistId,
                        a.series AS series,
                        b.mangaUpdatesId AS mangaUpdatesId
                        FROM manga a
                        INNER JOIN anilist b
                        ON a.series = b.series"""
        )
        rows = cur.fetchall()
        return map(lambda a: AnilistSeries(a["anilistId"], a["series"], a["mangaUpdatesId"]), rows)

    def getAllSeries(self) -> List[AnilistSeries]:
        cur = self.__getCursor()
        cur.execute(
            """
            SELECT DISTINCT anilistId, series, mangaUpdatesId FROM anilist
            """
        )
        rows = cur.fetchall()
        return map(lambda a: AnilistSeries(a["anilistId"], a["series"], a["mangaUpdatesId"]), rows)

    def getAllSeriesWithoutTrackerIds(self) -> List[str]:
        cur = self.__getCursor()
        cur.execute(
            """SELECT DISTINCT a.series FROM manga a
                        LEFT JOIN anilist b
                        ON a.series = b.series
                    WHERE anilistId IS NULL"""
        )
        rows = cur.fetchall()
        return rows

    def getChaptersForSeriesBeforeNumber(self, anilistId, chapter):
        cur = self.__getCursor()
        cur.execute(
            """
            SELECT chapter
            FROM manga a
            INNER JOIN anilist b
            ON a.series = b.series
            WHERE anilistId = ?
            AND CAST(chapter AS REAL) <= ?
                        """,
            (anilistId, chapter),
        )
        rows = cur.fetchall()
        return rows

    def getSourceForChapter(self, series, chapter):
        cur = self.__getCursor()
        cur.execute(
            """SELECT source FROM manga
                        WHERE series = ? AND chapter = ? """,
            (series, chapter),
        )
        row = cur.fetchone()
        if row is not None:
            return row["source"]
        else:
            return None

    def getArchiveForChapter(self, series, chapter):
        cur = self.__getCursor()
        series = series
        cur.execute(
            """SELECT archive FROM manga
                        WHERE series = ? AND chapter = ? """,
            (series, chapter),
        )
        row = cur.fetchone()
        if row is not None:
            return row["archive"]
        else:
            return None

    def getAnilistIDForSeries(self, series):
        cur = self.__getCursor()
        series = series
        cur.execute(
            """SELECT anilistId FROM anilist
                        WHERE series = ?""",
            (series,),
        )
        row = cur.fetchone()
        if row is not None:
            return row["anilistId"]
        else:
            return None

    def getLowestChapterAndLastUpdatedForSeries(self):
        cur = self.__getCursor()
        cur.execute(
            """
        SELECT MIN(CAST(a.chapter AS INT)), a.series, anilistId, MAX(a.creation_date)
        FROM manga a
        INNER JOIN anilist AS b
        ON a.series = b.series
        GROUP BY anilistId
                        """
        )
        # HAVING MAX(a.creation_date) > ?
        return cur.fetchall()

    def getHighestChapterAndLastUpdatedForSeries(self, anilistId):
        cur = self.__getCursor()
        cur.execute(
            """
        SELECT MAX(CAST(a.chapter AS INT)) AS max_chapter,
          a.series,
          anilistId,
          mangaUpdatesId,
          MAX(a.creation_date) AS max_date
        FROM anilist b
        LEFT JOIN manga AS a
        ON a.series = b.series
        WHERE anilistId = ?
        GROUP BY anilistId;
                        """
        , (anilistId,))
        return cur.fetchone()