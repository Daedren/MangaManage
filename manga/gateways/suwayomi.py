import base64
import json
import logging
import math
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Optional
from urllib.parse import urlsplit


CACHE_TTL_SECONDS = 5 * 60
FAILURE_RETRY_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 10
PAGE_SIZE = 100
MAX_PAGES = 1000
TITLE_CACHE_SIZE = 256
DOWNLOAD_REQUEST_TIMEOUT_SECONDS = 60

# fetchChapters is supported by older Suwayomi versions as well as current ones.
FETCH_CHAPTERS_MUTATION = """
mutation GapChapters($mangaId: Int!) {
  fetchChapters(input: { mangaId: $mangaId }) {
    chapters { id chapterNumber isDownloaded }
  }
}
"""

DOWNLOAD_QUEUE_QUERY = """
query GapDownloadQueue {
  downloadStatus { queue { chapter { id } } }
}
"""

ENQUEUE_CHAPTERS_MUTATION = """
mutation DownloadGap($ids: [Int!]!) {
  enqueueChapterDownloads(input: { ids: $ids }) {
    downloadStatus { state }
  }
}
"""


LIBRARY_QUERY = """
query LibrarySources($first: Int!, $offset: Int!) {
  mangas(filter: { inLibrary: { equalTo: true } }, first: $first, offset: $offset,
         order: [{ by: ID, byType: ASC }]) {
    nodes {
      id
      source { name displayName }
      trackRecords { nodes { remoteId tracker { name } } }
    }
    pageInfo { hasNextPage }
  }
}
"""

TITLE_QUERY = """
query MangaTrackingByTitle($title: String!, $first: Int!, $offset: Int!) {
  mangas(filter: { title: { likeInsensitive: $title } }, first: $first, offset: $offset,
         order: [{ by: ID, byType: ASC }]) {
    nodes {
      id
      title
      trackRecords { nodes { remoteId tracker { name } } }
    }
    pageInfo { hasNextPage }
  }
}
"""


class SuwayomiDownloadError(Exception):
    """A safe, user-facing failure message without upstream credentials or URLs."""


class SuwayomiGateway:
    """Suwayomi library lookups and explicit, on-demand gap downloads."""

    def __init__(self, base_url="", web_url="", username="", password="",
                 token="", transport=None, clock=None):
        self.base_url = base_url.strip().rstrip("/")
        self.web_url = web_url.strip().rstrip("/") or self.base_url
        for url in (self.base_url, self.web_url):
            if url:
                parts = urlsplit(url)
                if (parts.scheme not in ("http", "https") or not parts.netloc
                        or parts.username or parts.password or parts.query or parts.fragment):
                    raise ValueError("Suwayomi URLs must be HTTP(S) base URLs without credentials, query or fragment")
        self._headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token.strip()}"
        elif username:
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            self._headers["Authorization"] = f"Basic {credentials}"
        self._transport = transport or urllib.request.urlopen
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._download_lock = threading.Lock()
        self._snapshot = {}
        self._next_refresh = 0
        self._error = None
        self._has_snapshot = False
        self._title_cache = OrderedDict()
        self._title_retry_at = 0

    def queueGapDownloads(self, anilist_id: int, lower: float, upper: float):
        """Refresh linked sources and enqueue one copy per number inside the gap.

        Serialize actions so simultaneous/repeated clicks see the updated queue.
        Never start the global downloader or modify tracking/quarantine state.
        """
        if not self.base_url:
            raise SuwayomiDownloadError("Suwayomi is not configured. Configure it in settings.ini first.")
        if (not math.isfinite(lower) or not math.isfinite(upper)
                or lower < 0 or lower >= upper):
            raise ValueError("Invalid chapter gap")
        with self._download_lock:
            try:
                # A mutating action must not trust stale library/tracking matches.
                with self._lock:
                    sources = self._loadLibrary().get(anilist_id, [])
                return self._queueGapFromSources(sources, lower, upper)
            except SuwayomiDownloadError:
                raise
            except Exception as error:
                self._logDownloadFailure(error)
                raise SuwayomiDownloadError(
                    "Unable to check Suwayomi chapters or its download queue. "
                    "Check the connection and credentials, then try again."
                ) from None

    def _queueGapFromSources(self, sources, lower, upper):
        result = {
            "status": "no_source", "queued_chapters": [],
            "already_downloaded": [], "already_queued": [], "warnings": [],
        }
        if not sources:
            return result
        chapters = []
        successful_sources = 0
        for source in sorted(sources, key=lambda item: item["manga_id"]):
            try:
                data = self._downloadGraphql(FETCH_CHAPTERS_MUTATION, {"mangaId": source["manga_id"]})
                nodes = data["fetchChapters"]["chapters"]
                if not isinstance(nodes, list):
                    raise ValueError("Invalid chapter list")
                seen = set()
                for chapter in nodes:
                    self._validateDownloadChapter(chapter)
                    if chapter["id"] in seen:
                        raise ValueError("Repeated chapter ID")
                    seen.add(chapter["id"])
                # Validate the whole source before using any of its results.
                chapters.extend(sorted(nodes, key=lambda item: item["id"]))
                successful_sources += 1
            except Exception as error:
                self._logDownloadFailure(error)
                result["warnings"].append(
                    f"Could not refresh chapters from {source['name']}; other sources were checked."
                )
        if not successful_sources:
            raise SuwayomiDownloadError(
                "Unable to refresh chapters from any linked Suwayomi source. "
                "Check the sources in Suwayomi, then try again."
            )
        candidates = [chapter for chapter in chapters if lower < chapter["chapterNumber"] < upper]
        if not candidates:
            result["status"] = "no_matches"
            return result
        data = self._downloadGraphql(DOWNLOAD_QUEUE_QUERY, {})
        queue = data["downloadStatus"]["queue"]
        if not isinstance(queue, list):
            raise ValueError("Invalid download queue")
        queued_ids = set()
        for item in queue:
            chapter_id = item["chapter"]["id"]
            if type(chapter_id) is not int or chapter_id < 0:
                raise ValueError("Invalid queued chapter ID")
            queued_ids.add(chapter_id)
        downloaded_numbers = {item["chapterNumber"] for item in candidates if item["isDownloaded"]}
        queued_numbers = {item["chapterNumber"] for item in candidates if item["id"] in queued_ids}
        selected = {}
        for chapter in candidates:
            number = chapter["chapterNumber"]
            if number not in downloaded_numbers and number not in queued_numbers:
                selected.setdefault(number, chapter["id"])
        result["already_downloaded"] = sorted(downloaded_numbers)
        result["already_queued"] = sorted(queued_numbers - downloaded_numbers)
        if not selected:
            result["status"] = "already_available"
            return result
        numbers = sorted(selected)
        try:
            data = self._downloadGraphql(ENQUEUE_CHAPTERS_MUTATION, {"ids": [selected[n] for n in numbers]})
            if data["enqueueChapterDownloads"]["downloadStatus"]["state"] not in ("STARTED", "STOPPED"):
                raise ValueError("Invalid enqueue response")
        except Exception as error:
            self._logDownloadFailure(error)
            # Do not blindly retry mutations: a timed-out request may have succeeded.
            raise SuwayomiDownloadError(
                "Suwayomi did not confirm the download request. Chapters may already be queued; "
                "check its download queue before trying again."
            ) from None
        result["status"] = "queued"
        result["queued_chapters"] = numbers
        return result

    @staticmethod
    def _validateDownloadChapter(chapter):
        if (type(chapter["id"]) is not int or chapter["id"] < 0
                or type(chapter["chapterNumber"]) not in (int, float)
                or not math.isfinite(chapter["chapterNumber"])
                or type(chapter["isDownloaded"]) is not bool):
            raise ValueError("Invalid Suwayomi chapter")

    @staticmethod
    def _logDownloadFailure(error):
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        logging.getLogger(__name__).warning("Suwayomi gap-download request failed")

    def _downloadGraphql(self, query, variables):
        request = urllib.request.Request(
            self.base_url + "/api/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers=self._headers, method="POST",
        )
        with self._transport(request, timeout=DOWNLOAD_REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
        if (not isinstance(payload, dict) or payload.get("errors")
                or not isinstance(payload.get("data"), dict)):
            raise ValueError("Invalid Suwayomi GraphQL response")
        return payload["data"]

    def getAnilistIdForSeries(self, series: str) -> Optional[str]:
        """Resolve only unambiguous normalized titles; failures allow AniList fallback."""
        title = " ".join(series.split()).casefold()
        if not self.base_url or not title:
            return None
        with self._lock:
            now = self._clock()
            cached = self._title_cache.get(title)
            if cached is not None and now < cached[0]:
                self._title_cache.move_to_end(title)
                return cached[1]
            if now < self._title_retry_at:
                return None
            try:
                result = self._loadAnilistIdForTitle(title)
            except Exception as error:
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                logging.getLogger(__name__).warning(
                    "Suwayomi title lookup failed; falling back to AniList"
                )
                self._title_retry_at = self._clock() + FAILURE_RETRY_SECONDS
                return None
            self._title_retry_at = 0
            self._title_cache[title] = (self._clock() + CACHE_TTL_SECONDS, result)
            self._title_cache.move_to_end(title)
            while len(self._title_cache) > TITLE_CACHE_SIZE:
                self._title_cache.popitem(last=False)
            return result

    def _loadAnilistIdForTitle(self, title):
        anilist_ids = set()
        seen_ids = set()
        offset = 0
        # Wildcards between words tolerate whitespace differences upstream. The
        # normalized exact comparison below rejects all broader SQL LIKE matches.
        pattern = "%" + "%".join(title.split()) + "%"
        for _ in range(MAX_PAGES):
            request = urllib.request.Request(
                self.base_url + "/api/graphql",
                data=json.dumps({"query": TITLE_QUERY, "variables": {
                    "title": pattern, "first": PAGE_SIZE, "offset": offset,
                }}).encode(),
                headers=self._headers, method="POST",
            )
            with self._transport(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read())
            if not isinstance(payload, dict) or payload.get("errors"):
                raise ValueError("Invalid Suwayomi GraphQL response")
            page = payload["data"]["mangas"]
            nodes = page["nodes"]
            has_next = page["pageInfo"]["hasNextPage"]
            if not isinstance(nodes, list) or type(has_next) is not bool or (has_next and not nodes):
                raise ValueError("Invalid Suwayomi pagination")
            for manga in nodes:
                manga_id = manga["id"]
                if type(manga_id) is not int or manga_id < 0 or manga_id in seen_ids:
                    raise ValueError("Invalid or repeated Suwayomi manga ID")
                seen_ids.add(manga_id)
                candidate_title = manga["title"]
                if not isinstance(candidate_title, str) or not candidate_title.strip():
                    raise ValueError("Invalid Suwayomi manga title")
                if " ".join(candidate_title.split()).casefold() != title:
                    continue
                records = manga["trackRecords"]["nodes"]
                if not isinstance(records, list):
                    raise ValueError("Invalid Suwayomi tracking records")
                for record in records:
                    if record["tracker"]["name"].casefold() != "anilist":
                        continue
                    remote_id = record["remoteId"]
                    if (type(remote_id) not in (str, int)
                            or not str(remote_id).isascii() or not str(remote_id).isdigit()
                            or int(remote_id) <= 0):
                        raise ValueError("Invalid AniList media ID")
                    anilist_ids.add(str(int(remote_id)))
            if not has_next:
                if len(anilist_ids) == 1:
                    return anilist_ids.pop()
                logging.getLogger(__name__).info(
                    "Suwayomi title lookup found no unique AniList ID; falling back to AniList"
                )
                return None
            offset += len(nodes)
        raise ValueError("Suwayomi title lookup exceeded pagination limit")

    def getLibrarySources(self):
        """Return (sources by AniList ID, warning); never replace a cache with partial data."""
        if not self.base_url:
            return {}, "Suwayomi is not configured."
        with self._lock:
            if self._clock() < self._next_refresh:
                return self._snapshot, self._error
            try:
                snapshot = self._loadLibrary()
            except Exception as error:
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                # Do not expose upstream errors, URLs or credentials in API responses/logs.
                logging.getLogger(__name__).warning("Unable to refresh Suwayomi library sources")
                self._error = (
                    "Suwayomi is unavailable; showing cached sources."
                    if self._has_snapshot else "Suwayomi sources are unavailable."
                )
                self._next_refresh = self._clock() + FAILURE_RETRY_SECONDS
            else:
                self._snapshot = snapshot
                self._has_snapshot = True
                self._error = None
                self._next_refresh = self._clock() + CACHE_TTL_SECONDS
            return self._snapshot, self._error

    def _loadLibrary(self):
        sources = {}
        seen_ids = set()
        offset = 0
        for _ in range(MAX_PAGES):
            request = urllib.request.Request(
                self.base_url + "/api/graphql",
                data=json.dumps({"query": LIBRARY_QUERY,
                                 "variables": {"first": PAGE_SIZE, "offset": offset}}).encode(),
                headers=self._headers, method="POST",
            )
            with self._transport(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read())
            if not isinstance(payload, dict) or payload.get("errors"):
                raise ValueError("Invalid Suwayomi GraphQL response")
            page = payload["data"]["mangas"]
            nodes = page["nodes"]
            has_next = page["pageInfo"]["hasNextPage"]
            if not isinstance(nodes, list) or type(has_next) is not bool or (has_next and not nodes):
                raise ValueError("Invalid Suwayomi pagination")
            for manga in nodes:
                manga_id = manga["id"]
                if type(manga_id) is not int or manga_id < 0 or manga_id in seen_ids:
                    raise ValueError("Invalid or repeated Suwayomi manga ID")
                seen_ids.add(manga_id)
                source = manga["source"]
                records = manga["trackRecords"]["nodes"]
                if not isinstance(records, list):
                    raise ValueError("Invalid Suwayomi tracking records")
                if source is None:
                    continue
                name = source.get("displayName") or source.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Invalid Suwayomi source name")
                link = {"manga_id": manga_id, "name": name,
                        "url": f"{self.web_url}/manga/{manga_id}"}
                for record in records:
                    if record["tracker"]["name"].casefold() != "anilist":
                        continue
                    remote_id = record["remoteId"]
                    if not isinstance(remote_id, (str, int)) or isinstance(remote_id, bool):
                        raise ValueError("Invalid AniList media ID")
                    anilist_id = int(remote_id)
                    if anilist_id <= 0:
                        raise ValueError("Invalid AniList media ID")
                    matches = sources.setdefault(anilist_id, [])
                    if link not in matches:
                        matches.append(link)
            if not has_next:
                return sources
            offset += len(nodes)
        raise ValueError("Suwayomi library exceeded pagination limit")
