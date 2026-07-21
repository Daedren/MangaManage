import configparser
import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from appContainer import ApplicationContainer
from cross.last_run_logs import capture_last_run_logs, get_last_run_log_path

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
    """Delete a chapter from the database."""
    try:
        with capture_last_run_logs(config, f"API delete chapter {database_id}"):
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
    """Get the latest releases for a series from MangaUpdates."""
    try:
        releases = mangaupd_gateway.latestReleasesForId(series_id)
        return {"series_id": series_id, "releases": releases}
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
