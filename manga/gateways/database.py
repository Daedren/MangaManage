from datetime import datetime
import sqlite3
from typing import List
from contextlib import contextmanager
from .utils.databaseModels import AnilistSeries
from .databaseMigrations import DatabaseMigrations


class DatabaseGateway:
    def __init__(self, databaseLocation: str) -> None:
        self.databaseLocation = databaseLocation
        with self.__conn() as (conn, _):
            self.migrations = DatabaseMigrations()
            self.migrations.doMigrations(conn)
        super().__init__()

    @contextmanager
    def __conn(self):
        conn = sqlite3.connect(self.databaseLocation)
        conn.row_factory = sqlite3.Row
        yield conn, conn.cursor()
        conn.close()

    def getAllChapters(self):
        with self.__conn() as (_, cur):
            query = """
            SELECT chapter, anilistId
            FROM manga
            INNER JOIN anilist
            ON manga.series = anilist.series
            WHERE active = 1
            """
            cur.execute(query)
            rows = cur.fetchall()
            return rows

    def getAllDetailedChapters(self):
        with self.__conn() as (_, cur):
            query = """
            SELECT manga.series, chapter, creation_date, anilistId
            FROM manga
            INNER JOIN anilist
            ON manga.series = anilist.series
            WHERE active = 1
            ORDER BY manga.series, chapter
            """
            cur.execute(query)
            rows = cur.fetchall()
            return rows

    def getSeriesForAnilist(self, anilistId):
        with self.__conn() as (_, cur):

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

    def doesExistChapterAndAnilist(self, anilistId, chapterNumber):
        with self.__conn() as (_, cur):

            # Remember that anilist only stores integers for chapter numbers!
            query = """
            SELECT a.series
            FROM manga a
            INNER JOIN anilist b
            ON a.series = b.series
            WHERE chapter = ? AND anilistId = ? AND a.active = 1
            """
            cur.execute(query, (chapterNumber, anilistId))
            row = cur.fetchone()
            return row

    def deleteChapter(self, anilistId, chapterNumber):
        with self.__conn() as (conn, cur):

            # Remember that anilist only stores integers for chapter numbers!
            query = """
            UPDATE manga
            SET active = 0, last_active = datetime('now')
            WHERE chapter = ?
            AND series IN ( SELECT series FROM anilist WHERE anilistId = ?)
            """
            cur.execute(query, (chapterNumber, anilistId))
            conn.commit()

    def insertChapter(self, seriesName, chapterNumber: str, archivePath, sourcePath):
        with self.__conn() as (conn, cur):

            query = """
            INSERT INTO manga(series, chapter, archive, source)
            VALUES(?,?,?,?)
            """
            cur.execute(query, (seriesName, chapterNumber, archivePath, sourcePath))
            conn.commit()

    def insertTracking(self, seriesName, anilistId: int):
        with self.__conn() as (conn, cur):

            query = """
            INSERT OR REPLACE INTO anilist(series, anilistId)
            VALUES(?, ?)
            """
            cur.execute(query, (seriesName, anilistId))
            conn.commit()

    def insertMangaUpdt(self, anilistId, mangaUpdatesId: int):
        with self.__conn() as (conn, cur):

            query = """
            INSERT INTO mangaupd(mangaUpdatesId, anilistId)
            VALUES(?, ?)
            """
            cur.execute(query, (mangaUpdatesId, anilistId))
            conn.commit()

    def updateMangaUpdtLatestChapter(self, mangaUpdatesId: int, latestChapter: int):
        with self.__conn() as (conn, cur):

            query = """
            UPDATE mangaupd
            SET latestChapter = ?
            WHERE mangaUpdatesId = ?
            """
            cur.execute(query, (latestChapter, mangaUpdatesId))
            conn.commit()

    def getAllSeriesWithLocalFiles(self) -> List[AnilistSeries]:
        with self.__conn() as (_, cur):

            cur.execute(
                """SELECT DISTINCT b.anilistId AS anilistId,
                            a.series AS series,
                            c.mangaUpdatesId AS mangaUpdatesId
                            FROM manga a
                            INNER JOIN anilist b
                            ON a.series = b.series
                            LEFT JOIN mangaupd c
                            ON b.anilistId = c.anilistId
                            WHERE a.active = 1"""
            )
            rows = cur.fetchall()
            return map(
                lambda a: AnilistSeries(
                    a["anilistId"], a["series"], a["mangaUpdatesId"]
                ),
                rows,
            )

    def getAllSeries(self) -> List[AnilistSeries]:
        with self.__conn() as (_, cur):

            cur.execute(
                """
                SELECT DISTINCT a.anilistId, a.series, b.mangaUpdatesId
                FROM anilist a
                LEFT JOIN mangaUpd b
                ON a.anilistId = b.anilistId
                """
            )
            rows = cur.fetchall()
            return map(
                lambda a: AnilistSeries(
                    a["anilistId"], a["series"], a["mangaUpdatesId"]
                ),
                rows,
            )

    def getAllSeriesWithoutTrackerIds(self) -> List[str]:
        with self.__conn() as (_, cur):

            cur.execute(
                """SELECT DISTINCT a.series FROM manga a
                            LEFT JOIN anilist b
                            ON a.series = b.series
                        WHERE anilistId IS NULL and a.active = 1"""
            )
            rows = cur.fetchall()
            return rows

    def getChaptersForSeriesBeforeNumber(self, anilistId, chapter):
        with self.__conn() as (_, cur):

            cur.execute(
                """
                SELECT chapter
                FROM manga a
                INNER JOIN anilist b
                ON a.series = b.series
                WHERE anilistId = ?
                AND CAST(chapter AS REAL) <= ?
                AND a.active = 1
                            """,
                (anilistId, chapter),
            )
            rows = cur.fetchall()
            return rows

    def getSourceForChapter(self, series, chapter):
        with self.__conn() as (_, cur):

            cur.execute(
                """SELECT source FROM manga
                            WHERE series = ? AND chapter = ? AND active = 1""",
                (series, chapter),
            )
            row = cur.fetchone()
            if row is not None:
                return row["source"]
            else:
                return None

    def getArchiveForChapter(self, series, chapter):
        with self.__conn() as (_, cur):

            series = series
            cur.execute(
                """SELECT archive FROM manga
                            WHERE series = ? AND chapter = ? AND active = 1""",
                (series, chapter),
            )
            row = cur.fetchone()
            if row is not None:
                return row["archive"]
            else:
                return None

    def getAnilistIDForSeries(self, series):
        with self.__conn() as (_, cur):

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
        with self.__conn() as (_, cur):

            cur.execute(
                """
            SELECT MIN(CAST(a.chapter AS INT)), a.series, anilistId, MAX(a.creation_date)
            FROM manga a
            INNER JOIN anilist AS b
            ON a.series = b.series
            WHERE a.active = 1
            GROUP BY anilistId
                            """
            )
            # HAVING MAX(a.creation_date) > ?
            return cur.fetchall()

    def getHighestChapterAndLastUpdatedForSeries(self):
        with self.__conn() as (_, cur):

            cur.execute(
                """
SELECT
    MAX(
        CASE
            WHEN mng.active = 1 THEN CAST(mng.chapter AS INT)
            ELSE NULL
        END
    ) AS max_chapter,
    mng.series,
    upd.anilistId,
    upd.mangaUpdatesId,
    upd.latestChapter,
    MAX(mng.creation_date) AS max_date
FROM
    mangaupd upd
    LEFT JOIN anilist AS ani ON upd.anilistId = ani.anilistId
    LEFT JOIN manga AS mng ON ani.series = mng.series
GROUP BY
    upd.anilistId;
                            """,
                (),
            )
            rows = cur.fetchall()
            # Create anilist ID keyed dictionary
            model_dictionary = dict((v['anilistId'], v) for v in rows)
            return model_dictionary

    def getAllChaptersOfSeriesUpdatedAfter(self, lastUpdated: datetime):
        with self.__conn() as (_, cur):

            query = """
            SELECT chapter, anilistId
            FROM manga a
            INNER JOIN anilist b
            ON a.series = b.series
            WHERE active = 1 AND a.series IN (
              SELECT DISTINCT series
              FROM manga c
              WHERE creation_date > ?
            )
            """
            cur.execute(query, (lastUpdated,))
            rows = cur.fetchall()
            return rows

    def getSeriesLastUpdatedSince(self, lastUpdated: datetime):
        with self.__conn() as (_, cur):

            query = """
            SELECT anilistId, MAX(a.creation_date) AS lastUpdated
            FROM manga a
            INNER JOIN anilist b
            ON a.series = b.series
            WHERE a.creation_date > ?
            GROUP BY anilistId
            """
            cur.execute(query, (lastUpdated,))
            rows = cur.fetchall()
            return rows

    # def getVolumeChapters(self, anilistId):
    #    cur = self.__getCursor()
    #    cur.execute(
    #        """SELECT volume, MAX(volumeChapter) FROM manga a
    #           INNER JOIN anilist b
    #           ON a.series = b.series
    #           WHERE anilistId = ?
    #           GROUP BY anilistId, volume;
    #        """,
    #        (anilistId, )
    #    )
    #    rows = cur.fetchall()
    #    return rows
