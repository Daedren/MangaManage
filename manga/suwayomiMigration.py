"""Single-entry migration using the same GraphQL operations as Suwayomi's WebUI.

No downloaded files, AniList progress or MangaManage state are changed.
Upstream mutations are not transactional: copy and verify before any cleanup.
"""
import hashlib
import hmac
import json
import logging
import math
import re
import secrets
import urllib.error
from collections import OrderedDict


PAGE_SIZE = 100
MAX_PAGES = 1000
PREVIEW_TTL = 600
REQUIRED_MUTATIONS = {
    "fetchSourceManga", "fetchMangaAndChapters", "updateManga",
    "updateChapters", "updateMangaCategories", "bindTrackRecord", "unbindTrack",
}

SOURCES_QUERY = """
query MigrationSources {
  __schema { mutationType { fields { name } } }
  sources { nodes { id name displayName lang } }
}
"""
MANGA_QUERY = """
query MigrationManga($id: Int!) {
  manga(id: $id) {
    id title sourceId inLibrary source { name displayName }
    categories { nodes { id } totalCount }
    trackRecords {
      nodes { id remoteId trackerId tracker { name } }
      totalCount
    }
  }
}
"""
CHAPTERS_QUERY = """
query MigrationChapters($id: Int!, $first: Int!, $offset: Int!) {
  chapters(filter: { mangaId: { equalTo: $id } }, first: $first, offset: $offset,
           order: [{ by: ID, byType: ASC }]) {
    nodes { id chapterNumber isRead isBookmarked isDownloaded manga { id } }
    totalCount pageInfo { hasNextPage }
  }
}
"""
SEARCH_MUTATION = """
mutation MigrationSearch($input: FetchSourceMangaInput!) {
  fetchSourceManga(input: $input) {
    hasNextPage mangas { id title sourceId inLibrary }
  }
}
"""
FETCH_MUTATION = """
mutation MigrationFetch($id: Int!, $chapters: Boolean!) {
  fetchMangaAndChapters(input: { id: $id, fetchManga: true, fetchChapters: $chapters }) {
    manga { id }
  }
}
"""
LIBRARY_MUTATION = """
mutation MigrationLibrary($id: Int!, $inLibrary: Boolean!) {
  updateManga(input: { id: $id, patch: { inLibrary: $inLibrary } }) {
    manga { id inLibrary }
  }
}
"""
CATEGORY_MUTATION = """
mutation MigrationCategories($id: Int!, $categories: [Int!]!) {
  updateMangaCategories(input: { id: $id, patch: { addToCategories: $categories } }) {
    manga { id }
  }
}
"""
CHAPTER_MUTATION = """
mutation MigrationChapterState($input: UpdateChaptersInput!) {
  updateChapters(input: $input) { chapters { id } }
}
"""
BIND_MUTATION = """
mutation MigrationBind($id: Int!, $recordId: Int!) {
  bindTrackRecord(input: { mangaId: $id, trackRecordId: $recordId }) {
    trackRecord { id remoteId trackerId manga { id } }
  }
}
"""
UNBIND_MUTATION = """
mutation MigrationUnbind($recordId: Int!) {
  unbindTrack(input: { recordId: $recordId, deleteRemoteTrack: false }) {
    clientMutationId
  }
}
"""


class SuwayomiMigrationError(Exception):
    """A safe message and HTTP status; never includes an upstream exception."""

    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


def _id(value):
    if type(value) is not int or value < 0:
        raise ValueError("Invalid ID")
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Invalid text")
    return value


def _source_id(value):
    # LongString must never travel through a JavaScript number.
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ValueError("Invalid source ID")
    return value


class SuwayomiMigration:
    def __init__(self, gateway):
        self.gateway = gateway
        self._secret = secrets.token_bytes(32)
        self._used_previews = OrderedDict()

    def _request(self, query, variables):
        if not self.gateway.base_url:
            raise SuwayomiMigrationError("Suwayomi is not configured. Configure it in settings.ini first.")
        try:
            return self.gateway._downloadGraphql(query, variables)
        except SuwayomiMigrationError:
            raise
        except Exception as error:
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            logging.getLogger(__name__).warning("Suwayomi migration request failed")
            raise SuwayomiMigrationError(
                "Suwayomi could not confirm this request. Check its connection, credentials, "
                "source availability and migration permissions/version."
            ) from None

    def sources(self):
        data = self._request(SOURCES_QUERY, {})
        available = {item["name"] for item in data["__schema"]["mutationType"]["fields"]}
        if not REQUIRED_MUTATIONS <= available:
            raise SuwayomiMigrationError(
                "This Suwayomi version does not support the required migration operations. Update Suwayomi first."
            )
        nodes = data["sources"]["nodes"]
        if not isinstance(nodes, list):
            raise ValueError("Invalid sources")
        sources = [{"id": _source_id(item["id"]),
                    "name": _text(item.get("displayName") or item["name"]),
                    "language": _text(item["lang"])} for item in nodes]
        if len({item["id"] for item in sources}) != len(sources):
            raise ValueError("Duplicate sources")
        return sorted(sources, key=lambda item: (item["name"].casefold(), item["language"], item["id"]))

    def _manga(self, manga_id, chapters=False):
        manga = self._request(MANGA_QUERY, {"id": manga_id})["manga"]
        if manga is None:
            raise SuwayomiMigrationError("This manga is no longer available in Suwayomi. Refresh its details.", 409)
        if _id(manga["id"]) != manga_id or type(manga["inLibrary"]) is not bool:
            raise ValueError("Invalid manga")
        _text(manga["title"])
        _source_id(manga["sourceId"])
        _text(manga["source"].get("displayName") or manga["source"]["name"])
        for field in ("categories", "trackRecords"):
            nodes = manga[field]["nodes"]
            if (not isinstance(nodes, list) or type(manga[field]["totalCount"]) is not int
                    or len(nodes) != manga[field]["totalCount"]):
                raise ValueError("Incomplete migration data")
            ids = [_id(node["id"]) for node in nodes]
            if len(set(ids)) != len(ids):
                raise ValueError("Duplicate migration IDs")
            manga[field]["nodes"] = sorted(nodes, key=lambda node: node["id"])
        for record in manga["trackRecords"]["nodes"]:
            _id(record["trackerId"])
            _text(record["tracker"]["name"])
            remote = record["remoteId"]
            if type(remote) not in (str, int) or not str(remote).isascii() or not str(remote).isdigit():
                raise ValueError("Invalid remote tracker ID")
            record["remoteId"] = str(remote)
        tracker_ids = [item["trackerId"] for item in manga["trackRecords"]["nodes"]]
        if len(tracker_ids) != len(set(tracker_ids)):
            raise ValueError("Duplicate trackers")
        manga["chapters"] = self._chapters(manga_id) if chapters else []
        return manga

    def _chapters(self, manga_id):
        chapters, seen, total = [], set(), None
        for _ in range(MAX_PAGES):
            page = self._request(CHAPTERS_QUERY, {
                "id": manga_id, "first": PAGE_SIZE, "offset": len(chapters),
            })["chapters"]
            nodes, has_next = page["nodes"], page["pageInfo"]["hasNextPage"]
            if (not isinstance(nodes, list) or type(has_next) is not bool
                    or type(page["totalCount"]) is not int or page["totalCount"] < 0
                    or (has_next and not nodes)):
                raise ValueError("Invalid chapter pagination")
            if total is not None and total != page["totalCount"]:
                raise SuwayomiMigrationError("The chapter list changed. Review a fresh migration preview.", 409)
            total = page["totalCount"]
            for chapter in nodes:
                chapter_id = _id(chapter["id"])
                if (chapter_id in seen or _id(chapter["manga"]["id"]) != manga_id
                        or type(chapter["chapterNumber"]) not in (int, float)
                        or not math.isfinite(chapter["chapterNumber"])
                        or any(type(chapter[field]) is not bool for field in ("isRead", "isBookmarked", "isDownloaded"))):
                    raise ValueError("Invalid chapter state")
                seen.add(chapter_id)
                chapters.append(chapter)
            if not has_next:
                if len(chapters) != total:
                    raise ValueError("Incomplete chapters")
                return sorted(chapters, key=lambda item: item["id"])
        raise ValueError("Chapter pagination exceeded limit")

    def _original(self, anilist_id, original_id, chapters=False):
        manga = self._manga(original_id, chapters)
        links = [record for record in manga["trackRecords"]["nodes"]
                 if record["tracker"]["name"].casefold() == "anilist"]
        if not manga["inLibrary"] or len(links) != 1 or links[0]["remoteId"] != str(anilist_id):
            raise SuwayomiMigrationError(
                "The original manga is no longer an AniList-linked library entry for this series. Refresh the series list.", 409
            )
        return manga

    def context(self, anilist_id, original_id):
        with self.gateway._download_lock:
            original = self._original(anilist_id, original_id)
            return {"original": self._summary(original),
                    "sources": [source for source in self.sources() if source["id"] != original["sourceId"]]}

    def search(self, anilist_id, original_id, source_id, query, page):
        with self.gateway._download_lock:
            original = self._original(anilist_id, original_id)
            if source_id == original["sourceId"] or source_id not in {source["id"] for source in self.sources()}:
                raise SuwayomiMigrationError("Choose another installed Suwayomi source.", 409)
            data = self._request(SEARCH_MUTATION, {"input": {
                "source": source_id, "type": "SEARCH", "query": query.strip(), "page": page,
            }})["fetchSourceManga"]
            if type(data["hasNextPage"]) is not bool or not isinstance(data["mangas"], list):
                raise ValueError("Invalid search results")
            results = []
            seen = set()
            for item in data["mangas"]:
                manga_id = _id(item["id"])
                if (_source_id(item["sourceId"]) != source_id or manga_id in seen
                        or type(item["inLibrary"]) is not bool):
                    raise ValueError("Invalid search manga")
                seen.add(manga_id)
                results.append({"manga_id": manga_id, "title": _text(item["title"]),
                                "in_library": item["inLibrary"], "url": self._url(manga_id)})
            return {"results": results, "has_next_page": data["hasNextPage"], "page": page}

    def _prepare(self, anilist_id, original_id, destination_id, options):
        if original_id == destination_id:
            raise SuwayomiMigrationError("A manga cannot be migrated to itself.", 409)
        original = self._original(anilist_id, original_id, options["migrate_chapters"])
        destination = self._manga(destination_id)
        if original["sourceId"] == destination["sourceId"]:
            raise SuwayomiMigrationError("Choose a manga on a different source.", 409)
        if destination["sourceId"] not in {source["id"] for source in self.sources()}:
            raise SuwayomiMigrationError("The destination source is no longer installed.", 409)
        fetched = self._request(FETCH_MUTATION, {"id": destination_id, "chapters": options["migrate_chapters"]})
        if _id(fetched["fetchMangaAndChapters"]["manga"]["id"]) != destination_id:
            raise ValueError("Destination refresh was not confirmed")
        destination = self._manga(destination_id, options["migrate_chapters"])
        if original["sourceId"] == destination["sourceId"]:
            raise SuwayomiMigrationError("Choose a manga on a different source.", 409)
        self._check_trackers(original, destination)
        return original, destination, self._transfers(original, destination, options)

    @staticmethod
    def _check_trackers(original, destination):
        records = {record["trackerId"]: record["remoteId"] for record in original["trackRecords"]["nodes"]}
        for record in destination["trackRecords"]["nodes"]:
            # Reject unrelated trackers as well as differing bindings: a different
            # AniList link must never make this entry appear under two series.
            if records.get(record["trackerId"]) != record["remoteId"]:
                raise SuwayomiMigrationError(
                    "The destination has conflicting tracking records. Resolve them in Suwayomi before migrating.", 409
                )

    @staticmethod
    def _transfers(original, destination, options):
        read, bookmarked, unmatched = [], [], []
        if options["migrate_chapters"]:
            highest_read = max((c["chapterNumber"] for c in original["chapters"] if c["isRead"]), default=None)
            if highest_read is not None:
                read = [c["id"] for c in destination["chapters"]
                        if c["chapterNumber"] <= highest_read and not c["isRead"]]
            # Like the WebUI, choose one matching destination per bookmarked
            # number. Lowest chapter ID makes duplicate handling deterministic.
            first_by_number = {}
            for chapter in destination["chapters"]:
                first_by_number.setdefault(chapter["chapterNumber"], chapter)
            for number in sorted({c["chapterNumber"] for c in original["chapters"] if c["isBookmarked"]}):
                match = first_by_number.get(number)
                if match is None:
                    unmatched.append(number)
                elif not match["isBookmarked"]:
                    bookmarked.append(match["id"])
        existing_categories = {c["id"] for c in destination["categories"]["nodes"]}
        categories = ([c["id"] for c in original["categories"]["nodes"] if c["id"] not in existing_categories]
                      if options["migrate_categories"] else [])
        existing_trackers = {r["trackerId"] for r in destination["trackRecords"]["nodes"]}
        records = [r["id"] for r in original["trackRecords"]["nodes"] if r["trackerId"] not in existing_trackers]
        return {"read": sorted(read), "bookmarked": sorted(bookmarked), "categories": categories,
                "records": records, "unmatched_bookmarks": unmatched}

    def _url(self, manga_id):
        return f"{self.gateway.web_url}/manga/{manga_id}"

    def _summary(self, manga):
        return {"manga_id": manga["id"], "title": manga["title"], "source_id": manga["sourceId"],
                "source_name": manga["source"].get("displayName") or manga["source"]["name"],
                "in_library": manga["inLibrary"], "url": self._url(manga["id"])}

    def _signature(self, expires, nonce, anilist_id, original, destination, options):
        payload = json.dumps(
            [expires, nonce, anilist_id, original, destination, options],
            sort_keys=True, separators=(",", ":"),
        )
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()

    def preview(self, anilist_id, original_id, destination_id, options):
        with self.gateway._download_lock:
            original, destination, transfers = self._prepare(anilist_id, original_id, destination_id, options)
            expires = int(self.gateway._clock()) + PREVIEW_TTL
            nonce = secrets.token_hex(8)
            signature = self._signature(
                expires, nonce, anilist_id, original, destination, options,
            )
            return {"original": self._summary(original), "destination": self._summary(destination),
                    "read_chapters": len(transfers["read"]), "bookmarked_chapters": len(transfers["bookmarked"]),
                    "categories": len(transfers["categories"]), "tracking_records": len(original["trackRecords"]["nodes"]),
                    "unmatched_bookmarks": transfers["unmatched_bookmarks"],
                    "preview_token": f"{expires}:{nonce}:{signature}"}

    def execute(self, anilist_id, original_id, destination_id, options, preview_token):
        with self.gateway._download_lock:
            match = re.fullmatch(r"([0-9]+):([0-9a-f]{16}):([0-9a-f]{64})", preview_token)
            if match is None:
                raise SuwayomiMigrationError("Review a fresh migration preview before confirming.", 409)
            expires_text, nonce, signature = match.groups()
            expires = int(expires_text)
            if expires <= self.gateway._clock() or preview_token in self._used_previews:
                raise SuwayomiMigrationError("This preview expired or was already submitted. Review a fresh preview.", 409)
            original, destination, transfers = self._prepare(anilist_id, original_id, destination_id, options)
            expected_signature = self._signature(
                expires, nonce, anilist_id, original, destination, options,
            )
            if not hmac.compare_digest(signature, expected_signature):
                raise SuwayomiMigrationError("The manga data or options changed. Review a fresh migration preview.", 409)
            self._used_previews[preview_token] = expires
            while len(self._used_previews) > 256:
                self._used_previews.popitem(last=False)
            result = {"status": "completed", "stage": "destination_library", "completed_steps": [],
                      "message": "Migration completed. Existing downloads and local archives were kept.",
                      "destination": self._summary(destination), "warnings": []}
            if transfers["unmatched_bookmarks"]:
                result["warnings"].append("Some bookmarks had no matching destination chapter and were not transferred.")
            cleanup_started = False
            try:
                if not destination["inLibrary"]:
                    data = self._request(LIBRARY_MUTATION, {"id": destination_id, "inLibrary": True})
                    if data["updateManga"]["manga"] != {"id": destination_id, "inLibrary": True}:
                        raise ValueError("Library update was not confirmed")
                result["completed_steps"].append("destination_library")
                result["stage"] = "chapter_state"
                for field, ids in (("isRead", transfers["read"]), ("isBookmarked", transfers["bookmarked"])):
                    for offset in range(0, len(ids), PAGE_SIZE):
                        batch = ids[offset:offset + PAGE_SIZE]
                        data = self._request(CHAPTER_MUTATION, {"input": {"ids": batch, "patch": {field: True}}})
                        if {item["id"] for item in data["updateChapters"]["chapters"]} != set(batch):
                            raise ValueError("Chapter update was not confirmed")
                result["completed_steps"].append("chapter_state")
                result["stage"] = "categories"
                if transfers["categories"]:
                    data = self._request(CATEGORY_MUTATION, {"id": destination_id, "categories": transfers["categories"]})
                    if data["updateMangaCategories"]["manga"]["id"] != destination_id:
                        raise ValueError("Category update was not confirmed")
                result["completed_steps"].append("categories")
                result["stage"] = "tracking"
                for record_id in transfers["records"]:
                    data = self._request(BIND_MUTATION, {"id": destination_id, "recordId": record_id})
                    if data["bindTrackRecord"]["trackRecord"]["manga"]["id"] != destination_id:
                        raise ValueError("Tracking copy was not confirmed")
                result["completed_steps"].append("tracking")
                result["stage"] = "verification"
                verified = self._manga(destination_id, options["migrate_chapters"])
                self._verify(original, destination, verified, transfers)
                # Another client can change the original while we copy. Keep it
                # intact if so; our lock only coordinates MangaManage actions.
                if self._manga(original_id, options["migrate_chapters"]) != original:
                    raise ValueError("Original changed during migration")
                result["completed_steps"].append("verification")
                result["stage"] = "original_library"
                cleanup_started = True
                data = self._request(LIBRARY_MUTATION, {"id": original_id, "inLibrary": False})
                if data["updateManga"]["manga"] != {"id": original_id, "inLibrary": False}:
                    raise ValueError("Original removal was not confirmed")
                result["completed_steps"].append("original_library")
                result["stage"] = "original_tracking"
                for record in original["trackRecords"]["nodes"]:
                    self._request(UNBIND_MUTATION, {"recordId": record["id"]})
                result["completed_steps"].append("original_tracking")
                result["stage"] = "final_verification"
                removed = self._manga(original_id)
                if removed["inLibrary"] or removed["trackRecords"]["nodes"]:
                    raise ValueError("Original cleanup was not confirmed")
                self._verify(original, destination, self._manga(destination_id, options["migrate_chapters"]), transfers)
                result["destination"]["in_library"] = True
                result["stage"] = "complete"
            except Exception:
                logging.getLogger(__name__).warning("Suwayomi migration stopped at %s", result["stage"])
                result["status"] = "uncertain" if cleanup_started else "partial"
                result["message"] = (
                    "The destination was copied, but cleanup could not be confirmed. "
                    "Check both entries in Suwayomi before attempting another migration."
                    if cleanup_started else
                    "Migration stopped before original-entry cleanup. The original was kept; "
                    "the destination may have been partly updated. Check both entries in Suwayomi, then review a fresh preview."
                )
            finally:
                self.gateway.invalidateMigrationCaches()
            return result

    @staticmethod
    def _verify(original, before, after, transfers):
        if (not after["inLibrary"] or after["id"] != before["id"]
                or after["sourceId"] != before["sourceId"]):
            raise ValueError("Destination library verification failed")
        expected_tracks = {(r["trackerId"], r["remoteId"]) for r in original["trackRecords"]["nodes"]}
        actual_tracks = {(r["trackerId"], r["remoteId"]) for r in after["trackRecords"]["nodes"]}
        if actual_tracks != expected_tracks:
            raise ValueError("Tracking verification failed")
        categories = {c["id"] for c in after["categories"]["nodes"]}
        if not ({c["id"] for c in before["categories"]["nodes"]} | set(transfers["categories"])) <= categories:
            raise ValueError("Category verification failed")
        chapters = {c["id"]: c for c in after["chapters"]}
        for field, ids in (("isRead", transfers["read"]), ("isBookmarked", transfers["bookmarked"])):
            expected = set(ids) | {c["id"] for c in before["chapters"] if c[field]}
            if any(chapter_id not in chapters or not chapters[chapter_id][field] for chapter_id in expected):
                raise ValueError("Chapter verification failed")
