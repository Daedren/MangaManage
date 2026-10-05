import configparser
import datetime
import http.client
import logging
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from appContainer import ApplicationContainer
from cross.last_run_logs import capture_last_run_logs, get_last_run_log_path
from manga.missingChapters import CheckGapsInChapters
from manga.gateways.utils.exceptions import AnilistRequestException, TokenRefreshException

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
pushover_gateway = application_container.gateways.push


class UpdateAnilistIdRequest(BaseModel):
    series: str
    anilistId: str

# Create FastAPI app
app = FastAPI()

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
        progress = anilist_gateway.getProgressFor(media_id)
        if progress is None:
            raise HTTPException(status_code=404, detail="Media ID not found")
        return {"media_id": media_id, "progress": progress}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_all_read_progress() -> tuple[dict[int, int] | None, str | None]:
    """Use the gateway's cached, general list query, never one request per series."""
    try:
        entries = anilist_gateway.getAllEntries(reading_only=False)
        if entries is not None:
            return {media_id: entry.progress for media_id, entry in entries.items()}, None
        return None, "AniList returned no read-progress response."
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
    return None, reason


@app.get("/anilist/progress")
def get_anilist_progress_list():
    """Get read progress across all AniList lists using one cached bulk lookup."""
    progress, reason = get_all_read_progress()
    if progress is None:
        raise HTTPException(status_code=503, detail=reason)
    return {"progress": progress}


@app.get("/anilist/search")
async def search_anilist(title: str):
    """Search for a media title in Anilist."""
    try:
        results = anilist_gateway.searchMediaBy(title)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/chapters")
async def get_all_chapters(active: int = 1, title: str = None, limit: int = 50, offset: int = 0):
    """Get paginated chapters from the database."""
    try:
        chapters, total = database_gateway.getAllDetailedChapters(
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
        filter_before_pagination = mangaupdates_status is not None
        series, total = database_gateway.getAllDetailedSeries(
            title=title.strip() if title else None,
            limit=None if filter_before_pagination else limit,
            offset=0 if filter_before_pagination else offset,
            quarantined_ids=filesystem_gateway.getQuarantinedSeries(),
            quarantined=quarantined, sort_by=sort_by, sort_direction=sort_direction,
        )
        # Load a single bulk snapshot whenever this page has mapped series, both
        # for the displayed last-read chapter and MangaUpdates status checks.
        needs_progress = any(item.get("anilistId") is not None for item in series)
        progress, progress_error = get_all_read_progress() if needs_progress else (None, None)
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
        if filter_before_pagination:
            series = [
                item for item in series
                if item["mangaupdates_status"] == mangaupdates_status
            ]
            total = len(series)
            series = series[offset:offset + limit]
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


@app.get("/logs")
async def get_logs():
    """Get logs from the last CLI or API run."""
    try:
        log_path = get_last_run_log_path(config)
        if not log_path.exists():
            return {"logs": "", "exists": False}
        return {"logs": log_path.read_text(encoding="utf-8", errors="replace"), "exists": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/process-source")
async def process_source():
    """Run the default CLI processing task."""
    try:
        anilist_gateway.clearCache()
        with capture_last_run_logs(config, "API process source"):
            application_container.mainRunner.execute(interactive=False)
        return {"message": "Source processing completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/check-missing-sql")
async def check_missing_sql(fix: bool = False):
    """Detect archived chapters that are missing from the database."""
    try:
        with capture_last_run_logs(config, "API check missing SQL"):
            application_container.manga.checkMissingSQL.execute(fixAfter=fix)
        return {"message": "Missing SQL check completed", "fix": fix}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/check-missing-chapters")
async def check_missing_chapters():
    """Check all archived series for missing chapter gaps."""
    try:
        anilist_gateway.clearCache()
        with capture_last_run_logs(config, "API check missing chapters"):
            gaps = application_container.manga.checkGapsInChapters.getGapsFromChaptersSince(
                datetime.datetime.utcfromtimestamp(0)
            )
        return {
            "message": "Missing chapter check completed",
            "missing_chapters": [gap.reasonToPrint() for gap in gaps or []],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/check-manga-updates")
async def check_manga_updates():
    """Run the MangaUpdates CLI check."""
    try:
        anilist_gateway.clearCache()
        with capture_last_run_logs(config, "API check MangaUpdates"):
            application_container.manga.checkForUpdates.updateLocalIds()
            application_container.manga.checkForUpdates.checkForUpdates()
        return {"message": "MangaUpdates check completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/update-anilist-id")
async def update_anilist_id(request: UpdateAnilistIdRequest):
    """Manually update the AniList ID for a series."""
    try:
        anilist_gateway.clearCache()
        with capture_last_run_logs(config, f"API update AniList ID for {request.series}"):
            application_container.manga.updateTrackerIds.manualUpdateFor(
                request.series, request.anilistId
            )
        return {
            "message": "AniList ID updated",
            "series": request.series,
            "anilistId": request.anilistId,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/anilist-id")
async def get_anilist_id_for_title(title: str):
    """Get the stored AniList ID for a title."""
    try:
        anilist_id = database_gateway.getAnilistIDForSeries(title)
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
    try:
        with capture_last_run_logs(config, f"API insert chapter for {series_name}"):
            database_gateway.insertChapter(series_name, chapter_number, archive_path, source_path)
        return {"message": "Chapter inserted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/database/chapter")
async def delete_chapter(database_id: int):
    """Delete a chapter archive and mark its database record inactive."""
    try:
        with capture_last_run_logs(config, f"API delete chapter {database_id}"):
            chapter = database_gateway.getChapterDetailsById(database_id)
            if chapter is not None:
                filesystem_gateway.deleteArchive(chapter["anilistId"], chapter["chapter"])
            database_gateway.deleteChapterById(database_id)
        return {"message": "Chapter deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/filesystem/quarantined")
async def get_quarantined_series():
    """Get all quarantined series."""
    try:
        quarantined_series = filesystem_gateway.getQuarantinedSeries()
        return {"quarantined_series": quarantined_series}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/filesystem/quarantine/{anilist_id}")
async def quarantine_series(anilist_id: str):
    """Quarantine a series by its Anilist ID."""
    try:
        with capture_last_run_logs(config, f"API quarantine series {anilist_id}"):
            filesystem_gateway.quarantineSeries(anilist_id)
        return {"message": f"Series {anilist_id} quarantined successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mangaupd/latest/{series_id}")
async def get_latest_releases(series_id: int):
    """Get the latest chapter from MangaUpdates and cache it in the database."""
    try:
        latest_chapter = mangaupd_gateway.getLatestChapterForId(series_id)
        if latest_chapter is not None:
            database_gateway.updateMangaUpdtLatestChapter(series_id, latest_chapter)
        return {"series_id": series_id, "latest_chapter": latest_chapter}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pushover/send")
async def send_push_notification(message: str):
    """Send a push notification using Pushover."""
    try:
        with capture_last_run_logs(config, "API send push notification"):
            pushover_gateway.sendPush(message)
        return {"message": "Push notification sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
