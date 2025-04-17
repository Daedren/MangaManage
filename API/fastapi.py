import configparser
from fastapi import FastAPI, HTTPException
from appContainer import ApplicationContainer

# Load configuration
config = configparser.ConfigParser(allow_no_value=True)
config.read("settings.ini")

# Initialize the application container
application_container = ApplicationContainer(config)

# Access gateways from the container
anilist_gateway = application_container.gateways.tracker
database_gateway = application_container.gateways.database
filesystem_gateway = application_container.gateways.filesystem
mangaupd_gateway = application_container.gateways.mangaUpdates
pushover_gateway = application_container.gateways.push

# Create FastAPI app
app = FastAPI()


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
async def get_all_chapters():
    """Get all chapters from the database."""
    try:
        chapters = database_gateway.getAllDetailedChapters()
        return {"chapters": chapters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/database/chapter")
async def insert_chapter(series_name: str, chapter_number: str, archive_path: str, source_path: str):
    """Insert a new chapter into the database."""
    try:
        database_gateway.insertChapter(series_name, chapter_number, archive_path, source_path)
        return {"message": "Chapter inserted successfully"}
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
        pushover_gateway.sendPush(message)
        return {"message": "Push notification sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))