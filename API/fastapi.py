import configparser
import asyncio
from contextlib import asynccontextmanager
import datetime
import http.client
import logging
from typing import Annotated, Literal
from fastapi import Body, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from appContainer import ApplicationContainer
from cross.last_run_logs import CaptureBusy, capture_last_run_logs, get_last_run_log_path
from API.task_runs import TaskRuns
from API.log_stream import follow_logs, read_log
from manga.missingChapters import CheckGapsInChapters
from manga.gateways.utils.exceptions import AnilistRequestException, TokenRefreshException
from manga.gateways.suwayomi import SuwayomiDownloadError
from manga.suwayomiMigration import SuwayomiMigrationError

# Load configuration
config = configparser.ConfigParser(allow_no_value=True)
config.read("settings.ini")

# Parse allowed origins from settings.ini
allowed_origins = config["system"]["allowed_origins"].split(",")

# Initialize the application container
application_container = ApplicationContainer(config)

# Access gateways from the container
anilist_gateway = application_container.gateways.tracker
database_gateway = application_container.gateways.database
filesystem_gateway = application_container.gateways.filesystem
mangaupd_gateway = application_container.gateways.mangaUpdates
suwayomi_gateway = application_container.gateways.suwayomi
pushover_gateway = application_container.gateways.push


class UpdateAnilistIdRequest(BaseModel):
    series: str
    anilistId: str


class TrackerGapRequest(BaseModel):
    type: Literal["tracker_gap"]
    last_read: float = Field(ge=0, allow_inf_nan=False)
    first_stored: float = Field(gt=0, allow_inf_nan=False)


class ConsecutiveGapRequest(BaseModel):
    type: Literal["consecutive_gap"]
    before: float = Field(ge=0, allow_inf_nan=False)
    after: float = Field(gt=0, allow_inf_nan=False)


GapDownloadRequest = Annotated[TrackerGapRequest | ConsecutiveGapRequest, Body(discriminator="type")]


class MigrationSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    original_manga_id: int = Field(ge=0, strict=True)
    source_id: str = Field(pattern=r"^[0-9]+$", max_length=20, strict=True)
    query: str = Field(min_length=1, max_length=300, strict=True)
    page: int = Field(default=1, ge=1, le=1000, strict=True)


class MigrationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_manga_id: int = Field(ge=0, strict=True)
    destination_manga_id: int = Field(ge=0, strict=True)
    migrate_chapters: bool = Field(default=True, strict=True)
    migrate_categories: bool = Field(default=True, strict=True)

    def options(self):
        return {
            "migrate_chapters": self.migrate_chapters,
            "migrate_categories": self.migrate_categories,
        }


class MigrationExecuteRequest(MigrationPreviewRequest):
    preview_token: str = Field(min_length=1, max_length=100, strict=True)


# Create FastAPI app
task_runs = TaskRuns(config)


@asynccontextmanager
async def lifespan(app):
    yield
    await asyncio.to_thread(task_runs.close)


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Use origins from settings.ini
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


@app.get("/anilist/progress/{media_id}")
async def get_anilist_progress(media_id: int):
    """Get progress for a specific media ID from Anilist."""
    try:
        progress = await asyncio.to_thread(anilist_gateway.getProgressFor, media_id)
        if progress is None:
            raise HTTPException(status_code=404, detail="Media ID not found")
        return {"media_id": media_id, "progress": progress}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_all_read_progress() -> tuple[
    dict[int, int] | None, dict[int, str | None] | None, str | None
]:
    """Load progress and AniList list status in one cached bulk lookup."""
    try:
        entries = anilist_gateway.getAllEntries(reading_only=False)
        if entries is not None:
            progress = {media_id: entry.progress for media_id, entry in entries.items()}
            list_status = {
                media_id: getattr(entry, "list_status", None)
                for media_id, entry in entries.items()
            }
            return progress, list_status, None
        return None, None, "AniList returned no read-progress response."
    except TokenRefreshException:
        reason = "AniList authentication needs renewal; refresh the token in settings.ini."
    except AnilistRequestException as error:
        if error.status == 429:
            reason = "AniList rate limit reached (HTTP 429); try again later."
        elif error.status == 401:
            reason = "AniList authentication failed (HTTP 401); refresh the token in settings.ini."
        elif error.status == 403:
            reason = "AniList access denied (HTTP 403); check the token and account access."
        elif error.status is not None:
            reason = f"AniList API request failed (status {error.status}); try again later."
        else:
            reason = "AniList rejected the read-progress query; check server logs."
    except TimeoutError:
        reason = "AniList read-progress request timed out; try again later."
    except (OSError, http.client.HTTPException):
        reason = "Could not connect to AniList to retrieve read progress; check the connection."
    except (ValueError, KeyError, TypeError, AttributeError):
        logging.getLogger(__name__).warning("Invalid AniList read-progress response", exc_info=True)
        reason = "AniList returned an invalid read-progress response; check server logs."
    except Exception as error:
        logging.getLogger(__name__).warning("Unable to retrieve AniList read progress", exc_info=True)
        reason = f"AniList read-progress lookup failed ({type(error).__name__}); check server logs."
    return None, None, reason


@app.get("/anilist/progress")
def get_anilist_progress_list():
    """Get read progress across all AniList lists using one cached bulk lookup."""
    progress, _, reason = get_all_read_progress()
    if progress is None:
        raise HTTPException(status_code=503, detail=reason)
    return {"progress": progress}


@app.get("/anilist/search")
async def search_anilist(title: str):
    """Search for a media title in Anilist."""
    try:
        results = await asyncio.to_thread(anilist_gateway.searchMediaBy, title)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/chapters")
async def get_all_chapters(active: int = 1, title: str = None, limit: int = 50, offset: int = 0):
    """Get paginated chapters from the database."""
    try:
        chapters, total = await asyncio.to_thread(
            database_gateway.getAllDetailedChapters,
            active=active, title=title, limit=limit, offset=offset
        )
        return {"chapters": chapters, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/series")
def get_all_series(
    title: str = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    quarantined: bool | None = None,
    mangaupdates_status: Literal[
        "up_to_date", "missing_chapters", "unavailable", "unknown"
    ] | None = None,
    sort_by: Literal["series", "last_updated", "quarantined"] = "last_updated",
    sort_direction: Literal["asc", "desc"] = "desc",
):
    """List series by their newest chapter creation date, including inactive chapters."""
    try:
        # AniList list status is only available from its bulk list lookup, so
        # filter the complete matching result before slicing the requested page.
        series, total = database_gateway.getAllDetailedSeries(
            title=title.strip() if title else None,
            limit=None,
            offset=0,
            quarantined_ids=filesystem_gateway.getQuarantinedSeries(),
            quarantined=quarantined, sort_by=sort_by, sort_direction=sort_direction,
        )
        # Load one bulk snapshot whenever the matching result has mapped series,
        # both for displayed last-read chapters and AniList list status checks.
        needs_tracker_data = any(item.get("anilistId") is not None for item in series)
        progress, list_status, progress_error = (
            get_all_read_progress() if needs_tracker_data else (None, None, None)
        )
        for item in series:
            latest = item.get("mangaupdates_latest_chapter")
            stored = item.get("latest_stored_chapter") or 0
            last_read = progress.get(item["anilistId"]) if progress is not None else None
            item["anilist_last_read"] = last_read
            reason = None
            if latest is None:
                status = "unavailable"
                if item["anilistId"] is None:
                    reason = "No AniList ID assigned; MangaUpdates cannot be linked."
                elif item.get("mangaupdates_id") is None:
                    reason = "No MangaUpdates ID linked to this series."
                else:
                    reason = "MangaUpdates ID is linked, but no latest chapter has been cached."
            elif stored >= latest or (last_read is not None and last_read >= latest):
                status = "up_to_date"
            elif item["anilistId"] is None:
                status = "unknown"
                reason = "Stored chapters are behind; no AniList ID assigned to check read progress."
            elif progress is None:
                status = "unknown"
                reason = progress_error
            elif item["anilistId"] in progress and last_read is None:
                status = "unknown"
                reason = "AniList returned no read progress for this series."
            else:
                status = "missing_chapters"
                if item["anilistId"] not in progress:
                    reason = "Stored chapters are behind; this series is not on your AniList list."
            item["mangaupdates_status"] = status
            item["mangaupdates_status_reason"] = reason
        excluded_ids = {
            media_id for media_id, status in (list_status or {}).items()
            if status in ("COMPLETED", "DROPPED", "PAUSED")
        }
        series = [item for item in series if item.get("anilistId") not in excluded_ids]
        if mangaupdates_status is not None:
            series = [
                item for item in series
                if item["mangaupdates_status"] == mangaupdates_status
            ]
        total = len(series)
        series = series[offset:offset + limit]
        # One cached, paginated library snapshot; no per-row Suwayomi requests.
        needs_sources = any(item.get("anilistId") is not None for item in series)
        sources, source_error = suwayomi_gateway.getLibrarySources() if needs_sources else ({}, None)
        for item in series:
            item["suwayomi_sources"] = sources.get(item.get("anilistId"), [])
            item["suwayomi_status_reason"] = (
                "No AniList ID assigned to match Suwayomi tracking records."
                if item.get("anilistId") is None else source_error or (
                    None if item["suwayomi_sources"]
                    else "No matching AniList-linked manga with a source in the Suwayomi library."
                )
            )
        return {"series": series, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/series/{anilist_id}/quarantine-details")
def get_series_quarantine_details(anilist_id: int):
    """Explain current gaps on demand; never run the mutating quarantine workflow."""
    try:
        quarantined = anilist_id in filesystem_gateway.getQuarantinedSeries()
        if not quarantined:
            return {"quarantined": False, "status": "not_quarantined", "reasons": []}
        checker = CheckGapsInChapters(database_gateway, filesystem_gateway, anilist_gateway)
        return {"quarantined": True, **checker.getQuarantineDetails(anilist_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/database/series/{anilist_id}/quarantine-gap/download")
def download_series_quarantine_gap(anilist_id: int, request: GapDownloadRequest):
    """Revalidate one current gap, then queue available chapters in Suwayomi."""
    try:
        if anilist_id not in filesystem_gateway.getQuarantinedSeries():
            raise HTTPException(status_code=409, detail="This series is no longer quarantined. Refresh its details.")
        anilist_gateway.clearCache()
        checker = CheckGapsInChapters(database_gateway, filesystem_gateway, anilist_gateway)
        details = checker.getQuarantineDetails(anilist_id)
        if details["status"] == "tracker_unavailable":
            raise HTTPException(status_code=503, detail="AniList progress is unavailable. Try again later.")
        if request.model_dump() not in details["reasons"]:
            raise HTTPException(status_code=409, detail="This gap has changed or is no longer present. Refresh its details.")
        if isinstance(request, TrackerGapRequest):
            lower, upper = request.last_read, request.first_stored
        else:
            lower, upper = request.before, request.after
        return suwayomi_gateway.queueGapDownloads(anilist_id, lower, upper)
    except HTTPException:
        raise
    except SuwayomiDownloadError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except Exception:
        logging.getLogger(__name__).warning("Unable to queue downloads for a quarantine gap")
        raise HTTPException(status_code=500, detail="Unable to check this gap. Try again or check server logs.") from None


def migration_response(action):
    """All migration errors are sanitized, including malformed upstream data."""
    try:
        return action()
    except SuwayomiMigrationError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None
    except Exception:
        logging.getLogger(__name__).warning("Unable to process Suwayomi migration data")
        raise HTTPException(
            status_code=503,
            detail=("Unable to load valid migration data from Suwayomi. "
                    "Check its connection and version, then try again."),
        ) from None


@app.get("/database/series/{anilist_id}/migration")
def get_series_migration(
    anilist_id: Annotated[int, Path(ge=1)],
    original_manga_id: int = Query(ge=0),
):
    return migration_response(
        lambda: suwayomi_gateway.migration.context(anilist_id, original_manga_id)
    )


@app.post("/database/series/{anilist_id}/migration/search")
def search_series_migration(
    anilist_id: Annotated[int, Path(ge=1)], request: MigrationSearchRequest,
):
    return migration_response(lambda: suwayomi_gateway.migration.search(
        anilist_id, request.original_manga_id, request.source_id, request.query, request.page,
    ))


@app.post("/database/series/{anilist_id}/migration/preview")
def preview_series_migration(
    anilist_id: Annotated[int, Path(ge=1)], request: MigrationPreviewRequest,
):
    return migration_response(lambda: suwayomi_gateway.migration.preview(
        anilist_id, request.original_manga_id, request.destination_manga_id, request.options(),
    ))


@app.post("/database/series/{anilist_id}/migration")
def execute_series_migration(
    anilist_id: Annotated[int, Path(ge=1)], request: MigrationExecuteRequest,
):
    return migration_response(lambda: suwayomi_gateway.migration.execute(
        anilist_id, request.original_manga_id, request.destination_manga_id,
        request.options(), request.preview_token,
    ))


@app.get("/logs")
def get_logs(cursor: str | None = None, run_id: str | None = None):
    """Read at most 64 KiB; a cursor reads subsequent output instead of the whole file."""
    try:
        return read_log(resolve_log_path(run_id), cursor)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def resolve_log_path(run_id):
    if run_id is None:
        return get_last_run_log_path(config)
    try:
        return task_runs.log_path(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task run not found or no longer retained.") from None


@app.get("/logs/stream")
async def stream_logs(request: Request, cursor: str | None = None, run_id: str | None = None):
    path = await asyncio.to_thread(resolve_log_path, run_id)
    status = (lambda: task_runs.get(run_id)) if run_id else None
    return StreamingResponse(
        follow_logs(request, path, request.headers.get("last-event-id") or cursor, status),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/tasks/runs/latest")
def latest_task_run():
    return {"run": task_runs.latest()}


@app.get("/tasks/runs/{run_id}")
def get_task_run(run_id: str):
    try:
        return task_runs.get(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task run not found or no longer retained.") from None


def start_task(label, action):
    try:
        return task_runs.start(label, action)
    except CaptureBusy as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@app.post("/tasks/process-source", status_code=202)
def process_source():
    def action():
        anilist_gateway.clearCache()
        application_container.mainRunner.execute(interactive=False)
        return {"message": "Source processing completed"}
    return start_task("Process source", action)


@app.post("/tasks/check-missing-sql", status_code=202)
def check_missing_sql(fix: bool = False):
    def action():
        application_container.manga.checkMissingSQL.execute(fixAfter=fix)
        return {"message": "Missing SQL check completed", "fix": fix}
    return start_task("Fix missing SQL" if fix else "Check missing SQL", action)


@app.post("/tasks/check-missing-chapters", status_code=202)
def check_missing_chapters():
    def action():
        anilist_gateway.clearCache()
        gaps = application_container.manga.checkGapsInChapters.getGapsFromChaptersSince(
            datetime.datetime.utcfromtimestamp(0)
        )
        return {
            "message": "Missing chapter check completed",
            "missing_chapters": [gap.reasonToPrint() for gap in gaps or []],
        }
    return start_task("Check missing chapters", action)


@app.post("/tasks/check-manga-updates", status_code=202)
def check_manga_updates():
    def action():
        anilist_gateway.clearCache()
        application_container.manga.checkForUpdates.updateLocalIds()
        application_container.manga.checkForUpdates.checkForUpdates()
        return {"message": "MangaUpdates check completed"}
    return start_task("Check MangaUpdates", action)


@app.post("/tasks/update-anilist-id", status_code=202)
def update_anilist_id(request: UpdateAnilistIdRequest):
    def action():
        anilist_gateway.clearCache()
        application_container.manga.updateTrackerIds.manualUpdateFor(request.series, request.anilistId)
        return {
            "message": "AniList ID updated",
            "series": request.series,
            "anilistId": request.anilistId,
        }
    return start_task("Update AniList ID", action)


@app.get("/database/anilist-id")
async def get_anilist_id_for_title(title: str):
    """Get the stored AniList ID for a title."""
    try:
        anilist_id = await asyncio.to_thread(database_gateway.getAnilistIDForSeries, title)
        if anilist_id is None:
            raise HTTPException(status_code=404, detail="Title not found")
        return {"title": title, "anilistId": anilist_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/database/chapter")
async def insert_chapter(series_name: str, chapter_number: str, archive_path: str, source_path: str):
    """Insert a new chapter into the database."""
    await run_logged_action(
        f"API insert chapter for {series_name}",
        lambda: database_gateway.insertChapter(series_name, chapter_number, archive_path, source_path),
    )
    return {"message": "Chapter inserted successfully"}


async def run_logged_action(label, action):
    def execute():
        with capture_last_run_logs(config, label):
            return action()
    try:
        return await asyncio.to_thread(execute)
    except CaptureBusy as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from None

@app.delete("/database/chapter")
async def delete_chapter(database_id: int):
    """Delete a chapter archive and mark its database record inactive."""
    def action():
        chapter = database_gateway.getChapterDetailsById(database_id)
        if chapter is not None:
            filesystem_gateway.deleteArchive(chapter["anilistId"], chapter["chapter"])
        database_gateway.deleteChapterById(database_id)
    await run_logged_action(f"API delete chapter {database_id}", action)
    return {"message": "Chapter deleted successfully"}


@app.get("/filesystem/quarantined")
async def get_quarantined_series():
    """Get all quarantined series."""
    try:
        quarantined_series = await asyncio.to_thread(filesystem_gateway.getQuarantinedSeries)
        return {"quarantined_series": quarantined_series}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/filesystem/quarantine/{anilist_id}")
async def quarantine_series(anilist_id: str):
    """Quarantine a series by its Anilist ID."""
    await run_logged_action(
        f"API quarantine series {anilist_id}", lambda: filesystem_gateway.quarantineSeries(anilist_id),
    )
    return {"message": f"Series {anilist_id} quarantined successfully"}


@app.get("/mangaupd/latest/{series_id}")
async def get_latest_releases(series_id: int):
    """Get the latest chapter from MangaUpdates and cache it in the database."""
    try:
        latest_chapter, manga_updates_url = await asyncio.to_thread(mangaupd_gateway.getSeriesDetailsForId, series_id)
        if latest_chapter is not None or manga_updates_url is not None:
            await asyncio.to_thread(
                database_gateway.updateMangaUpdtLatestChapter,
                series_id, latest_chapter, manga_updates_url
            )
        return {"series_id": series_id, "latest_chapter": latest_chapter}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pushover/send")
async def send_push_notification(message: str):
    """Send a push notification using Pushover."""
    await run_logged_action("API send push notification", lambda: pushover_gateway.sendPush(message))
    return {"message": "Push notification sent successfully"}
