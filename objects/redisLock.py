from __future__ import annotations

import time
from typing import Optional

from objects import glob


class redisLock:
    def __init__(self, key: str) -> None:
        self.key = key

    def is_locked(self) -> bool:
        is_locked = False

        lock_bytes: Optional[bytes] = glob.redis.get(self.key)
        if lock_bytes is not None:
            is_locked = lock_bytes.decode() == "1"

        return is_locked

    def wait_for_release(self) -> None:
        while self.is_locked():
            time.sleep(0.01)

    def acquire(self) -> None:
        self.wait_for_release()
        glob.redis.set(self.key, "1")

    def release(self) -> None:
        glob.redis.delete(self.key)

    def __enter__(self) -> None:
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
