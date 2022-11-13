from __future__ import annotations

import json
from typing import Optional


def shape(d: dict) -> dict:
    """
    Returns a shape of a dictionary.
    Used to check if two dictionaries have the same structure

    :param d: dictionary
    :return: `d`'s shape
    """
    if isinstance(d, dict):
        return {k: shape(d[k]) for k in d}


class wrongStructureError(Exception):
    pass


class generalPubSubHandler:
    __slots__ = ("structure", "type", "strict")

    def __init__(self) -> None:
        self.structure = {}
        self.type = "json"
        self.strict = True

    def parseData(self, data: bytes) -> Optional[object]:
        """
        Parse received data

        :param data: received data, as bytes array
        :return: parsed data or None if it's invalid
        """
        if self.type == "json":
            data = json.loads(data.decode("utf-8"))
            if shape(data) != shape(self.structure) and self.strict:
                raise wrongStructureError()
        elif self.type == "int":
            data = int(data.decode("utf-8"))
        elif self.type == "int_list":
            data = [int(i) for i in data.decode().split(",")]

        return data
