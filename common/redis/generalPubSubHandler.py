from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any


class WrongStructureError(Exception):
    pass


class generalPubSubHandler(ABC):
    __slots__ = ("structure", "type", "strict")

    def __init__(self) -> None:
        self.structure = {}
        self.type = "int"
        self.strict = True

    @abstractmethod
    async def handle(self, raw_data: bytes) -> None: ...

    def parseData(self, raw_data: bytes) -> Any:
        """
        Parse received data

        :param data: received data, as bytes array
        :return: parsed data or None if it's invalid
        """
        if self.type == "int":
            data = int(raw_data.decode("utf-8"))
        elif self.type == "int_list":
            data = [int(i) for i in raw_data.decode().split(",")]
        else:
            raise NotImplementedError("Unknown data type")

        return data
