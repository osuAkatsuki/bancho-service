from __future__ import annotations

import functools
import logging
import os.path
import sys
import time
from collections.abc import Awaitable
from collections.abc import Callable
from typing import ParamSpec
from typing import TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def tracef(f: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """A helper to understand where functions are being called."""

    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Awaitable[R]:
        caller_frame = sys._getframe(1)

        async def async_wrapper() -> R:
            st = time.time()
            value = await f(*args, **kwargs)
            et = time.time()

            file = os.path.basename(caller_frame.f_code.co_filename)
            line = caller_frame.f_lineno
            logging.info(
                "Traced function execution",
                extra={
                    "function": f.__name__,
                    "execution_time_ms": (et - st) * 1000,
                    "code_location": f"{file}:{line}",
                },
            )
            return value

        return async_wrapper()

    return wrapper
