
from typing import Tuple, List

import subprocess


def run_command(command: List[str], shell: bool=False) -> Tuple[int, int, str, str]:
    pipes = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell, universal_newlines=True)
    pid = pipes.pid
    std_out, std_err = pipes.communicate()
    return pid, pipes.returncode, std_out, std_err
