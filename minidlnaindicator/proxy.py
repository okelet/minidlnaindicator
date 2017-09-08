
from typing import  Optional, List

import fnmatch
import logging
import urllib


class Proxy(object):

    def __init__(self, host: str=None, port: int=0, username: Optional[str]=None, password: Optional[str]=None, exceptions: Optional[List[str]]=[]) -> None:
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exceptions = exceptions


    def to_url(self, include_password: bool=False) -> str:
        proxy = "http://"
        if self.username and self.password:
            proxy += urllib.quote(self.username) + ":" + (urllib.quote(self.password) if include_password else "*******") + "@"
        elif self.username:
            proxy += urllib.quote(self.username) + "@"
        elif self.password:
            proxy += (urllib.quote(self.password) if include_password else "*******") + "@"
        proxy += self.host + ":" + str(self.port)
        return proxy


    def allows_url(self, url: str) -> bool:
        self.logger.debug("Checking if proxy %s is valid for URL %s...", self.to_url(), url)
        return self.allows_host(urllib.parse.urlparse(url).hostname)


    def allows_host(self, host: str) -> bool:

        self.logger.debug("Checking if proxy %s is valid for host %s...", self.to_url(), host)
        for exception in self.exceptions:
            if fnmatch.fnmatch(host, exception):
                self.logger.debug("Host %s found in exception %s, ignoring proxy...", host, exception)
                return False

        self.logger.debug("Host not in exceptions; returning proxy %s...", self.to_url())
        return True


    def __repr__(self) -> str:
        return self.to_url()
