
from typing import List

import logging
import psutil
import threading

from .fslistener import FSListener


class FSMonitorThread(threading.Thread):

    def __init__(self) -> None:

        threading.Thread.__init__(self)

        self._logger = logging.getLogger(__name__)

        self._stop_signal = threading.Event()

        self._listeners = []  # type: List[FSListener]


    def add_listener(self, listener: FSListener) -> bool:
        if not listener in self._listeners:
            self._listeners.append(listener)
            return True
        return False


    def remove_listener(self, listener: FSListener) -> bool:
        if listener in self._listeners:
            self._listeners.remove(listener)
            return True
        return False


    def run(self) -> None:

        self._logger.debug("Starting FS check thread...")

        self._stop_signal.clear()
        previous_filesystems = None
        while not self._stop_signal.is_set():

            current_filesystems = sorted([x.mountpoint for x in psutil.disk_partitions()])

            if previous_filesystems != None and previous_filesystems != current_filesystems:
                self._logger.debug(
                    "Detected FS change; old: %s; new: %s; notifying...",
                    previous_filesystems,
                    current_filesystems
                )
                for listener in self._listeners:
                    listener.on_fs_changed(current_filesystems)

            previous_filesystems = current_filesystems

            self._stop_signal.wait(10)

        self._logger.debug("FS check thread finished.")


    def stop(self) -> None:

        self._logger.debug("Stopping FS check thread...")
        self._stop_signal.set()
