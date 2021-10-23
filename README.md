# MangaManage

Helps managing stuff downloaded from Tachiyomi.

# Features
- Grabs a folder of Tachiyomi downloads, converts them to .cbz with accompanying ComicInfo.xml with its metadata.
- Deletes the .cbz files once you've marked the chapters as read in Anilist
- Quarantines (Moves it to a different folder) comics when there's missing chapters to avoid reading it by accident. They're moved back when the problem is fixed.
  - When there's a gap in downloaded chapters (e.g. 35 skips directly to 38)
  - When the first available chapter isn't the one right after the last one you read (Anilist says last read is 30, first available is 32)
- Can check if there's a more recent manga release on MangaUpdates than the latest one archived. Good to know if a source has been slacking off.
  - TODO: Cache it

# Future plans
Nothing really, some ideas:
- Perhaps upscale if some scans are found to be of bad resolution.
- Information about missing chapters and errors in the push notification
- Perhaps make the archive folder have series' names again for those who read directly from the cbz folders
  - Or provide a folder with symlinks/hardlinks

# Usage
- Set appropriate variables and folder paths in settings.ini
- Install dependencies (`pip install -r requirements.txt`)
- Just run it (`python3 .`) with the manga inside the `sourcefolder` with the same folder structure that Tachiyomi leaves the downloads at.

Alternatively there's a Dockerfile and image available at [Docker Hub](https://hub.docker.com/r/raikon/mangamanage)

There are some additional flags to run only some parts of the code, or to assist in some other manner, though they're not essential.

```
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
