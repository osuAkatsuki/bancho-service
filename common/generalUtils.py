from __future__ import annotations
from typing import Optional

from common.constants import mods as Mods


def secondsToReadable(seconds: int) -> str:
    r: list[str] = []

    days, seconds = divmod(seconds, 60 * 60 * 24)
    if days:
        r.append(f"{days:02d}")

    hours, seconds = divmod(seconds, 60 * 60)
    if hours:
        r.append(f"{hours:02d}")

    minutes, seconds = divmod(seconds, 60)
    r.append(f"{minutes:02d}")

    r.append(f"{seconds % 60:02d}")
    return ":".join(r)


def stringToBool(s: str) -> bool:
    """Convert a string (True/true/1) to bool"""
    return s in {"True", "true", "1", 1}


def getRank(
    *,
    gameMode: int,
    mods: int,
    acc: float,
    c300: int,
    c100: int,
    c50: int,
    cmiss: int,
) -> str:
    """
    Return a string with rank/grade for a given score.
    Used mainly for tillerino

    :param gameMode: game mode number
    :param mods: mods value
    :param acc: accuracy
    :param c300: 300 hit count
    :param c100: 100 hit count
    :param c50: 50 hit count
    :param cmiss: misses count
    :return: rank/grade string
    """
    total = c300 + c100 + c50 + cmiss
    hdfl = (mods & (Mods.HIDDEN | Mods.FLASHLIGHT)) > 0

    if gameMode == 0:
        # osu!
        if acc == 100:
            return "XH" if hdfl else "X"
        if c300 / total > 0.90 and c50 / total < 0.1 and cmiss == 0:
            return "SH" if hdfl else "S"
        if (c300 / total > 0.80 and cmiss == 0) or (c300 / total > 0.90):
            return "A"
        if (c300 / total > 0.70 and cmiss == 0) or (c300 / total > 0.80):
            return "B"
        if c300 / total > 0.60:
            return "C"
        return "D"
    elif gameMode == 1:
        # TODO: osu!taiko
        return "A"
    elif gameMode == 2:
        # osu!catch
        if acc == 100:
            return "XH" if hdfl else "X"
        if 98.01 <= acc <= 99.99:
            return "SH" if hdfl else "S"
        if 94.01 <= acc <= 98.00:
            return "A"
        if 90.01 <= acc <= 94.00:
            return "B"
        if 85.01 <= acc <= 90.00:
            return "C"
        return "D"
    elif gameMode == 3:
        # osu!mania
        if acc == 100:
            return "XH" if hdfl else "X"
        if acc > 95:
            return "SH" if hdfl else "S"
        if acc > 90:
            return "A"
        if acc > 80:
            return "B"
        if acc > 70:
            return "C"
        return "D"

    return "A"
