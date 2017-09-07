
from typing import List, Optional

import logging
import os
import subprocess
import threading
import time

from .constants import APPINDICATOR_ID, LOCALE_DIR
from .processlistener import ProcessListener
from .exceptions.processstop import ProcessStopException
from .exceptions.processnotrunning import ProcessNotRunningException

import gettext
_ = gettext.translation(APPINDICATOR_ID, LOCALE_DIR, fallback=True).gettext


class ProcessRunner(object):

    def __init__(self) -> None:

        self._logger = logging.getLogger(__name__)

        self.pid = 0
        self._run_thread = None  # type: Optional[threading.Thread]
        self._listeners = []  # type: List[ProcessListener]


    def add_listener(self, listener: ProcessListener) -> bool:
        if listener not in self._listeners:
            self._listeners.append(listener)
            return True
        return False


    def remove_listener(self, listener: ProcessListener) -> bool:
        if listener in self._listeners:
            self._listeners.remove(listener)
            return True
        return False


    def is_running(self) -> bool:
        if self._run_thread and self._run_thread.is_alive():
            return True
        else:
            return False


    def stop(self) -> bool:

        if not self.pid:
            raise ProcessNotRunningException()

        self._logger.debug("Stopping process with PID %s...", self.pid)
        try:
            os.kill(self.pid, 15)
        except OSError as ex:
            raise ProcessStopException(str(ex))

        # Wait to the process to die
        finish_time = time.time() + 5
        while time.time() < finish_time:
            if self.pid:
                time.sleep(0.2)
            else:
                killed = True
                break

        if killed:
            return True
        else:
            return False


    def start(self, command: List[str], ignore_running: bool=False) -> None:

        if self.is_running() and not ignore_running:
            raise RuntimeError()

        self._run_thread = threading.Thread(target=self._start_blocking, kwargs={"command": command})
        self._run_thread.start()


    def _start_blocking(self, command: List[str]) -> None:

        self._logger.debug("Notifying before starting...")
        for listener in self._listeners:
            listener.on_process_starting()

        try:

            self._logger.debug("Starting process: %s...", command)
            pipes = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.pid = pipes.pid

            self._logger.debug("Notifying process started with PID %s...", self.pid)
            for listener in self._listeners:
                listener.on_process_started(self.pid)

            std_out, std_err = pipes.communicate()
            exit_code = pipes.returncode

            self._logger.debug("Notifying process finished; PID: %s, exit code: %s...", self.pid, exit_code)
            pid = self.pid
            self.pid = 0
            for listener in self._listeners:
                listener.on_process_finished(command, pid, exit_code, std_out, std_err)

        except Exception as ex:
            self._logger.exception("Error running command %s: %s.", command, ex)
            for listener in self._listeners:
                listener.on_process_error(str(ex))
