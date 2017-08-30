
from typing import List, Optional

import codecs
import enum
import getpass
import gettext
import logging
import os
import random
import re
import time
import uuid

from gi.repository import GLib

from .constants import MINIDLNA_CACHE_DIR, MINIDLNA_CONFIG_DIR, MINIDLNA_LOG_FILENAME, MINIDLNA_CONFIG_FILE, \
    APPINDICATOR_ID, LOCALE_DIR, MINIDLNA_LOG_PATH

_ = gettext.translation(APPINDICATOR_ID, LOCALE_DIR, fallback=True).gettext


class MiniDLNAConfig(object):
    """
    :type log: str
    """
    def __init__(self, indicator, config_file: str) -> None:

        self.logger = logging.getLogger(__name__)

        self.port = 0
        self.dirs = []  # type: List[MiniDLNADirectory]
        self.log = None  # type: Optional[str]

        self.indicator = indicator
        self.config_file = config_file
        self.last_reloaded = 0  # type: float
        self.reload_config()


    def reload_config(self) -> None:

        self.port = 0
        self.dirs = []
        self.log = None

        if not os.path.exists(MINIDLNA_CONFIG_DIR):
            self.logger.debug("Creating config dir: {config_dir}...".format(config_dir=MINIDLNA_CONFIG_DIR))
            os.mkdir(MINIDLNA_CONFIG_DIR)

        if not os.path.exists(MINIDLNA_CACHE_DIR):
            self.logger.debug("Creating cache dir: {cache_dir}...".format(cache_dir=MINIDLNA_CACHE_DIR))
            os.mkdir(MINIDLNA_CACHE_DIR)

        last_modification = None
        if os.path.exists(MINIDLNA_CONFIG_FILE):
            last_modification = os.path.getmtime(MINIDLNA_CONFIG_FILE)

        if last_modification and self.last_reloaded and last_modification < self.last_reloaded:
            self.logger.debug("Config won't be reloaded because it hasn't changed.")
            return

        self.logger.debug("Reloading MiniDLNAconfiguration...")

        if not os.path.exists(MINIDLNA_CONFIG_FILE):

            self.logger.debug("Creating initial config file...")

            with codecs.open(MINIDLNA_CONFIG_FILE, "w", "utf-8") as f:
                home_dir = os.path.expanduser("~")
                f.write("db_dir={db_dir}\n".format(db_dir=MINIDLNA_CACHE_DIR))
                self.log = os.path.join(MINIDLNA_CONFIG_DIR, MINIDLNA_LOG_FILENAME)
                f.write("log_dir={log_dir}\n".format(log_dir=MINIDLNA_CONFIG_DIR))
                self.port = 8200+random.randint(1, 99)
                self.logger.debug("Setting port to {port}".format(port=self.port))
                f.write("port={port}\n".format(port=self.port))
                f.write("uuid={uuid}\n".format(uuid=str(uuid.uuid4())))
                f.write("friendly_name=" + _("Multimedia for {user}").format(user=getpass.getuser()) + "\n")

                download_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                if download_dir:
                    if download_dir != home_dir:
                        download_dir = download_dir.decode('utf-8')
                        self.logger.debug("Adding folder {folder} as downloads...".format(folder=download_dir))
                        f.write("media_dir={media_dir}\n".format(media_dir=download_dir))
                        self.dirs.append(MiniDLNADirectory(download_dir, MiniDLNAMediaType.MIXED))
                    else:
                        self.logger.debug("Detected download folder {folder} is the same as the home folder; ignoring.".format(folder=download_dir))
                else:
                    self.logger.debug("Couldn't detect download folder; ignoring.")

                pictures_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
                if pictures_dir:
                    if pictures_dir != home_dir:
                        pictures_dir = pictures_dir.decode('utf-8')
                        self.logger.debug("Adding folder {folder} as pictures...".format(folder=pictures_dir))
                        f.write("media_dir=P,{media_dir}\n".format(media_dir=pictures_dir))
                        self.dirs.append(MiniDLNADirectory(pictures_dir, MiniDLNAMediaType.PICTURES))
                    else:
                        self.logger.debug("Detected pictures folder {folder} is the same as the home folder; ignoring.".format(folder=pictures_dir))
                else:
                    self.logger.debug("Couldn't detect pictures folder; ignoring.")

                music_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC)
                if music_dir:
                    if music_dir != home_dir:
                        music_dir = music_dir.decode('utf-8')
                        self.logger.debug("Adding folder {folder} as music...".format(folder=music_dir))
                        f.write("media_dir=A,{media_dir}\n".format(media_dir=music_dir))
                        self.dirs.append(MiniDLNADirectory(music_dir, MiniDLNAMediaType.AUDIO))
                    else:
                        self.logger.debug("Detected music folder {folder} is the same as the home folder; ignoring.".format(folder=music_dir))
                else:
                    self.logger.debug("Couldn't detect music folder; ignoring.")

                videos_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)
                if videos_dir:
                    if videos_dir != home_dir:
                        videos_dir = videos_dir.decode('utf-8')
                        self.logger.debug("Adding folder {folder} as videos...".format(folder=videos_dir))
                        f.write("media_dir=V,{media_dir}\n".format(media_dir=videos_dir))
                        self.dirs.append(MiniDLNADirectory(videos_dir, MiniDLNAMediaType.VIDEO))
                    else:
                        self.logger.debug("Detected videos folder {folder} is the same as the home folder; ignoring.".format(folder=videos_dir))
                else:
                    self.logger.debug("Couldn't detect videos folder; ignoring.")

            self.last_reloaded = time.time()

        else:

            # Obtener los datos actuales del archivo de configuración
            self.logger.debug("Reading existing config file {config_file}...".format(config_file=MINIDLNA_CONFIG_FILE))
            with codecs.open(MINIDLNA_CONFIG_FILE, mode="r+", encoding="utf-8") as fp:
                uuid_file = None
                friendly_name = None
                log_dir = None
                db_dir = None
                for line in fp:
                    line = line.strip()
                    if line.startswith("#"):
                        continue
                    if line.startswith("port="):
                        port_str = re.sub(r'^port=', "", line)
                        try:
                            self.port = int(port_str)
                            self.logger.debug("Setting port to {port}...".format(port=self.port))
                        except Exception as ex:
                            self.logger.error("Error converting port {port} to integer: {error}".format(port=port_str, error=str(ex)))
                    elif line.startswith("db_dir="):
                        db_dir = re.sub(r'^db_dir=', "", line)
                        self.logger.debug("Setting db_dir to {db_dir}...".format(db_dir=db_dir))
                    elif line.startswith("log_dir="):
                        log_dir = re.sub(r'^log_dir=', "", line)
                        self.log = os.path.join(log_dir, MINIDLNA_LOG_FILENAME)
                        self.logger.debug("Setting log_dir to {log_dir}...".format(log_dir=self.log))
                    elif line.startswith("uuid="):
                        uuid_file = re.sub(r'^uuid=', "", line)
                        self.logger.debug("Setting uuid to {uuid}...".format(uuid=uuid_file))
                    elif line.startswith("friendly_name="):
                        friendly_name = re.sub(r'^friendly_name=', "", line)
                        self.logger.debug("Setting friendly_name to {friendly_name}...".format(friendly_name=friendly_name))
                    elif line.startswith("media_dir="):
                        line = re.sub(r'^media_dir=', '', line)
                        if line.startswith("A,"):
                            line = re.sub(r'^A,', '', line)
                            self.logger.debug("Adding audio folder {folder}...".format(folder=line))
                            self.dirs.append(MiniDLNADirectory(line, MiniDLNAMediaType.AUDIO))
                        elif line.startswith("P,"):
                            line = re.sub(r'^P,', '', line)
                            self.logger.debug("Adding pictures folder {folder}...".format(folder=line))
                            self.dirs.append(MiniDLNADirectory(line, MiniDLNAMediaType.PICTURES))
                        elif line.startswith("V,"):
                            line = re.sub(r'^V,', '', line)
                            self.logger.debug("Adding video folder {folder}...".format(folder=line))
                            self.dirs.append(MiniDLNADirectory(line, MiniDLNAMediaType.VIDEO))
                        elif line.startswith("PV,"):
                            line = re.sub(r'^PV,', '', line)
                            self.logger.debug("Adding pictures/video folder {folder}...".format(folder=line))
                            self.dirs.append(MiniDLNADirectory(line, MiniDLNAMediaType.PICTURESVIDEO))
                        else:
                            self.logger.debug("Adding mixed (no-type specified) folder {folder}...".format(folder=line))
                            self.dirs.append(MiniDLNADirectory(line, MiniDLNAMediaType.MIXED))

                if not uuid_file or not friendly_name or not log_dir or not db_dir or not self.port:
                    fp.write("\n")
                    if not uuid_file:
                        self.logger.info("No UUID specified in configuration file; generating one and saving to file...")
                        generated_uuid_file = str(uuid.uuid4())
                        self.logger.debug("UUID generated: {uuid}".format(uuid=generated_uuid_file))
                        fp.write("uuid={uuid}\n".format(uuid=generated_uuid_file))
                    if not friendly_name:
                        self.logger.info("No friendly_name specified in configuration file; generating one and saving to file...")
                        generated_friendly_name = _("Multimedia for {user}").format(user=getpass.getuser())
                        self.logger.debug("friendly_name generated: {friendly_name}".format(friendly_name=generated_friendly_name))
                        fp.write("friendly_name={friendly_name}\n".format(friendly_name=generated_friendly_name))
                    if not db_dir:
                        self.logger.info("No db_dir specified in configuration file; generating one and saving to file...")
                        fp.write("db_dir={db_dir}\n".format(db_dir=MINIDLNA_CACHE_DIR))
                    if not log_dir:
                        self.logger.info("No log_dir specified in configuration file; generating one and saving to file...")
                        fp.write("log_dir={log_dir}\n".format(log_dir=MINIDLNA_CONFIG_DIR))
                        self.log = os.path.join(MINIDLNA_CONFIG_DIR, MINIDLNA_LOG_FILENAME)
                    if not self.port:
                        self.logger.info("No port specified in configuration file; generating one and saving to file...")
                        self.port = 8200 + random.randint(1, 99)
                        self.logger.debug("Port generated: {port}".format(port=self.port))
                        fp.write("port={port}\n".format(port=self.port))

            self.last_reloaded = time.time()


class MiniDLNAMediaType(enum.Enum):
    AUDIO = "audio"
    VIDEO = "video"
    PICTURES = "pictures"
    PICTURESVIDEO = "picturesvideo"
    MIXED = "mixed"


class MiniDLNADirectory(object):
    """
    :type path: str
    :type media_type: MiniDLNAMediaType
    """
    def __init__(self, path: str, media_type: MiniDLNAMediaType) -> None:
        self.path = path
        self.media_type = media_type


    @property
    def description(self) -> str:
        if self.media_type == MiniDLNAMediaType.AUDIO:
            return _("Audio")
        elif self.media_type == MiniDLNAMediaType.VIDEO:
            return _("Video")
        elif self.media_type == MiniDLNAMediaType.PICTURES:
            return _("Pictures")
        elif self.media_type == MiniDLNAMediaType.PICTURESVIDEO:
            return _("Pictures/Video")
        elif self.media_type == MiniDLNAMediaType.MIXED:
            return _("Mixed")
        else:
            return _("Unknown")


    @property
    def accessable(self) -> bool:
        return os.path.exists(self.path) and os.path.isdir(self.path) and os.access(self.path, os.R_OK)
