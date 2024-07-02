from __future__ import annotations

import cProfile
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


# (global state, referenced elsewhere)
profiler = cProfile.Profile()


def tracef(f: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """A helper to understand where functions are being called."""

    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Awaitable[R]:
        caller_frame = sys._getframe(1)
        second_caller_frame = sys._getframe(2)
        third_caller_frame = sys._getframe(3)

        async def async_wrapper() -> R:
            st = time.time()
            value = await f(*args, **kwargs)
            et = time.time()

            file = os.path.basename(caller_frame.f_code.co_filename)
            line = caller_frame.f_lineno

            second_file = os.path.basename(second_caller_frame.f_code.co_filename)
            second_line = second_caller_frame.f_lineno

            third_file = os.path.basename(third_caller_frame.f_code.co_filename)
            third_line = third_caller_frame.f_lineno

            logging.info(
                "Traced function execution",
                extra={
                    "function": f.__name__,
                    "execution_time_ms": (et - st) * 1000,
                    "code_location": f"{file}:{line}",
                    "second_code_location": f"{second_file}:{second_line}",
                    "third_code_location": f"{third_file}:{third_line}",
                },
            )
            return value

        return async_wrapper()

    return wrapper
