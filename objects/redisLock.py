from __future__ import annotations

import time
from types import TracebackType
from typing import Optional

from objects import glob

LOCK_EXPIRY = 10  # in seconds
RETRY_DELAY = 0.05  # in seconds


class redisLock:
    def __init__(self, key: str) -> None:
        self.key = key

    def try_acquire(self) -> Optional[bool]:
        return glob.redis.set(self.key, "1", ex=LOCK_EXPIRY, nx=True)

    def acquire(self) -> None:
        while not self.try_acquire():
            time.sleep(RETRY_DELAY)

    def release(self) -> None:
        glob.redis.delete(self.key)

    def __enter__(self) -> None:
        self.acquire()

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.release()
