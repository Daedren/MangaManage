import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from API import fastapi
from manga.gateways.utils.exceptions import AnilistRequestException, TokenRefreshException


class TestSeriesUpdates(unittest.TestCase):
    def setUp(self):
        self.database = MagicMock()
        self.tracker = MagicMock()
        self.filesystem = MagicMock()
        self.filesystem.getQuarantinedSeries.return_value = []
        self.tracker.getAllEntries.return_value = {}
        self.mangaupdates = MagicMock()
        for name, gateway in (
            ("database_gateway", self.database), ("anilist_gateway", self.tracker),
            ("filesystem_gateway", self.filesystem), ("mangaupd_gateway", self.mangaupdates),
        ):
            patcher = patch.object(fastapi, name, gateway)
            patcher.start()
            self.addCleanup(patcher.stop)

    def row(self, media_id=42, stored=8, latest=10, mangaupdates_id=123):
        return {
            "series": f"Series {media_id}", "anilistId": media_id,
            "last_updated": None, "quarantined": False,
            "latest_stored_chapter": stored, "mangaupdates_latest_chapter": latest,
            "mangaupdates_id": mangaupdates_id,
        }

    def fetch(self, rows):
        self.database.getAllDetailedSeries.return_value = (rows, len(rows))
        result = fastapi.get_all_series(limit=50, offset=0)
        self.tracker.getProgressFor.assert_not_called()
        self.tracker.clearCache.assert_not_called()
        self.mangaupdates.getLatestChapterForId.assert_not_called()
        return result["series"]

    def test_stored_chapter_equal_or_ahead_is_up_to_date_without_anilist(self):
        rows = self.fetch([self.row(stored=10), self.row(media_id=43, stored=11.5)])
        self.assertTrue(all(row["mangaupdates_status"] == "up_to_date" for row in rows))
        self.tracker.getAllEntries.assert_not_called()

    def test_one_general_progress_lookup_for_all_series(self):
        self.tracker.getAllEntries.return_value = {
            42: SimpleNamespace(progress=10), 43: SimpleNamespace(progress=12),
            44: SimpleNamespace(progress=9),
        }
        rows = self.fetch([self.row(media_id=id) for id in (42, 43, 44)])
        self.assertEqual([row["mangaupdates_status"] for row in rows],
                         ["up_to_date", "up_to_date", "missing_chapters"])
        self.assertEqual([row["anilist_last_read"] for row in rows], [10, 12, 9])
        self.tracker.getAllEntries.assert_called_once_with(reading_only=False)

    def test_missing_cache_is_unavailable_and_skips_anilist(self):
        rows = self.fetch([self.row(latest=None), self.row(media_id=None, latest=None)])
        self.assertTrue(all(row["mangaupdates_status"] == "unavailable" for row in rows))
        self.tracker.getAllEntries.assert_not_called()

    def test_absent_read_entry_and_no_active_chapters_are_missing(self):
        rows = self.fetch([self.row(stored=None)])
        self.assertEqual(rows[0]["mangaupdates_status"], "missing_chapters")
        self.assertIsNone(rows[0]["anilist_last_read"])

    def test_no_tracker_mapping_is_unknown_without_anilist(self):
        rows = self.fetch([self.row(media_id=None)])
        self.assertEqual(rows[0]["mangaupdates_status"], "unknown")
        self.assertIn("no AniList ID assigned", rows[0]["mangaupdates_status_reason"])
        self.tracker.getAllEntries.assert_not_called()

    def test_anilist_failure_keeps_list_and_stored_up_to_date_status(self):
        self.tracker.getAllEntries.side_effect = RuntimeError("AniList unavailable")
        with self.assertLogs("API.fastapi", level="WARNING"):
            rows = self.fetch([self.row(), self.row(media_id=43, stored=10)])
        self.assertEqual([row["mangaupdates_status"] for row in rows], ["unknown", "up_to_date"])
        self.assertIn("lookup failed (RuntimeError)", rows[0]["mangaupdates_status_reason"])
        self.assertIsNone(rows[1]["mangaupdates_status_reason"])

    def test_anilist_none_response_is_unknown(self):
        self.tracker.getAllEntries.return_value = None
        row = self.fetch([self.row()])[0]
        self.assertEqual(row["mangaupdates_status"], "unknown")
        self.assertEqual(row["mangaupdates_status_reason"], "AniList returned no read-progress response.")

    def test_empty_page_skips_anilist(self):
        self.assertEqual(self.fetch([]), [])
        self.tracker.getAllEntries.assert_not_called()

    def test_zero_chapter_is_known_not_unavailable(self):
        row = self.fetch([self.row(stored=None, latest=0)])[0]
        self.assertEqual(row["mangaupdates_status"], "up_to_date")

    def test_general_progress_endpoint(self):
        self.tracker.getAllEntries.return_value = {42: SimpleNamespace(progress=10)}
        self.assertEqual(fastapi.get_anilist_progress_list(), {"progress": {42: 10}})
        self.tracker.getAllEntries.assert_called_once_with(reading_only=False)
        self.tracker.getProgressFor.assert_not_called()

    def test_general_progress_endpoint_failure(self):
        self.tracker.getAllEntries.return_value = None
        with self.assertRaises(HTTPException) as caught:
            fastapi.get_anilist_progress_list()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail, "AniList returned no read-progress response.")

    def test_missing_ids_and_missing_cached_chapter_have_separate_reasons(self):
        rows = self.fetch([
            self.row(media_id=None, latest=None, mangaupdates_id=None),
            self.row(media_id=42, latest=None, mangaupdates_id=None),
            self.row(media_id=43, latest=None),
        ])
        self.assertEqual([row["mangaupdates_status_reason"] for row in rows], [
            "No AniList ID assigned; MangaUpdates cannot be linked.",
            "No MangaUpdates ID linked to this series.",
            "MangaUpdates ID is linked, but no latest chapter has been cached.",
        ])
        self.tracker.getAllEntries.assert_not_called()

    def test_specific_anilist_failures(self):
        for error, message in (
            (TokenRefreshException("https://example.com"), "authentication needs renewal"),
            (AnilistRequestException(401), "authentication failed (HTTP 401)"),
            (AnilistRequestException(403), "access denied (HTTP 403)"),
            (AnilistRequestException(429), "rate limit reached (HTTP 429)"),
            (AnilistRequestException(503), "API request failed (status 503)"),
            (AnilistRequestException(), "rejected the read-progress query"),
            (TimeoutError(), "request timed out"),
            (ConnectionError(), "Could not connect to AniList"),
            (KeyError("data"), "invalid read-progress response"),
        ):
            with self.subTest(error=error):
                self.tracker.getAllEntries.side_effect = error
                if isinstance(error, KeyError):
                    with self.assertLogs("API.fastapi", level="WARNING"):
                        row = self.fetch([self.row()])[0]
                else:
                    row = self.fetch([self.row()])[0]
                self.assertEqual(row["mangaupdates_status"], "unknown")
                self.assertIn(message, row["mangaupdates_status_reason"])

    def test_absent_list_entry_is_distinct_from_failed_lookup(self):
        row = self.fetch([self.row()])[0]
        self.assertEqual(row["mangaupdates_status"], "missing_chapters")
        self.assertIn("not on your AniList list", row["mangaupdates_status_reason"])

    def test_null_progress_in_list_is_unknown(self):
        self.tracker.getAllEntries.return_value = {42: SimpleNamespace(progress=None)}
        row = self.fetch([self.row()])[0]
        self.assertEqual(row["mangaupdates_status"], "unknown")
        self.assertEqual(row["mangaupdates_status_reason"], "AniList returned no read progress for this series.")
