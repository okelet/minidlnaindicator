
from typing import List


class FSListener(object):

    def on_fs_changed(self, new_filesystems: List[str]) -> None:
        raise NotImplementedError()
