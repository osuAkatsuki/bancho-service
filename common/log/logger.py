from __future__ import annotations

import logging
from collections.abc import Mapping
from contextvars import ContextVar
from types import TracebackType
from typing import Any
from typing import Optional
from typing import TypeAlias
from typing import Union

LOG_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "LOG_CONTEXT",
    default=None,
)

_SysExcInfoType: TypeAlias = Union[
    tuple[type[BaseException], BaseException, Optional[TracebackType]],
    tuple[None, None, None],
]
ExcInfoType: TypeAlias = Optional[Union[bool, _SysExcInfoType, BaseException]]


def add_context(**kwargs: Any) -> None:
    log_context = LOG_CONTEXT.get()
    if log_context is None:
        log_context = {}
        LOG_CONTEXT.set(log_context)
    log_context.update(kwargs)


def _log(
    levelname: str,
    msg: object,
    *args: object,
    exc_info: ExcInfoType = None,
    stack_info: bool = False,
    stacklevel: int = 1,
    extra: Mapping[str, object] | None = None,
) -> None:
    log_context = LOG_CONTEXT.get()
    if log_context is None:
        log_context = {}
        LOG_CONTEXT.set(log_context)
    else:
        extra = dict(extra) if extra is not None else {}
        extra.update(log_context)
    logging.log(
        logging.getLevelName(levelname),
        msg,
        *args,
        exc_info=exc_info,
        stack_info=stack_info,
        stacklevel=stacklevel,
        extra=extra,
    )


def debug(
    msg: object,
    *args: object,
    exc_info: ExcInfoType = None,
    stack_info: bool = False,
    stacklevel: int = 1,
    extra: Mapping[str, object] | None = None,
) -> None:
    return _log(
        "DEBUG",
        msg,
        *args,
        exc_info=exc_info,
        stack_info=stack_info,
        stacklevel=stacklevel,
        extra=extra,
    )


def info(
    msg: object,
    *args: object,
    exc_info: ExcInfoType = None,
    stack_info: bool = False,
    stacklevel: int = 1,
    extra: Mapping[str, object] | None = None,
) -> None:
    return _log(
        "INFO",
        msg,
        *args,
        exc_info=exc_info,
        stack_info=stack_info,
        extra=extra,
    )


def warning(
    msg: object,
    *args: object,
    exc_info: ExcInfoType = None,
    stack_info: bool = False,
    stacklevel: int = 1,
    extra: Mapping[str, object] | None = None,
) -> None:
    return _log(
        "WARNING",
        msg,
        *args,
        exc_info=exc_info,
        stack_info=stack_info,
        extra=extra,
    )


def error(
    msg: object,
    *args: object,
    exc_info: ExcInfoType = None,
    stack_info: bool = False,
    stacklevel: int = 1,
    extra: Mapping[str, object] | None = None,
) -> None:
    return _log(
        "ERROR",
        msg,
        *args,
        exc_info=exc_info,
        stack_info=stack_info,
        extra=extra,
    )


def exception(
    msg: object,
    *args: object,
    exc_info: ExcInfoType = True,
    stack_info: bool = False,
    stacklevel: int = 1,
    extra: Mapping[str, object] | None = None,
) -> None:
    return _log(
        "ERROR",
        msg,
        *args,
        exc_info=exc_info,
        stack_info=stack_info,
        extra=extra,
    )
