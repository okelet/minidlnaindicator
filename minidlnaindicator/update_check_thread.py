
from typing import List

import logging
import xmlrpc.client
import threading

from .update_check_listener import UpdateCheckListener
from .version import __version__ as module_version


class UpdateCheckConfig(object):

    def __init__(self) -> None:
        self.excluded_interfaces_regexps = []  # type: List[str]
        self.time_between_update_checks = 1800


class UpdateCheckThread(threading.Thread):

    def __init__(self, config: UpdateCheckConfig) -> None:

        threading.Thread.__init__(self)

        self._logger = logging.getLogger(__name__)
        self.config = config
        self._stop_signal = threading.Event()
        self._listeners = []  # type: List[UpdateCheckListener]


    def add_listener(self, listener: UpdateCheckListener) -> bool:
        if not listener in self._listeners:
            self._listeners.append(listener)
            return True
        return False


    def remove_listener(self, listener: UpdateCheckListener) -> bool:
        if listener in self._listeners:
            self._listeners.remove(listener)
            return True
        return False


    def run(self) -> None:

        self._logger.debug("Starting update check thread...")

        self._stop_signal.clear()

        # Wait 120 seconds before the first update check
        self._stop_signal.wait(120)

        while not self._stop_signal.is_set():

            self._logger.debug("Checking for new version...")
            try:

                pypi = xmlrpc.client.ServerProxy("https://pypi.python.org/pypi")
                available = pypi.package_releases("minidlnaindicator")
                if not available:
                    self._logger.error("Porject minidlnaindicator not found in PyPi.")
                else:

                    latest_version = available[0]
                    self._logger.debug("Versions detected: %s", available)
                    self._logger.debug("Latest version: %s", latest_version)
                    if latest_version != module_version:
                        self._logger.info("New version available; current: %s, new: %s", module_version, latest_version)
                        for listener in self._listeners:
                            listener.on_update_detected(latest_version)

            except Exception as ex:
                self._logger.exception("Exception when checking for updates: %s", ex)

            self._stop_signal.wait(self.config.time_between_update_checks)

        self._logger.debug("Update check thread finished.")


    def stop(self) -> None:

        self._logger.debug("Stopping update check thread...")
        self._stop_signal.set()
