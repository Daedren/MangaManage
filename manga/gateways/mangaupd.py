import json
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from urllib.parse import urlsplit

from cross.decorators import Logger


API_BASE_URL = "https://api.mangaupdates.com/v1"
DEFAULT_REQUEST_DELAY_SECONDS = 2
MAX_TOTAL_BACKOFF_SECONDS = 10 * 60
REQUEST_TIMEOUT_SECONDS = 30
MAX_TRANSIENT_RETRIES = 3
CACHE_TTL_SECONDS = 5 * 60


@Logger
class MangaUpdatesGateway:
    def __init__(self, transport=None, clock=None, sleep=None):
        self.request_delay_seconds = DEFAULT_REQUEST_DELAY_SECONDS
        self.total_backoff_seconds = 0
        self._transport = transport or urllib.request.urlopen
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._last_request_at = None
        self._cache = {}
        # CLI tasks and direct API requests share this gateway and its pacing.
        self._lock = threading.RLock()

    def resetBackoffBudget(self):
        with self._lock:
            self.total_backoff_seconds = 0

    def searchForSeries(self, names: List[str]) -> Optional[int]:
        names = [name.strip() for name in names if name and name.strip()]
        if not names:
            return None
        name = self.__getMostSearchableTitle(names)
        response = self._request("/series/search", {
            "search": name, "stype": "title", "orderby": "score",
            "page": 1, "perpage": 20,
        })
        results = response.get("results")
        if not isinstance(results, list):
            raise ValueError("MangaUpdates search response has no valid results list")
        has_candidates = False
        normalized_names = {self._normalizeTitle(title) for title in names}
        for result in results:
            if (not isinstance(result, dict)
                    or not isinstance(result.get("record"), dict)):
                raise ValueError("Invalid MangaUpdates search record")
            record = result["record"]
            if record.get("type") == "Novel":
                continue
            series_id = record.get("series_id")
            if type(series_id) is not int or series_id <= 0:
                raise ValueError("Invalid MangaUpdates series ID")
            has_candidates = True
            titles = [record.get("title"), result.get("hit_title")]
            if any(
                isinstance(title, str)
                and self._normalizeTitle(title) in normalized_names
                for title in titles
            ):
                self.logger.debug("Matched %s to MangaUpdates ID %s", name, series_id)
                return series_id
        if has_candidates:
            self.logger.warning("No exact MangaUpdates title match for %s", name)
        return None

    def getLatestChapterForId(self, series_id: int) -> Optional[int]:
        latest_chapter, _ = self.getSeriesDetailsForId(series_id)
        return latest_chapter

    def getSeriesDetailsForId(self, series_id: int) -> tuple[Optional[int], Optional[str]]:
        if type(series_id) is not int or series_id <= 0:
            raise ValueError("MangaUpdates series ID must be a positive integer")
        response = self._request(f"/series/{series_id}")
        chapter = response.get("latest_chapter")
        if chapter is not None and (type(chapter) is not int or chapter < 0):
            raise ValueError("Invalid MangaUpdates latest_chapter value")
        url = response.get("url")
        if url is not None:
            parsed_url = urlsplit(url) if isinstance(url, str) else None
            if (parsed_url is None or parsed_url.scheme != "https"
                    or parsed_url.netloc != "www.mangaupdates.com"
                    or not parsed_url.path.startswith("/series/")
                    or parsed_url.query or parsed_url.fragment):
                raise ValueError("Invalid MangaUpdates series URL")
        return chapter, url

    def _request(self, path, payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        key = (path, body)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and self._clock() - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]
            # Expire old responses rather than growing the cache indefinitely.
            self._cache = {key: value for key, value in self._cache.items()
                           if self._clock() - value[0] < CACHE_TTL_SECONDS}
            request = urllib.request.Request(
                API_BASE_URL + path, data=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "MangaManage/1.0",
                },
                method="POST" if payload is not None else "GET",
            )
            retry_delay = self.request_delay_seconds
            transient_retries = 0
            while True:
                self._paceRequest()
                try:
                    with self._transport(
                        request, timeout=REQUEST_TIMEOUT_SECONDS
                    ) as result:
                        response = json.loads(result.read())
                    if not isinstance(response, dict):
                        raise ValueError(
                            "MangaUpdates returned a non-object JSON response"
                        )
                    self._cache[key] = (self._clock(), response)
                    return response
                except urllib.error.HTTPError as error:
                    if error.code != 429 and not 500 <= error.code < 600:
                        error.close()
                        raise
                    rate_limited = error.code == 429
                    delay = self._retryAfter(error.headers.get("Retry-After"))
                    error.close()
                    if not rate_limited:
                        transient_retries += 1
                        if transient_retries > MAX_TRANSIENT_RETRIES:
                            raise
                    self._backoff(max(retry_delay, delay or 0), error)
                    if rate_limited:
                        self.request_delay_seconds = max(
                            self.request_delay_seconds, retry_delay
                        )
                except (urllib.error.URLError, TimeoutError) as error:
                    transient_retries += 1
                    if transient_retries > MAX_TRANSIENT_RETRIES:
                        raise
                    self._backoff(retry_delay, error)
                retry_delay *= 2

    def _paceRequest(self):
        if self._last_request_at is not None:
            elapsed = self._clock() - self._last_request_at
            remaining = self.request_delay_seconds - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._clock()

    def _backoff(self, delay, error):
        if self.total_backoff_seconds + delay > MAX_TOTAL_BACKOFF_SECONDS:
            raise RuntimeError(
                "MangaUpdates retry backoff exceeded the 10-minute limit"
            ) from error
        self.total_backoff_seconds += delay
        self.logger.warning("MangaUpdates request failed (%s); retrying in %s seconds",
                            error, delay)
        self._sleep(delay)

    @staticmethod
    def _retryAfter(value):
        if not value:
            return None
        try:
            return max(0, int(value))
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                return max(0, (date - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    @staticmethod
    def _normalizeTitle(title):
        return " ".join(unicodedata.normalize("NFKC", title).casefold().split())

    def __getMostSearchableTitle(self, titles: List[str]):
        return max(titles, key=lambda s: sum(c.isascii() for c in s))
