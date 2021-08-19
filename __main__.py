import argparse
from mainRunner import MainRunner
from appContainer import ApplicationContainer
import configparser

import manga.deleteReadAnilist as deleteRead
import manga.updateAnilistIds as updateIds
import manga.mangagetchapter as getChapter
import manga.missingChapters as missingChapters
from manga.checkMissingSQL import CheckMissingChaptersInSQL


def main(mainRunner: MainRunner,
         checkMissingSQL: CheckMissingChaptersInSQL):
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-deleteRead', action='store_true')
    parser.add_argument('-updateIds', action='store', type=str,
                        nargs='?',
                        default=None,
                        const='',
                        help='Updates anilistIds for the inputted series, or all of them.')
    parser.add_argument('-getChapter', action='store', type=str, nargs=2,
                        help='Returns chapter number for given title and anilistId')
    parser.add_argument('-missingChapters', action='store', type=str, nargs=1,
                        help='Returns missing chapters from given start date')
    parser.add_argument('--checkMissingSQL', action='store_true')
    parser.add_argument('--force', action='store_true')

    args = parser.parse_args()

    #if args.deleteRead:
    #    deleteRead.execute()

    #if args.updateIds is not None:
    #    if args.updateIds != '':
    #        print(updateIds.updateFor(args.updateIds))
    #    else:
    #        print(updateIds.updateAll())

    #if args.getChapter:
    #    print(getChapter.execute(args.getChapter[0], args.getChapter[1]))

    #if args.missingChapters:
    #    missingChapters.getProgressSince(args.missingChapters[0])

    if args.checkMissingSQL:
        checkMissingSQL.execute(fixAfter=args.force)
        return

    mainRunner.execute()
    return


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('settings.ini')

    #application = ApplicationContainer()
    #application.config.from_ini('settings.ini')
    #application.wire(modules=[sys.modules[__name__]])
    assert config is not None
    assert config["manga"]["sourcefolder"] is not None
    application = ApplicationContainer(config)
    main(application.mainRunner,
         application.manga.checkMissingSQL)
