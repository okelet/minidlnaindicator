
from typing import Optional


class ProcessListener(object):

    def on_process_starting(self) -> None:
        raise NotImplementedError()


    def on_process_started(self, pid: int) -> None:
        raise NotImplementedError()


    def on_process_finished(self, pid: int, exit_code: int, std_out: Optional[str], std_err: Optional[str]) -> None:
        raise NotImplementedError()


    def on_process_error(self, reason: str) -> None:
        raise NotImplementedError()
