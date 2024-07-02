from __future__ import annotations

import functools
import logging
import os.path
import sys
from collections.abc import Callable
from typing import ParamSpec
from typing import TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def tracef(f: Callable[P, R]) -> Callable[P, R]:
    """A helper to understand where functions are being called."""

    @functools.wraps(f)
    def tracef(*args: P.args, **kwargs: P.kwargs) -> R:
        caller_frame = sys._getframe(1)
        logging.info(
            "Traced function",
            extra={
                "function": f.__name__,
                "file": os.path.basename(caller_frame.f_code.co_filename),
                "line": caller_frame.f_lineno,
            },
        )
        return f(*args, **kwargs)

    return tracef
