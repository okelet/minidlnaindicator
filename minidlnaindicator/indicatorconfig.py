
from typing import Dict, Any, Optional, Tuple, List

import codecs
import fnmatch
import logging
import os
import json
import urllib

from gi.repository import Gio

from .constants import XDG_CONFIG_DIR, XDG_AUTOSTART_DIR, XDG_AUTOSTART_FILE, APPINDICATOR_ID, LOCALE_DIR, LOG_LEVELS, MINIDLNA_INDICATOR_CONFIG, MINIDLNA_CONFIG_DIR
from .update_check_thread import UpdateCheckConfig
from .proxy import Proxy

import gettext
_ = gettext.translation(APPINDICATOR_ID, LOCALE_DIR, fallback=True).gettext


class MiniDLNAIndicatorConfig(UpdateCheckConfig):

    def __init__(self, config_file: str, cmd_log_level: Optional[str]=None) -> None:

        self.logger = logging.getLogger(__name__)

        UpdateCheckConfig.__init__(self)

        self.cmd_log_level = cmd_log_level

        if config_file and config_file != MINIDLNA_INDICATOR_CONFIG:
            if not os.path.exists(config_file):
                raise Exception(_("The file {file} doesn't exist.").format(file=config_file))
            elif not os.path.isfile(config_file):
                raise Exception(_("The file {file} is not a file.").format(file=config_file))
            elif not os.access(config_file, os.R_OK):
                raise Exception(_("The file {file} doesn't exist.").format(file=config_file))
            else:
                self.config_file = config_file
        else:
            if not os.path.exists(MINIDLNA_CONFIG_DIR):
                os.mkdir(MINIDLNA_CONFIG_DIR)
            self.config_file = MINIDLNA_INDICATOR_CONFIG

        data = {}  # type: dict
        if os.path.exists(self.config_file):
            self.logger.debug("Loading configuration from file %s...", self.config_file)
            try:
                with codecs.open(self.config_file, 'r', 'utf-8') as fp:
                    data = json.load(fp)
            except Exception as ex:
                raise Exception(_("Error loading the configuration: {error}.").format(error=str(ex)))

        self._auto_start = True
        self.auto_start = data.get("auto_start", True)

        self.enable_orphan_process_killer = data.get("enable_orphan_process_killer", True)
        self.time_between_update_checks = data.get("time_between_update_checks", 1800)

        self._log_level = "error"
        log_level = data.get("log_level")
        if log_level and not log_level in LOG_LEVELS.keys():
            self.logger.error("Invalid log level %s found in configuration; defaulting to error...", log_level)
            log_level = "error"
        self.log_level = log_level


    @property
    def auto_start(self) -> bool:
        return self._auto_start


    @auto_start.setter
    def auto_start(self, auto_start: bool) -> None:
        self._auto_start = auto_start
        self.set_xdg_autostart(self._auto_start)


    def set_xdg_autostart(self, enabled: bool) -> None:

        # ~/.config
        if not os.path.exists(XDG_CONFIG_DIR):
            os.mkdir(XDG_CONFIG_DIR)

        # ~/.config/autostart
        if not os.path.exists(XDG_AUTOSTART_DIR):
            os.mkdir(XDG_AUTOSTART_DIR)

        with codecs.open(XDG_AUTOSTART_FILE, "w", "utf-8") as f:
            f.write("[Desktop Entry]\n")
            f.write("Encoding = UTF-8\n")
            f.write("Type = Application\n")
            f.write("Name = " + _("MiniDLNA Indicator") + "\n")
            f.write("Exec = minidlnaindicator\n")
            f.write("Icon = minidlnaindicator\n")
            f.write("Comment = " + _("Indicator for launching MiniDLNA as a normal user") + "\n")
            f.write("X-GNOME-Autostart-enabled = {value}\n".format(value='true' if enabled else 'false'))
            f.write("Terminal = false\n")


    @property
    def log_level(self) -> str:
        return self._log_level


    @log_level.setter
    def log_level(self, value: str) -> None:

        log_value = LOG_LEVELS.get(value)
        if not log_value:
            self.logger.error("Trying to set invalid log level: %s; defaulting to error...", value)
            value = "error"
            log_value = logging.ERROR

        self._log_level = value
        if not self.cmd_log_level:
            self.logger.info("Updating runtime log level to %s...", value)
            logging.getLogger("minidlnaindicator").setLevel(log_value)


    def to_dict(self) -> Dict:

        data = {}  # type: Dict[str, Any]

        if not self._auto_start:
            data["auto_start"] = False

        if not self.enable_orphan_process_killer:
            data["enable_orphan_process_killer"] = False

        if self.time_between_update_checks != 1800:
            data["time_between_update_checks"] = self.time_between_update_checks

        if self._log_level and self._log_level != "error":
            data["log_level"] = self._log_level

        return data


    def save(self, reason: Optional[str]=None) -> None:

        if reason:
            self.logger.info("Saving configuration ({reason})...".format(reason=reason))
        else:
            self.logger.info("Saving configuration (no reason)...")

        try:

            config_dir = os.path.dirname(self.config_file)
            if not os.path.exists(config_dir):
                os.mkdir(config_dir)

            cnf_data = self.to_dict()
            with codecs.open(self.config_file, 'w', 'utf-8') as outfile:
                json.dump(cnf_data, outfile, indent=4, sort_keys=True)

        except Exception as ex:
            raise Exception(_("Exception saving the configuration: {error}.").format(error=str(ex)))


    def detect_proxy(self) -> Optional[Proxy]:

        self.logger.debug("Detecting environment proxy...")
        current_env_proxy = os.getenv("http_proxy", os.getenv("HTTP_PROXY"))
        if not current_env_proxy:
            os.getenv("https_proxy", os.getenv("HTTPS_PROXY"))
        if not current_env_proxy:
            os.getenv("ftp_proxy", os.getenv("FTP_PROXY"))
        if current_env_proxy:
            url = urllib.parse.urlparse(current_env_proxy)
            p = Proxy()
            p.host = url.hostname
            p.port = url.port
            p.username = url.username
            p.password = url.password
            no_proxy = os.getenv("no_proxy", os.getenv("NO_PROXY"))
            if no_proxy:
                p.exceptions = [x.strip() for x in no_proxy.split(",") if x.strip()]
            self.logger.info("Found proxy in environment: %s", p.to_url())
            return p

        self.logger.debug("Detecting gnome proxy settings...")
        mode = Gio.Settings.new("org.gnome.system.proxy").get_string("mode")
        if mode == "manual":
            current_gnome_proxy = Gio.Settings.new("org.gnome.system.proxy.http").get_string("host")
            current_gnome_port = Gio.Settings.new("org.gnome.system.proxy.http").get_int("port")
            if not current_gnome_proxy:
                current_gnome_proxy = Gio.Settings.new("org.gnome.system.proxy.https").get_string("host")
                current_gnome_port = Gio.Settings.new("org.gnome.system.proxy.https").get_int("port")
            if not current_gnome_proxy:
                current_gnome_proxy = Gio.Settings.new("org.gnome.system.proxy.ftp").get_string("host")
                current_gnome_port = Gio.Settings.new("org.gnome.system.proxy.ftp").get_int("port")
            if current_gnome_proxy and current_gnome_port:
                p = Proxy()
                p.host = current_gnome_proxy
                p.port = current_gnome_port
                p.exceptions = Gio.Settings.new("org.gnome.system.proxy").get_strv("ignore-hosts")
                self.logger.info("Found proxy in gnome: %s", p.to_url())
                return p

        return None

