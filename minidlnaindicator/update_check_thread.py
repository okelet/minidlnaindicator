
from typing import List, Optional

import logging
import requests
import threading

from .update_check_listener import UpdateCheckListener


class UpdateCheckConfig(object):

    def __init__(self) -> None:
        self.time_between_update_checks = 1800


class UpdateCheckThread(threading.Thread):

    def __init__(self, config: UpdateCheckConfig, package_name: str, current_version: str, test_mode: str) -> None:

        threading.Thread.__init__(self)

        self._logger = logging.getLogger(__name__)

        self.config = config
        self.package_name = package_name
        self.current_version = current_version
        self.test_mode = test_mode

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
        if self.test_mode:
            self._stop_signal.wait(10)
        else:
            self._stop_signal.wait(120)

        previous_fetched_version = None
        while not self._stop_signal.is_set():

            self._logger.debug("Checking for new version...")
            try:

                if self.test_mode:
                    pypi_url = "https://testpypi.python.org/pypi"
                else:
                    pypi_url = "https://pypi.python.org/pypi"
                proxy = self.config.detect_proxy()

                self._logger.debug("Getting package info from %s...", pypi_url)
                package_url = "{pypi_url}/{package_name}/json".format(pypi_url=pypi_url, package_name=self.package_name)
                response = requests.get(
                    package_url,
                    timeout=5,
                    proxies={
                        "http": proxy.to_url(include_password=True) if proxy and proxy.allows_url(pypi_url) else None,
                        "https": proxy.to_url(include_password=True) if proxy and proxy.allows_url(pypi_url) else None,
                    }
                )
                if response.status_code == requests.codes.not_found:
                    self._logger.error("Package %s not found.", self.package_name)
                elif response.status_code != requests.codes.ok:
                    self._logger.error("Invalid response: %s.", response.status_code)
                else:
                    try:
                        latest_version = response.json().get("info", {}).get("version")
                        if not latest_version:
                            self._logger.error("No version available in response.")
                        else:
                            self._logger.debug("Latest version: %s", latest_version)
                            if latest_version == self.current_version:
                                self._logger.debug("Package up to date.")
                            elif latest_version < self.current_version:
                                self._logger.error("Current version (%s) is newer than Pypi version (%s).", self.current_version, latest_version)
                            else:
                                if not previous_fetched_version or previous_fetched_version < latest_version:
                                    previous_fetched_version = latest_version
                                    self._logger.info("New version detected; current: %s, new: %s", self.current_version, latest_version)
                                    for listener in self._listeners:
                                        listener.on_update_detected(latest_version)
                    except ValueError as ve:
                        self._logger.exception("Error getting the JSON response: %s", ve)

            except Exception as ex:
                self._logger.exception("Exception when checking for updates: %s", ex)

            if self.test_mode:
                # In test mode, we wait only 30 seconds
                self._stop_signal.wait(30)
            else:
                # In normal mode, we weit the time configured, normally, 1800 seconds
                self._stop_signal.wait(self.config.time_between_update_checks)

        self._logger.debug("Update check thread finished.")


    def stop(self) -> None:

        self._logger.debug("Stopping update check thread...")
        self._stop_signal.set()
