
from typing import Dict, Any

import codecs
import logging
import os
import yaml


class MiniDLNAIndicatorConfig(object):

    def __init__(self, filename: str) -> None:
        self.logger = logging.getLogger(__name__)
        self.filename = filename
        self.startup_indicator = True
        self.load()


    def load(self) -> None:

        if os.path.exists(self.filename):
            with codecs.open(self.filename, "r", "utf-8") as f:
                data = yaml.load(f)
                self.startup_indicator = data.get("startup_indicator", False)
                self.logger.debug("Startup indicator: {value}".format(value=self.startup_indicator))
        else:
            self.logger.info("Config file doesn't exist.")


    def save(self) -> None:

        data = {}  # type: Dict[str, Any]

        data["startup_indicator"] = self.startup_indicator

        with codecs.open(self.filename, "w", "utf-8") as f:
            yaml.dump(data, f)
