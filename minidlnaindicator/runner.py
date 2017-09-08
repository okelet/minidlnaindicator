
import argparse
import logging
import os
import sys

from minidlnaindicator.constants import LOG_DIR, LOG_LEVELS, LOGGING_CONFIG, APPINDICATOR_ID, LOCALE_DIR
from minidlnaindicator.exceptions.alreadyrunning import AlreadyRunningException
from minidlnaindicator.indicator import MiniDLNAIndicator
from minidlnaindicator.indicatorconfig import MiniDLNAIndicatorConfig

import gettext
_ = gettext.translation(APPINDICATOR_ID, LOCALE_DIR, fallback=True).gettext


def indicator() -> None:

    if not os.path.exists(LOG_DIR):
        os.mkdir(LOG_DIR)

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config')
    parser.add_argument('--stderr', action='store_true')
    parser.add_argument('--test-mode', action='store_true')
    parser.add_argument('-l', '--log-level', choices=LOG_LEVELS.keys())
    args = parser.parse_args()

    if args.stderr:
        LOGGING_CONFIG["loggers"]["minidlnaindicator"]["handlers"].append("console_handler")

    if args.log_level:
        LOGGING_CONFIG["loggers"]["minidlnaindicator"]["level"] = LOG_LEVELS.get(args.log_level)

    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)

    try:
        config = MiniDLNAIndicatorConfig(args.config, cmd_log_level=args.log_level)
    except Exception as ex:
        logger.exception("Error loading the configuration: %s.", ex)
        print(_("Error loading the configuration: {error}.").format(error=str(ex)), file=sys.stderr)
        sys.exit(1)

    try:
        app = MiniDLNAIndicator(config, args.test_mode)
        app.run()
    except AlreadyRunningException as _ex:
        logger.info("Application already running.")
        print(_("Application already running."))
        sys.exit(0)


if __name__ == "__main__":
    indicator()
