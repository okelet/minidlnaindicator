
from typing import Dict, Any

import logging
import os
import re


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALE_DIR = os.path.join(BASE_DIR, "locale")

APPINDICATOR_ID = 'minidlnaindicator'

APP_DBUS_PATH = "/com/github/okelet/minidlnaindicator"
APP_DBUS_DOMAIN = APP_DBUS_PATH
APP_DBUS_DOMAIN = re.sub("^/", "", APP_DBUS_DOMAIN)
APP_DBUS_DOMAIN = re.sub("/", ".", APP_DBUS_DOMAIN)

MINIDLNA_CONFIG_DIR = os.path.expanduser("~/.minidlna")
MINIDLNA_CONFIG_FILE = os.path.join(MINIDLNA_CONFIG_DIR, "minidlna.conf")
MINIDLNA_CACHE_DIR = os.path.join(MINIDLNA_CONFIG_DIR, "cache")
MINIDLNA_INDICATOR_CONFIG = os.path.join(MINIDLNA_CONFIG_DIR, "indicator.json")
MINIDLNA_LOG_FILENAME = "minidlna.log"
MINIDLNA_LOG_PATH = os.path.join(MINIDLNA_CONFIG_DIR, MINIDLNA_LOG_FILENAME)

XDG_CONFIG_DIR = os.path.expanduser("~/.config")
XDG_AUTOSTART_DIR = os.path.join(XDG_CONFIG_DIR, "autostart")
XDG_AUTOSTART_FILE = os.path.join(XDG_AUTOSTART_DIR, APPINDICATOR_ID + ".desktop")

MINIDLNA_ICON_GREY = os.path.join(BASE_DIR, "icons", "dlna_grey_32.png")
MINIDLNA_ICON_GREEN = os.path.join(BASE_DIR, "icons", "dlna_green_32.png")

# AUDIO_ICON = os.path.join(BASEDIR, "audio.svg")
# PICTURE_ICON = os.path.join(BASEDIR, "picture.svg")
# PICTUREVIDEO_ICON = os.path.join(BASEDIR, "picturevideo.svg")
# VIDEO_ICON = os.path.join(BASEDIR, "video.svg")
# MIXED_ICON = os.path.join(BASEDIR, "mixed.svg")

USER_CONFIG_DIR = os.path.expanduser("~/.minidlna")
USER_CONFIG_FILE = "minidlnaindicator.yml"
USER_CONFIG_PATH = os.path.join(USER_CONFIG_DIR, USER_CONFIG_FILE)

LOG_DIR = USER_CONFIG_DIR
LOG_FILE = "minidlnaindicator.log"
LOG_PATH = os.path.join(USER_CONFIG_DIR, LOG_FILE)

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "simple": {
            "format": "%(asctime)s - %(levelname)s - %(name)s:%(funcName)s:%(lineno)s - %(message)s",
        },
    },
    "handlers": {
        "console_handler": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "stream": "ext://sys.stderr",
        },
        "file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "simple",
            "filename": LOG_PATH,
            "maxBytes": 1048576,
            "backupCount": 10,
            "encoding": "utf8",
        },
    },
    "loggers": {
        "minidlnaindicator": {
            "level": "ERROR",
            "handlers": ["file_handler"],
            "propagate": False,
        },
    },
    "root": {
        "level": "ERROR",
        "handlers": ["file_handler"],
    },
}  # type: Dict[str, Any]
