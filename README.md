# MangaManage

Helps managing stuff downloaded from Tachiyomi

# Features
- Grabs a folder of Tachiyomi downloads, converts them to .cbz with accompanying ComicInfo.xml with its metadata.
- Deletes the .cbz files once you've marked the chapters as read in Anilist
- Quarantines (Moves it to a different folder) comics when there's missing chapters to avoid reading it by accident. They're moved back when the problem is fixed.
  - When there's a gap in downloaded chapters (e.g. 35 skips directly to 38)
  - When the first available chapter isn't the one right after the last one you read (Anilist says last read is 30, first available is 32)
