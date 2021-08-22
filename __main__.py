import argparse
import os
import logging
from manga.updateAnilistIds import UpdateTrackerIds
from manga.missingChapters import CheckGapsInChapters
from mainRunner import MainRunner
import datetime
from appContainer import ApplicationContainer
import configparser

from manga.checkMissingSQL import CheckMissingChaptersInSQL


def main(mainRunner: MainRunner,
         checkMissingSQL: CheckMissingChaptersInSQL,
         checkMissingChapters: CheckGapsInChapters,
         updateTrackerIds: UpdateTrackerIds):
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-deleteRead', action='store_true')
    parser.add_argument('--checkMissingSQL', action='store_true')
    parser.add_argument('--checkMissingChapters', action='store_true')
    parser.add_argument('--updateIds', action='store', type=str, nargs=2,
                        help='Updates tracker ID in DB for series. Usage: --updateIds <series> <anilistId>')
    parser.add_argument('--force', action='store_true')

    args = parser.parse_args()
    print(args)

    if args.checkMissingSQL:
        checkMissingSQL.execute(fixAfter=args.force)
        return

    if args.checkMissingChapters:
        date = datetime.datetime.utcfromtimestamp(0)
        checkMissingChapters.getGapsFromChaptersSince(date)
        return

    if args.updateIds:
        if len(args.updateIds) == 2:
            updateTrackerIds.manualUpdateFor(args.updateIds[0], args.updateIds[1])
        else:
            print("Invalid number of arguments")
        return


    mainRunner.execute()
    return


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('settings.ini')

    assert config is not None
    assert config["manga"]["sourcefolder"] is not None

    logging.basicConfig(level=config["system"]["loglevel"])
    application = ApplicationContainer(config)
    main(application.mainRunner,
         application.manga.checkMissingSQL,
         application.manga.checkGapsInChapters,
         application.manga.updateTrackerIds)
