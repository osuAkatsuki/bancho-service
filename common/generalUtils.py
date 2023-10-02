from __future__ import annotations

from functools import partial
from hashlib import md5
from random import choice
from string import ascii_uppercase
from string import digits
from time import localtime
from time import strftime
from typing import List
from typing import Optional
from typing import Union

from dill import dumps

from common.constants import mods
from common.constants import osuFlags as osu_flags
import logging

possible_chars = ascii_uppercase + digits


def randomString(length: int = 8) -> str:
    return "".join(choice(possible_chars) for _ in range(length))


def secondsToReadable(seconds: int) -> str:
    r: List[str] = []

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


IwantToDie = {"True", "true", "1", 1}


def stringToBool(s: str) -> bool:
    """Convert a string (True/true/1) to bool"""
    return s in IwantToDie


TIME_ORDER_SUFFIXES = ["s", "ms", "μs", "ns", "ps", "fs", "as", "zs", "ys"]


def fmt_time(n: Union[int, float]) -> str:
    for suffix in TIME_ORDER_SUFFIXES:
        if n >= 1:
            break
        n *= 1000  # more to go
    return f"{n:,.2f}{suffix}"


def fileMd5(filename: str) -> str:
    """
    Return filename's md5

    :param filename: name of the file
    :return: file md5
    """
    with open(filename, mode="rb") as f:
        d = md5()
        for buf in iter(partial(f.read, 128), b""):
            d.update(buf)
    return d.hexdigest()


def getRank(
    gameMode: int,
    __mods: int,
    acc: float,
    c300: int,
    c100: int,
    c50: int,
    cmiss: int,
    *,
    score_=None,
) -> str:
    """
    Return a string with rank/grade for a given score.
    Used mainly for tillerino

    :param gameMode: game mode number
    :param __mods: mods value
    :param acc: accuracy
    :param c300: 300 hit count
    :param c100: 100 hit count
    :param c50: 50 hit count
    :param cmiss: misses count
    :param score_: score object. Optional.
    :return: rank/grade string
    """
    if score_:
        return getRank(
            score_.gameMode,
            score_.mods,
            score_.accuracy,
            score_.c300,
            score_.c100,
            score_.c50,
            score_.cMiss,
        )

    total = c300 + c100 + c50 + cmiss
    hdfl = (__mods & (mods.HIDDEN | mods.FLASHLIGHT)) > 0

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


def getTimestamp(full: bool = False) -> str:
    """
    Return current time in YYYY-MM-DD HH:MM:SS format.
    Used in logs.

    :param full: Whether to include date
    :return: readable timestamp
    """
    return strftime("%Y-%m-%d %H:%M:%S" if full else "%H:%M:%S", localtime())


def hexString(s: str) -> str:
    """
    Output `s`'s bytes in DEX
    :param s: string
    :return: string with HEX values
    """
    return ":".join(f"{ord(str(c)):02x}" for c in s)


def getTotalSize(o: object) -> int:
    """
    Get approximate object size using dill

    :param o: object
    :return: approximate bytes size
    """
    try:
        return len(dumps(o, recurse=True))
    except:
        logging.error("Error while getting total object size!")
        return 0


def osuFlagsReadable(bit: int) -> Optional[List[str]]:
    if not bit:
        return
    flags: List[str] = []
    if bit & osu_flags.AinuClient:
        flags.append("[1] AinuClient")
    if bit & osu_flags.SpeedHackDetected:
        flags.append("[2] SpeedHackDetected")
    if bit & osu_flags.IncorrectModValue:
        flags.append("[4] IncorrectModValue")  # should actually always flag
    if bit & osu_flags.MultipleOsuClients:
        flags.append("[8] MultipleOsuClients")
    if bit & osu_flags.ChecksumFailure:
        flags.append("[16] ChecksumFailure")
    if bit & osu_flags.FlashlightChecksumIncorrect:
        flags.append("[32] FlashlightChecksumIncorrect")
    if bit & osu_flags.OsuExecutableChecksum:
        flags.append("[64] OsuExecutableChecksum")
    if bit & osu_flags.MissingProcessesInList:
        flags.append("[128] MissingProcessesInList")
    if bit & osu_flags.FlashLightImageHack:
        flags.append("[256] FlashLightImageHack")
    if bit & osu_flags.SpinnerHack:
        flags.append("[512] SpinnerHack")
    if bit & osu_flags.TransparentWindow:
        flags.append("[1024] TransparentWindow")
    if bit & osu_flags.FastPress:
        flags.append("[2048] FastPress")
    if bit & osu_flags.RawMouseDiscrepancy:
        flags.append("[4096] RawMouseDiscrepancy")
    if bit & osu_flags.RawKeyboardDiscrepancy:
        flags.append("[8192] RawKeyboardDiscrepancy")
    return flags
