from __future__ import annotations

from abc import ABC
from abc import abstractmethod


class AbstractPubSubHandler(ABC):
    @abstractmethod
    async def handle(self, raw_data: bytes) -> None: ...
