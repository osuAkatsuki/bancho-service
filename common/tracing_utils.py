from __future__ import annotations

import logging
import os.path
import sys


def tracef(f):
    def tracef(*args, **kwargs):
        # print where this is being called from
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
