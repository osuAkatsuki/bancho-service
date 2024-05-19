from __future__ import annotations

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


def get_score_grade(
    *,
    game_mode: int,
    mods: int,
    accuracy: float,
    count_300s: int,
    count_100s: int,
    count_50s: int,
    count_misses: int,
) -> str:
    """Return a string with rank/grade for a given score."""
    total = count_300s + count_100s + count_50s + count_misses
    hdfl = (mods & (Mods.HIDDEN | Mods.FLASHLIGHT)) > 0

    if game_mode == 0:
        # osu!
        if accuracy == 100:
            return "XH" if hdfl else "X"
        if count_300s / total > 0.90 and count_50s / total < 0.1 and count_misses == 0:
            return "SH" if hdfl else "S"
        if (count_300s / total > 0.80 and count_misses == 0) or (
            count_300s / total > 0.90
        ):
            return "A"
        if (count_300s / total > 0.70 and count_misses == 0) or (
            count_300s / total > 0.80
        ):
            return "B"
        if count_300s / total > 0.60:
            return "C"
        return "D"
    elif game_mode == 1:
        # TODO: osu!taiko
        return "A"
    elif game_mode == 2:
        # osu!catch
        if accuracy == 100:
            return "XH" if hdfl else "X"
        if 98.01 <= accuracy <= 99.99:
            return "SH" if hdfl else "S"
        if 94.01 <= accuracy <= 98.00:
            return "A"
        if 90.01 <= accuracy <= 94.00:
            return "B"
        if 85.01 <= accuracy <= 90.00:
            return "C"
        return "D"
    elif game_mode == 3:
        # osu!mania
        if accuracy == 100:
            return "XH" if hdfl else "X"
        if accuracy > 95:
            return "SH" if hdfl else "S"
        if accuracy > 90:
            return "A"
        if accuracy > 80:
            return "B"
        if accuracy > 70:
            return "C"
        return "D"

    return "A"
