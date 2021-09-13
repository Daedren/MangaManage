import argparse
import logging
import sys
from manga.updateAnilistIds import UpdateTrackerIds
from manga.missingChapters import CheckGapsInChapters
from manga.checkForUpdates import CheckForUpdates
from mainRunner import MainRunner
import datetime
from appContainer import ApplicationContainer
import configparser

from manga.checkMissingSQL import CheckMissingChaptersInSQL


def main(
    mainRunner: MainRunner,
    checkMissingSQL: CheckMissingChaptersInSQL,
    checkMissingChapters: CheckGapsInChapters,
    updateTrackerIds: UpdateTrackerIds,
    checkForUpdates: CheckForUpdates,
):
    parser = argparse.ArgumentParser("Running without arguments does the normal program execution, taking care of new chapters, etc")
    parser.add_argument(
        "--checkMissingSQL",
        action="store_true",
        help="Detects chapters in filesystem that aren't in database. --force fixes them",
    )
    parser.add_argument(
        "--checkMissingChapters",
        action="store_true",
        help="Prints missing chapters from downloaded series. This checks all series, while normal execution only checks those updated",
    )
    parser.add_argument(
        "--mangaUpdates",
        action="store_true",
        help="Cross-checks MangaUpdates to see if there are new chapters released we don't have",
    )
    parser.add_argument(
        "--updateIds",
        action="store",
        type=str,
        nargs=2,
        help="""Updates tracker ID in DB for series.
                        Usage: --updateIds <series> <anilistId>""",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="May ask for user interaction at times where the program would otherwise stop",
    )

    args = parser.parse_args()
    print(args)

    if args.checkMissingSQL:
        checkMissingSQL.execute(fixAfter=args.force)
        return

    if args.checkMissingChapters:
        date = datetime.datetime.utcfromtimestamp(0)
        checkMissingChapters.getGapsFromChaptersSince(date)
        return

    if args.mangaUpdates:
        checkForUpdates.updateLocalIds()
        checkForUpdates.checkForUpdates()
        return

    if args.updateIds:
        if len(args.updateIds) == 2:
            updateTrackerIds.manualUpdateFor(args.updateIds[0], args.updateIds[1])
        else:
            print("Invalid number of arguments")
        return

    mainRunner.execute(interactive=args.interactive)
    return


if __name__ == "__main__":
    config = configparser.ConfigParser(allow_no_value=True)
    config.read("settings.ini")

    assert config is not None
    assert config["manga"]["sourcefolder"] is not None

    handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(level=config["system"]["loglevel"], handlers=[handler])
    application = ApplicationContainer(config)
    main(
        application.mainRunner,
        application.manga.checkMissingSQL,
        application.manga.checkGapsInChapters,
        application.manga.updateTrackerIds,
        application.manga.checkForUpdates,
    )
