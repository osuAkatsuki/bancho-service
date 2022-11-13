from __future__ import annotations

from typing import Callable
from typing import List
from typing import Optional

import tornado.ioloop
from datadog import initialize
from datadog import ThreadStats

from objects import glob


class periodicCheck:
    def __init__(self, name: str, checkFunction: Callable) -> None:
        """
        Initialize a periodic check object

        :param name: Datadog stat name, without prefix
        :param checkFunction: Function that returns the data to report. Eg: `lambda: len(something)`
        """
        self.name = f"{glob.DATADOG_PREFIX}.{name}"
        self.checkFunction = checkFunction


class datadogClient:
    def __init__(
        self,
        apiKey: Optional[str] = None,
        appKey: Optional[str] = None,
        periodicChecks: Optional[List[periodicCheck]] = None,
        constant_tags: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize a toggleable Datadog Client

        :param apiKey: Datadog api key. Leave empty to create a dummy (disabled) Datadog client.
        :param appKey: Datadog app key. Leave empty to create a dummy (disabled) Datadog client.
        :param periodicChecks: List of periodicCheck objects. Optional. Leave empty to disable periodic checks.
        """
        if apiKey and appKey:
            initialize(api_key=apiKey, app_key=appKey)
            self.client = ThreadStats(constant_tags=constant_tags)
            self.client.start()
            self.periodicChecks = periodicChecks
            if self.periodicChecks:
                tornado.ioloop.PeriodicCallback(
                    self.__periodicCheckLoop,
                    10 * 1000,
                ).start()
        else:
            self.client = None

    def increment(self, *args, **kwargs) -> None:
        """
        Call self.client.increment(*args, **kwargs) if this client is not a dummy

        :param args:
        :param kwargs:
        :return:
        """
        if self.client:
            self.client.increment(*args, **kwargs)

    def gauge(self, *args, **kwargs) -> None:
        """
        Call self.client.gauge(*args, **kwargs) if this client is not a dummy

        :param args:
        :param kwargs:
        :return:
        """
        if self.client:
            self.client.gauge(*args, **kwargs)

    def __periodicCheckLoop(self) -> None:
        """Report periodic data to datadog."""
        if self.periodicChecks is not None:
            for i in self.periodicChecks:
                self.gauge(i.name, i.checkFunction())
