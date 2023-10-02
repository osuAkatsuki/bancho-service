from __future__ import annotations

import time
from types import TracebackType
from typing import Optional

from objects import glob

DEFAULT_LOCK_EXPIRY = 10  # in seconds
DEFAULT_RETRY_DELAY = 0.05  # in seconds


class redisLock:
    def __init__(self, key: str) -> None:
        self.key = key

    async def _try_acquire(self, expiry: float) -> Optional[bool]:
        return await glob.redis.set(self.key, "1", ex=expiry, nx=True)

    async def acquire(
        self,
        expiry: float = DEFAULT_LOCK_EXPIRY,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        while not await self._try_acquire(expiry):
            time.sleep(retry_delay)

    async def release(self) -> None:
        await glob.redis.delete(self.key)

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.release()
