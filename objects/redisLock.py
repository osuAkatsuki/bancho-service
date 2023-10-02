from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Optional

from objects import glob

LOCK_EXPIRY = 10  # in seconds
RETRY_DELAY = 0.05  # in seconds


class redisLock:
    def __init__(self, key: str) -> None:
        self.key = key

    async def try_acquire(self) -> Optional[bool]:
        return await glob.redis.set(self.key, "1", ex=LOCK_EXPIRY, nx=True)

    async def acquire(self) -> None:
        while not await self.try_acquire():
            await asyncio.sleep(RETRY_DELAY)

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
