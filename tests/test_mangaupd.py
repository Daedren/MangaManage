import io
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime
from unittest.mock import MagicMock

from manga.gateways.mangaupd import MangaUpdatesGateway


class TestMangaUpdates(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.sleeps = []
        self.transport = MagicMock()
        self.sut = MangaUpdatesGateway(self.transport, lambda: self.now, self.sleep)

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def response(self, payload):
        return io.BytesIO(json.dumps(payload).encode())

    def searchResponse(self, series_id=123, title="Series", series_type="Manga"):
        return self.response({"results": [{"record": {
            "series_id": series_id, "title": title, "type": series_type,
        }}]})

    def httpError(self, code, retry_after=None):
        headers = Message()
        if retry_after is not None:
            headers["Retry-After"] = retry_after
        return urllib.error.HTTPError("https://api.mangaupdates.com/v1/series/search",
                                      code, "error", headers, io.BytesIO())

    def test_mostSearchableTitle_CodeBreaker(self):
        result = self.sut._MangaUpdatesGateway__getMostSearchableTitle(
            ['CØDE:BREAKER', 'Code:Breaker', 'コード:ブレイカー'])
        self.assertEqual(result, "Code:Breaker")

    def test_searchUsesPublicJsonApiAndReturnsNumericId(self):
        self.transport.return_value = self.searchResponse(title="Code:Breaker")
        self.assertEqual(self.sut.searchForSeries(["Code:Breaker"]), 123)
        request = self.transport.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://api.mangaupdates.com/v1/series/search"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {
            "search": "Code:Breaker", "stype": "title", "orderby": "score",
            "page": 1, "perpage": 20,
        })
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertIsNotNone(request.get_header("User-agent"))
        self.assertEqual(self.transport.call_args.kwargs, {"timeout": 30})

    def test_searchFiltersNovelsAndPrefersExactHitTitle(self):
        self.transport.return_value = self.response({"results": [
            {"record": {"series_id": 1, "title": "Series", "type": "Novel"}},
            {"record": {"series_id": 2, "title": "Series sequel", "type": "Manga"}},
            {"record": {"series_id": 3, "title": "Alternate title", "type": "Manhwa"},
             "hit_title": "ＳＥＲＩＥＳ"},
        ]})
        self.assertEqual(self.sut.searchForSeries(["series"]), 3)

    def test_searchFallsBackToFirstNonNovel(self):
        self.transport.return_value = self.searchResponse(title="Different title")
        with self.assertLogs("MangaUpdatesGateway", level="WARNING"):
            self.assertEqual(self.sut.searchForSeries(["Series"]), 123)

    def test_emptyNamesDoNotMakeRequests(self):
        for names in ([], ["", "  "]):
            self.assertIsNone(self.sut.searchForSeries(names))
        self.transport.assert_not_called()

    def test_noResultsOrOnlyNovelsReturnNone(self):
        self.transport.side_effect = [self.response({"results": []}),
                                      self.searchResponse(series_type="Novel")]
        self.assertIsNone(self.sut.searchForSeries(["Unknown"]))
        self.assertIsNone(self.sut.searchForSeries(["Novel"]))

    def test_invalidSearchResultsRaise(self):
        for payload in ({}, {"results": None}, {"results": [None]},
                        {"results": [{"record": {"series_id": "123"}}]},
                        {"results": [{"record": {"series_id": True}}]}):
            with self.subTest(payload=payload):
                self.sut._cache.clear()
                self.transport.return_value = self.response(payload)
                with self.assertRaises(ValueError):
                    self.sut.searchForSeries(["Series"])

    def test_latestChapterUsesSeriesJson(self):
        self.transport.return_value = self.response({
            "series_id": 123, "latest_chapter": 42,
        })
        self.assertEqual(self.sut.getLatestChapterForId(123), 42)
        request = self.transport.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.mangaupdates.com/v1/series/123")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)

    def test_latestChapterHandlesZeroAndUnknown(self):
        self.transport.side_effect = [self.response({"latest_chapter": 0}),
                                      self.response({"latest_chapter": None}),
                                      self.response({})]
        self.assertEqual(self.sut.getLatestChapterForId(1), 0)
        self.assertIsNone(self.sut.getLatestChapterForId(2))
        self.assertIsNone(self.sut.getLatestChapterForId(3))

    def test_latestChapterRejectsInvalidValues(self):
        for index, chapter in enumerate((True, "42", -1, 4.5), start=1):
            self.transport.return_value = self.response({"latest_chapter": chapter})
            with self.subTest(chapter=chapter), self.assertRaises(ValueError):
                self.sut.getLatestChapterForId(index)

    def test_invalidIdDoesNotMakeRequest(self):
        for series_id in (True, "123", 0, -1):
            with self.subTest(series_id=series_id), self.assertRaises(ValueError):
                self.sut.getLatestChapterForId(series_id)
        self.transport.assert_not_called()

    def test_searchRetriesAfterRateLimitAndKeepsLongerDelay(self):
        self.transport.side_effect = [self.httpError(429) for _ in range(3)] + [
            self.searchResponse(),
        ]
        self.assertEqual(self.sut.searchForSeries(["Series"]), 123)
        self.assertEqual(self.sleeps, [2, 4, 8])
        self.assertEqual(self.sut.request_delay_seconds, 8)
        self.transport.side_effect = [
            self.httpError(429), self.searchResponse(456, "Another Series"),
        ]
        self.assertEqual(self.sut.searchForSeries(["Another Series"]), 456)
        self.assertEqual(self.sleeps, [2, 4, 8, 8, 8])
        self.assertEqual(self.sut.total_backoff_seconds, 22)

    def test_retryAfterIsHonored(self):
        self.transport.side_effect = [self.httpError(429, "12"), self.searchResponse()]
        self.assertEqual(self.sut.searchForSeries(["Series"]), 123)
        self.assertEqual(self.sleeps, [12])
        self.assertEqual(self.sut.total_backoff_seconds, 12)

    def test_retryAfterSupportsHttpDateAndInvalidValues(self):
        date = format_datetime(
            datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True
        )
        self.assertGreater(self.sut._retryAfter(date), 28)
        self.assertLessEqual(self.sut._retryAfter(date), 30)
        self.assertIsNone(self.sut._retryAfter("invalid"))
        self.assertEqual(self.sut._retryAfter("-1"), 0)

    def test_searchAbortsWhenCumulativeBackoffWouldExceedTenMinutes(self):
        self.transport.side_effect = [self.httpError(429) for _ in range(9)]
        with self.assertRaisesRegex(RuntimeError, "10-minute limit"):
            self.sut.searchForSeries(["Series"])
        self.assertEqual(self.sleeps, [2, 4, 8, 16, 32, 64, 128, 256])
        self.sut.resetBackoffBudget()
        self.assertEqual(self.sut.total_backoff_seconds, 0)

    def test_excessiveRetryAfterAbortsWithoutSleeping(self):
        self.transport.side_effect = self.httpError(429, "601")
        with self.assertRaisesRegex(RuntimeError, "10-minute limit"):
            self.sut.getLatestChapterForId(123)
        self.assertEqual(self.sleeps, [])

    def test_transientFailuresAreRetriedWithBoundedAttempts(self):
        for error in (
            self.httpError(503), urllib.error.URLError("connection failed"), TimeoutError()
        ):
            with self.subTest(error=error):
                self.setUp()
                self.transport.side_effect = error
                with self.assertRaises(type(error)):
                    self.sut.getLatestChapterForId(123)
                self.assertEqual(self.transport.call_count, 4)
                self.assertEqual(self.sleeps, [2, 4, 8])

    def test_serverRetryAfterAndSuccessfulRetry(self):
        self.transport.side_effect = [
            self.httpError(503, "10"), self.response({"latest_chapter": 42}),
        ]
        self.assertEqual(self.sut.getLatestChapterForId(123), 42)
        self.assertEqual(self.sleeps, [10])

    def test_permanentHttpErrorsAreNotRetried(self):
        for code in (400, 401, 403, 404):
            with self.subTest(code=code):
                self.transport.reset_mock()
                self.transport.side_effect = self.httpError(code)
                with self.assertRaises(urllib.error.HTTPError):
                    self.sut.getLatestChapterForId(123)
                self.assertEqual(self.transport.call_count, 1)

    def test_invalidJsonAndNonObjectAreNotRetried(self):
        for body in (b"not json", b"[]"):
            with self.subTest(body=body):
                self.transport.reset_mock()
                self.transport.return_value = io.BytesIO(body)
                with self.assertRaises(ValueError):
                    self.sut.getLatestChapterForId(123)
                self.assertEqual(self.transport.call_count, 1)

    def test_searchAndChapterSharePacingAndCache(self):
        self.transport.side_effect = [
            self.searchResponse(), self.response({"latest_chapter": 42}),
            self.response({"latest_chapter": 43}),
        ]
        self.assertEqual(self.sut.searchForSeries(["Series"]), 123)
        self.assertEqual(self.sut.getLatestChapterForId(123), 42)
        self.assertEqual(self.sleeps, [2])
        self.assertEqual(self.sut.getLatestChapterForId(123), 42)
        self.assertEqual(self.sut.searchForSeries(["Series"]), 123)
        self.assertEqual(self.transport.call_count, 2)
        self.now += 301
        self.assertEqual(self.sut.getLatestChapterForId(123), 43)
        self.assertEqual(self.transport.call_count, 3)

    def test_budgetIsSharedAcrossSearchAndChapterRequests(self):
        self.sut.total_backoff_seconds = 599
        self.transport.side_effect = self.httpError(429)
        with self.assertRaisesRegex(RuntimeError, "10-minute limit"):
            self.sut.getLatestChapterForId(123)
