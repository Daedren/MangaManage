import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from manga.gateways.database import DatabaseGateway


class TestDatabaseSeries(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.database_path = str(Path(self.temp_directory.name) / "series.db")
        self.database = DatabaseGateway(self.database_path)

    def insert_chapter(self, series, chapter, timestamp, active=1):
        with closing(sqlite3.connect(self.database_path)) as conn, conn:
            conn.execute(
                "INSERT INTO manga (series, chapter, creation_date, active) VALUES (?, ?, ?, ?)",
                (series, chapter, timestamp, active),
            )

    def test_uses_newest_timestamp_not_highest_chapter_and_includes_inactive(self):
        self.insert_chapter("Alpha", "100", "2026-01-01 10:00:00")
        self.insert_chapter("Alpha", "2", "2026-02-01 10:00:00", active=0)
        with closing(sqlite3.connect(self.database_path)) as conn, conn:
            conn.execute("INSERT INTO anilist (series, anilistId) VALUES ('Alpha', 42)")

        series, total = self.database.getAllDetailedSeries()

        self.assertEqual(total, 1)
        self.assertEqual(series, [{
            "series": "Alpha", "anilistId": 42,
            "last_updated": "2026-02-01T10:00:00+00:00",
            "quarantined": False,
        }])

    def test_includes_unmapped_and_inactive_only_series(self):
        self.insert_chapter("Unmapped", "1", "2026-02-01 00:00:00", active=0)
        series, total = self.database.getAllDetailedSeries()
        self.assertEqual(total, 1)
        self.assertEqual(series[0]["series"], "Unmapped")
        self.assertIsNone(series[0]["anilistId"])

    def test_search_pagination_and_deterministic_order(self):
        self.insert_chapter("Alpha", "1", "2026-02-01 00:00:00")
        self.insert_chapter("Beta", "1", "2026-02-01 00:00:00")
        self.insert_chapter("Latest", "1", "2026-03-01 00:00:00")
        self.insert_chapter("Latest", "2", "2026-01-01 00:00:00")
        series, total = self.database.getAllDetailedSeries(limit=1, offset=1)
        self.assertEqual(total, 3)
        self.assertEqual([item["series"] for item in series], ["Alpha"])
        series, total = self.database.getAllDetailedSeries(title="lat")
        self.assertEqual(total, 1)
        self.assertEqual(series[0]["last_updated"], "2026-03-01T00:00:00+00:00")

    def test_normalizes_timezone_before_choosing_maximum(self):
        self.insert_chapter("Alpha", "1", "2026-02-01T10:00:00+02:00")
        self.insert_chapter("Alpha", "2", "2026-02-01T09:00:00Z")
        series, _ = self.database.getAllDetailedSeries()
        self.assertEqual(series[0]["last_updated"], "2026-02-01T09:00:00+00:00")

    def test_missing_dates_sort_last(self):
        self.insert_chapter("Unknown", "1", None)
        self.insert_chapter("Known", "1", "2026-01-01 00:00:00")
        series, _ = self.database.getAllDetailedSeries()
        self.assertEqual([item["series"] for item in series], ["Known", "Unknown"])
        self.assertIsNone(series[1]["last_updated"])

    def test_empty_results(self):
        self.assertEqual(self.database.getAllDetailedSeries(), ([], 0))
        self.insert_chapter("Alpha", "1", "2026-01-01 00:00:00")
        self.assertEqual(self.database.getAllDetailedSeries(title="missing"), ([], 0))

    def test_pagination_bounds(self):
        self.insert_chapter("Alpha", "1", "2026-01-01 00:00:00")
        series, total = self.database.getAllDetailedSeries(limit=0, offset=-1)
        self.assertEqual(total, 1)
        self.assertEqual(len(series), 1)

    def seed_quarantined_series(self):
        for name, tracker_id in (("Alpha", 42), ("Beta", 43), ("gamma", 44)):
            self.insert_chapter(name, "1", "2026-02-01 00:00:00")
            with closing(sqlite3.connect(self.database_path)) as conn, conn:
                conn.execute("INSERT INTO anilist (series, anilistId) VALUES (?, ?)", (name, tracker_id))
        self.insert_chapter("Unmapped", "1", "2026-03-01 00:00:00")

    def test_quarantine_filter_applied_before_count_and_pagination(self):
        self.seed_quarantined_series()
        series, total = self.database.getAllDetailedSeries(
            quarantined_ids=[42, 44], quarantined=True, limit=1, offset=1,
        )
        self.assertEqual(total, 2)
        self.assertEqual([item["series"] for item in series], ["gamma"])
        self.assertTrue(series[0]["quarantined"])
        series, total = self.database.getAllDetailedSeries(quarantined_ids=[42, 44], quarantined=False)
        self.assertEqual(total, 2)
        self.assertEqual([item["series"] for item in series], ["Unmapped", "Beta"])
        self.assertTrue(all(not item["quarantined"] for item in series))
        series, total = self.database.getAllDetailedSeries(title="alp", quarantined_ids=[42], quarantined=True)
        self.assertEqual(total, 1)
        self.assertEqual(series[0]["series"], "Alpha")

    def test_empty_quarantine_list(self):
        self.seed_quarantined_series()
        self.assertEqual(self.database.getAllDetailedSeries(quarantined=True), ([], 0))
        _, total = self.database.getAllDetailedSeries(quarantined=False)
        self.assertEqual(total, 4)

    def test_sort_each_column_in_both_directions(self):
        self.seed_quarantined_series()
        expected = {
            ("series", "asc"): ["Alpha", "Beta", "gamma", "Unmapped"],
            ("series", "desc"): ["Unmapped", "gamma", "Beta", "Alpha"],
            ("last_updated", "asc"): ["Alpha", "Beta", "gamma", "Unmapped"],
            ("last_updated", "desc"): ["Unmapped", "Alpha", "Beta", "gamma"],
            ("quarantined", "asc"): ["Beta", "Unmapped", "Alpha", "gamma"],
            ("quarantined", "desc"): ["Alpha", "gamma", "Beta", "Unmapped"],
        }
        for (column, direction), names in expected.items():
            with self.subTest(column=column, direction=direction):
                series, _ = self.database.getAllDetailedSeries(
                    quarantined_ids=[42, 44], sort_by=column, sort_direction=direction,
                )
                self.assertEqual([item["series"] for item in series], names)

    def test_missing_dates_sort_last_ascending_too(self):
        self.insert_chapter("Unknown", "1", None)
        self.insert_chapter("Known", "1", "2026-01-01 00:00:00")
        series, _ = self.database.getAllDetailedSeries(sort_direction="asc")
        self.assertEqual([item["series"] for item in series], ["Known", "Unknown"])

    def test_sort_allowlist(self):
        for options in ({"sort_by": "series; DROP TABLE manga"}, {"sort_direction": "invalid"}):
            with self.assertRaises(ValueError):
                self.database.getAllDetailedSeries(**options)

    def test_reads_only_active_chapters_for_selected_series(self):
        self.seed_quarantined_series()
        self.insert_chapter("Alpha", "2", "2026-03-01 00:00:00", active=0)
        self.assertEqual(self.database.getActiveChaptersForAnilist(42), [{"series": "Alpha", "chapter": "1"}])
