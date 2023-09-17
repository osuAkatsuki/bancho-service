from __future__ import annotations

import time

from objects import glob

DEFAULT_LOCK_EXPIRY = 10  # in seconds
DEFAULT_RETRY_DELAY = 0.05  # in seconds


class redisLock:
    def __init__(self, key: str) -> None:
        self.key = key

    def _try_acquire(self, expiry: float) -> bool | None:
        return glob.redis.set(self.key, "1", ex=expiry, nx=True)

    def acquire(
        self,
        expiry: float = DEFAULT_LOCK_EXPIRY,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        while not self._try_acquire(expiry):
            time.sleep(retry_delay)

    def release(self) -> None:
        glob.redis.delete(self.key)

    def __enter__(self) -> None:
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
