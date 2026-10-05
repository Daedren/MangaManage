from datetime import datetime, timezone
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

    def getAllDetailedChapters(self, active: int = 1, title: str = None, limit: int = 50, offset: int = 0):
        limit = min(max(1, limit), 100)
        with self.__conn() as (_, cur):
            conditions = ["manga.active = ?"]
            filter_params = [active]
            if title:
                conditions.append("manga.series LIKE ?")
                filter_params.append(f"%{title}%")
            where = " AND ".join(conditions)

            cur.execute(
                f"SELECT COUNT(*) FROM manga INNER JOIN anilist ON manga.series = anilist.series WHERE {where}",
                filter_params,
            )
            total = cur.fetchone()[0]

            query = f"""
            SELECT manga.id, manga.series, chapter, creation_date, anilistId, manga.active
            FROM manga
            INNER JOIN anilist
            ON manga.series = anilist.series
            WHERE {where}
            ORDER BY datetime(manga.creation_date) DESC
            LIMIT ? OFFSET ?
            """
            cur.execute(query, filter_params + [limit, offset])
            rows = cur.fetchall()
            return rows, total

    def getAllDetailedSeries(
        self, title: str = None, limit: int | None = 50, offset: int = 0,
        quarantined_ids=(), quarantined=None, sort_by="last_updated", sort_direction="desc",
    ):
        if limit is not None:
            limit = min(max(1, limit), 100)
        offset = max(0, offset)
        columns = {"series": "series COLLATE NOCASE", "last_updated": "last_updated", "quarantined": "quarantined"}
        if sort_by not in columns or sort_direction not in ("asc", "desc"):
            raise ValueError("Invalid series sort")
        ids = sorted(set(quarantined_ids))
        membership = f"grouped.anilistId IN ({','.join('?' for _ in ids)})" if ids else "0"
        # Match any alias without excluding other aliases' chapters from aggregates.
        having = "HAVING MAX(manga.series LIKE ?) = 1" if title else ""
        params = ([f"%{title}%"] if title else []) + ids
        cte = f"""
            WITH grouped AS (
                SELECT MIN(manga.series) AS series, anilist.anilistId,
                       MAX(datetime(manga.creation_date)) AS last_updated,
                       MAX(CASE WHEN manga.active = 1 THEN CAST(manga.chapter AS REAL) END) AS latest_stored_chapter
                FROM manga INNER JOIN anilist ON manga.series = anilist.series
                WHERE anilist.anilistId IS NOT NULL
                GROUP BY anilist.anilistId {having}
            ), detailed AS (
                SELECT grouped.series, grouped.anilistId, grouped.last_updated,
                       grouped.latest_stored_chapter, mangaupd.mangaUpdatesId AS mangaupdates_id,
                       mangaupd.latestChapter AS mangaupdates_latest_chapter,
                       mangaupd.mangaUpdatesUrl AS mangaupdates_url,
                       COALESCE({membership}, 0) AS quarantined
                FROM grouped
                LEFT JOIN mangaupd ON grouped.anilistId = mangaupd.anilistId
            )
        """
        status_where = "WHERE quarantined = ?" if quarantined is not None else ""
        if quarantined is not None:
            params.append(int(quarantined))
        # Unknown dates always come last; AniList ID breaks ties between groups.
        null_order = "last_updated IS NULL ASC," if sort_by == "last_updated" else ""
        order = f"{null_order} {columns[sort_by]} {sort_direction.upper()}, series COLLATE NOCASE ASC, series ASC, anilistId ASC"
        with self.__conn() as (_, cur):
            cur.execute(
                f"{cte} SELECT COUNT(*) FROM detailed {status_where}",
                params,
            )
            total = cur.fetchone()[0]
            query = f"""
                {cte}
                SELECT * FROM detailed {status_where}
                ORDER BY {order}
            """
            query_params = params
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                query_params = params + [limit, offset]
            cur.execute(query, query_params)
            series = [dict(row) for row in cur.fetchall()]
            for item in series:
                item["quarantined"] = bool(item["quarantined"])
                if item["last_updated"] is not None:
                    item["last_updated"] = datetime.fromisoformat(
                        item["last_updated"]
                    ).replace(tzinfo=timezone.utc).isoformat()
            return series, total

    def getActiveChaptersForAnilist(self, anilist_id: int):
        with self.__conn() as (_, cur):
            cur.execute(
                """SELECT manga.series, manga.chapter FROM manga
                   INNER JOIN anilist ON manga.series = anilist.series
                   WHERE anilist.anilistId = ? AND manga.active = 1""",
                (anilist_id,),
            )
            return [dict(row) for row in cur.fetchall()]

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
    
    def deleteChapterById(self, chapterId):
        with self.__conn() as (conn, cur):

            query = """
            UPDATE manga
            SET active = 0, last_active = datetime('now')
            WHERE id = ?
            """
            cur.execute(query, (chapterId,))
            conn.commit()

    def getChapterDetailsById(self, chapterId):
        with self.__conn() as (_, cur):
            query = """
            SELECT manga.chapter, anilist.anilistId
            FROM manga
            INNER JOIN anilist
            ON manga.series = anilist.series
            WHERE manga.id = ?
            """
            cur.execute(query, (chapterId,))
            return cur.fetchone()

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

    def updateMangaUpdtLatestChapter(
        self, mangaUpdatesId: int, latestChapter: int = None, mangaUpdatesUrl: str = None,
    ):
        with self.__conn() as (conn, cur):

            query = """
            UPDATE mangaupd
            SET latestChapter = COALESCE(?, latestChapter),
                mangaUpdatesUrl = COALESCE(mangaUpdatesUrl, ?)
            WHERE mangaUpdatesId = ?
            """
            cur.execute(query, (latestChapter, mangaUpdatesUrl, mangaUpdatesId))
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
    upd.mangaUpdatesUrl,
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
