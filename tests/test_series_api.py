import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from API import fastapi


async def request_series(query="", path="/database/series"):
    """Exercise ASGI routing and query validation without an HTTP client dependency."""
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await fastapi.app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": query.encode(),
        "root_path": "", "headers": [], "server": ("test", 80),
        "client": ("test", 1234),
    }, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(body)


class TestSeriesEndpoint(unittest.TestCase):
    def setUp(self):
        self.database = MagicMock()
        patcher = patch.object(fastapi, "database_gateway", self.database)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.filesystem = MagicMock()
        self.filesystem.getQuarantinedSeries.return_value = [42]
        patcher = patch.object(fastapi, "filesystem_gateway", self.filesystem)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tracker = MagicMock()
        patcher = patch.object(fastapi, "anilist_gateway", self.tracker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_series_with_default_pagination(self):
        series = [{"series": "Alpha", "anilistId": None, "last_updated": "2026-02-01T00:00:00+00:00", "quarantined": False}]
        self.database.getAllDetailedSeries.return_value = (series, 1)
        status, body = asyncio.run(request_series())
        self.assertEqual(status, 200)
        self.assertEqual(body, {"series": series, "total": 1, "limit": 50, "offset": 0})
        self.database.getAllDetailedSeries.assert_called_once_with(
            title=None, limit=50, offset=0, quarantined_ids=[42], quarantined=None,
            sort_by="last_updated", sort_direction="desc",
        )
        self.tracker.getProgressFor.assert_not_called()

    def test_passes_trimmed_search_and_pagination(self):
        self.database.getAllDetailedSeries.return_value = ([], 0)
        status, body = asyncio.run(request_series("title=%20Alpha%20&limit=10&offset=20"))
        self.assertEqual(status, 200)
        self.assertEqual(body["series"], [])
        self.database.getAllDetailedSeries.assert_called_once_with(
            title="Alpha", limit=10, offset=20, quarantined_ids=[42], quarantined=None,
            sort_by="last_updated", sort_direction="desc",
        )

    def test_filters_mangaupdates_status_before_pagination(self):
        self.database.getAllDetailedSeries.return_value = ([
            {
                "series": "Current", "anilistId": None, "latest_stored_chapter": 10,
                "mangaupdates_latest_chapter": 10,
            },
            {
                "series": "No mapping", "anilistId": None, "latest_stored_chapter": 2,
                "mangaupdates_latest_chapter": 5,
            },
            {
                "series": "No AniList", "anilistId": None, "latest_stored_chapter": 1,
                "mangaupdates_latest_chapter": 3,
            },
            {
                "series": "No cache", "anilistId": None, "latest_stored_chapter": 2,
                "mangaupdates_latest_chapter": None,
            },
            {
                "series": "Unmapped progress", "anilistId": 43, "latest_stored_chapter": 2,
                "mangaupdates_latest_chapter": 5,
            },
        ], 5)
        self.tracker.getAllEntries.return_value = {}

        status, body = asyncio.run(request_series(
            "mangaupdates_status=unknown&limit=1&offset=1"
        ))

        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 2)
        self.assertEqual([item["series"] for item in body["series"]], ["No AniList"])
        self.database.getAllDetailedSeries.assert_called_once_with(
            title=None, limit=None, offset=0, quarantined_ids=[42], quarantined=None,
            sort_by="last_updated", sort_direction="desc",
        )
        self.tracker.getAllEntries.assert_called_once_with(reading_only=False)

    def test_rejects_invalid_mangaupdates_status_filter(self):
        status, _ = asyncio.run(request_series("mangaupdates_status=ongoing"))
        self.assertEqual(status, 422)
        self.database.getAllDetailedSeries.assert_not_called()

    def test_rejects_invalid_pagination(self):
        for query in ("limit=0", "limit=101", "offset=-1", "limit=invalid"):
            with self.subTest(query=query):
                status, _ = asyncio.run(request_series(query))
                self.assertEqual(status, 422)
        self.database.getAllDetailedSeries.assert_not_called()

    def test_database_failure_returns_server_error(self):
        self.database.getAllDetailedSeries.side_effect = RuntimeError("Database unavailable")
        status, body = asyncio.run(request_series())
        self.assertEqual(status, 500)
        self.assertEqual(body["detail"], "Database unavailable")

    def test_passes_filter_and_sort_options(self):
        self.database.getAllDetailedSeries.return_value = ([], 0)
        for value, expected in (("true", True), ("false", False)):
            status, _ = asyncio.run(request_series(f"quarantined={value}&sort_by=quarantined&sort_direction=asc"))
            self.assertEqual(status, 200)
            self.assertEqual(self.database.getAllDetailedSeries.call_args.kwargs["quarantined"], expected)
            self.assertEqual(self.database.getAllDetailedSeries.call_args.kwargs["sort_by"], "quarantined")
            self.assertEqual(self.database.getAllDetailedSeries.call_args.kwargs["sort_direction"], "asc")

    def test_rejects_invalid_filter_and_sort(self):
        for query in ("quarantined=invalid", "sort_by=invalid", "sort_direction=invalid"):
            status, _ = asyncio.run(request_series(query))
            self.assertEqual(status, 422)
        self.database.getAllDetailedSeries.assert_not_called()

    def test_quarantine_details_are_read_only_and_scoped_to_one_series(self):
        self.database.getActiveChaptersForAnilist.return_value = [{"series": "Alpha", "chapter": "37"}]
        self.tracker.getProgressFor.return_value = 35
        status, body = asyncio.run(request_series(path="/database/series/42/quarantine-details"))
        self.assertEqual(status, 200)
        self.assertEqual(body, {"quarantined": True, "status": "gaps_found", "reasons": [
            {"type": "tracker_gap", "last_read": 35, "first_stored": 37},
        ]})
        self.database.getActiveChaptersForAnilist.assert_called_once_with(42)
        self.tracker.getProgressFor.assert_called_once_with(42)
        self.database.getAllChapters.assert_not_called()
        self.tracker.getAllEntries.assert_not_called()
        self.filesystem.quarantineSeries.assert_not_called()
        self.filesystem.restoreQuarantinedArchive.assert_not_called()

    def test_nonquarantined_series_skips_gap_check(self):
        status, body = asyncio.run(request_series(path="/database/series/43/quarantine-details"))
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "not_quarantined")
        self.assertFalse(body["quarantined"])
        self.database.getActiveChaptersForAnilist.assert_not_called()
        self.tracker.getProgressFor.assert_not_called()

    def test_details_failure_returns_server_error(self):
        self.database.getActiveChaptersForAnilist.side_effect = RuntimeError("Database unavailable")
        status, _ = asyncio.run(request_series(path="/database/series/42/quarantine-details"))
        self.assertEqual(status, 500)
