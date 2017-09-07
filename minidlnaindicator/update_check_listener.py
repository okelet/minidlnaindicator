
class UpdateCheckListener(object):

    def on_update_detected(self, new_version: str) -> None:
        raise NotImplementedError()
