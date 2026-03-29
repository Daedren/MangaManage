# MangaManage

Helps managing stuff downloaded from Tachiyomi.

Why? I enjoy Tachiyomi's very well maintained sources, yet want to read on the computer, TV or iPad instead.
This allows for a completely hands-off management of Tachi downloads, to be consumed cross-platform.

## Features

- Grabs a folder of Tachiyomi downloads, converts them to CBZ
  - Also supports chapters already downloaded as CBZ
- Creates ComicInfo.xml metadata files to accompany the CBZ files.
- Deletes the CBZ files once you've marked the chapters as read in Anilist
- Quarantines (Moves it to a different folder) comics when there's missing chapters to avoid reading them by accident. They're moved back when the problem is fixed.
  - When there's a gap in downloaded chapters (e.g. 35 skips directly to 38)
  - When the first available chapter isn't the one right after the last one you read (Anilist says last read is 30, first available is 32)
- Sends a push notification when new chapters are dealt with.
- Can check if there's a more recent manga release on MangaUpdates than the latest one archived. Good to know if a source has been slacking off.

## Future plans

Nothing really, some ideas:

- Perhaps upscale if some scans are found to be of bad resolution.
- Perhaps make the archive folder have series' names again to make the CBZ folders "human readable"
  - Or provide a folder with symlinks/hardlinks?

## Usage

### Local Python Installation

- Set appropriate variables and folder paths in settings.ini
- Install dependencies (`pip install -r requirements.txt`)
- Just run it (`python3 .`) with the manga inside the `sourcefolder` with the same folder structure that Tachiyomi leaves the downloads at.

### Docker

A Docker image is available at [Docker Hub](https://hub.docker.com/r/raikon/mangamanage).

**Setup:**

1. Copy `settings.ini.example` to `settings.ini` and configure it:
   - Use container paths for folders: `/mbase/data/manga.db`, `/mbase/source`, `/mbase/archive`, `/mbase/quarantine`
   - Set your Anilist token and other credentials

2. Update `docker-compose.yml` to match your host folder paths:
   - Point source folder to your Tachiyomi downloads location
   - Set archive and quarantine folders to your desired locations
   - Database will be stored in `./data` by default

3. Run the container:
   ```bash
   # Run once
   docker-compose run --rm mangamanage
   
   # Or run as a service
   docker-compose up
   ```

**Updating Anilist Token:**

When your Anilist refresh token expires, simply:
1. Edit `settings.ini` on your host machine with the new token
2. Restart the container: `docker-compose restart mangamanage`
3. No rebuild required! The container reads the updated file.

**Alternative: Using docker run**

If you prefer not to use docker-compose:

```bash
docker run --rm \
  -v "$(pwd)/settings.ini:/mbase/settings.ini:ro" \
  -v "$(pwd)/data:/mbase/data" \
  -v "/path/to/tachiyomi/downloads:/mbase/source:ro" \
  -v "/path/to/manga/archive:/mbase/archive" \
  -v "/path/to/manga/quarantine:/mbase/quarantine" \
  raikon/mangamanage:latest
```

Remember to update the volume paths to match your system.

There are some additional flags to run only some parts of the code, or to assist in some other manner, though they're not essential.

```text
$ python3 . -h
usage: Running without arguments does the normal program execution, taking care of new chapters, etc
       [-h] [--checkMissingSQL] [--checkMissingChapters] [--mangaUpdates]
       [--updateIds UPDATEIDS UPDATEIDS] [--force] [--interactive]

optional arguments:
  -h, --help            show this help message and exit
  --checkMissingSQL     Detects chapters in filesystem that aren't in
                        database. --force fixes them
  --checkMissingChapters
                        Prints missing chapters from downloaded series.
                        This checks all series, while normal execution only checks those updated
  --mangaUpdates        Cross-checks MangaUpdates to see if there are new
                        chapters released we don't have
  --updateIds UPDATEIDS UPDATEIDS
                        Updates tracker ID in DB for series. Usage:
                        --updateIds <series> <anilistId>
  --force
  --interactive         May ask for user interaction at times where the
                        program would otherwise stop
```
