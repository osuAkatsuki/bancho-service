from __future__ import annotations

from typing import Optional
from typing import Union

from common.constants import mods
from objects import glob


def newFirst(
    scoreID: int,
    userID: int,
    md5: str,
    mode: int,
    relax: bool = False,
) -> None:
    """
    Set score into db

    :param userID: user id
    :param scoreID: score id
    :param md5: beatmap md5
    :param mode: gamemode
    :param rx: relax / vanilla bool
    """

    glob.db.execute(
        "REPLACE INTO scores_first VALUES (%s, %s, %s, %s, %s)",
        [md5, mode, 1 if relax else 0, scoreID, userID],
    )


def overwritePreviousScore(
    userID: int,
) -> Optional[str]:  # written pretty horribly, redo one day
    """
    Update a users previous score to overwrite all of their other scores, no matter what.
    The ratelimit has already been checked in the case of the !overwrite command.
    """

    # Figure out whether they would like
    # to overwrite a relax or vanilla score
    relax = glob.db.fetch(
        "SELECT time, play_mode FROM scores_relax "
        "WHERE userid = %s AND completed = 2 "
        "ORDER BY id DESC LIMIT 1",
        [userID],
    )
    vanilla = glob.db.fetch(
        "SELECT time, play_mode FROM scores "
        "WHERE userid = %s AND completed = 2 "
        "ORDER BY id DESC LIMIT 1",
        [userID],
    )

    if not (relax or vanilla):
        return  # No scores?
    elif not relax:
        table = "scores"
    elif not vanilla:
        table = "scores_relax"
    else:
        table = "scores_relax" if relax["time"] > vanilla["time"] else "scores"

    mode = relax["play_mode"] if table == "scores_relax" else vanilla["play_mode"]

    # Select the users newest completed=2 score
    result = glob.db.fetch(
        "SELECT {0}.id, {0}.beatmap_md5, beatmaps.song_name FROM {0} "
        "LEFT JOIN beatmaps USING(beatmap_md5) "
        "WHERE {0}.userid = %s AND {0}.completed = 2 AND {0}.play_mode = %s "
        "ORDER BY {0}.time DESC LIMIT 1".format(table),
        [userID, mode],
    )

    # Set their previous completed scores on the map to completed = 2.
    glob.db.execute(
        f"UPDATE {table} SET completed = 2 "
        "WHERE beatmap_md5 = %s AND (completed & 3) = 3 "
        "AND userid = %s AND play_mode = %s",
        [result["beatmap_md5"], userID, mode],
    )

    # Set their new score to completed = 3.
    glob.db.execute(f"UPDATE {table} SET completed = 3 WHERE id = %s", [result["id"]])

    # Update the last time they overwrote a score to the current time.
    glob.db.execute(
        "UPDATE users SET previous_overwrite = UNIX_TIMESTAMP() " "WHERE id = %s",
        [userID],
    )

    # Return song_name for the command to send back to the user
    return result["song_name"]


def getPPLimit(gameMode: int, mods_used: int) -> str:
    """
    Get PP Limit from DB based on gameMode

    :param gameMode: gamemode
    :param mods: mods used
    """

    s: Union[list[str], str] = ["pp"]
    if mods_used & mods.FLASHLIGHT:
        s.insert(0, "flashlight")
    if mods_used & mods.RELAX:
        s.insert(0, "relax")
    s = "_".join(s)

    return glob.db.fetch(f"SELECT {s} FROM pp_limits WHERE gamemode = %s", [gameMode])[
        s
    ]


def isRankable(m: int, maxCombo: int) -> bool:
    """
    Checks if `m` contains unranked mods

    :param m: mods enum
    :param maxCombo: the map's max combo
    :return: True if there are no unranked mods in `m`, else False
    """  # Allow scorev2 for long maps
    if (m & (mods.RELAX2 | mods.AUTOPLAY)) != 0:
        # has unranked mods
        return False

    if (m & mods.SCOREV2) != 0 and maxCombo < 5000:
        # has scorev2 with less than 5k combo
        # TODO: do this properly by calculating max score on the map,
        #       and checking if it's still in int32 space.
        return False

    return True


def readableMods(m: int) -> str:
    """
    Return a string with readable std mods.
    Used to convert a mods number for oppai

    :param m: mods bitwise number
    :return: readable mods string, eg HDDT
    """

    if not m:
        return ""

    r: list[str] = []
    if m & mods.NOFAIL:
        r.append("NF")
    if m & mods.EASY:
        r.append("EZ")
    if m & mods.TOUCHSCREEN:
        r.append("TD")
    if m & mods.HIDDEN:
        r.append("HD")
    if m & mods.NIGHTCORE:
        r.append("NC")
    elif m & mods.DOUBLETIME:
        r.append("DT")
    if m & mods.HARDROCK:
        r.append("HR")
    if m & mods.RELAX:
        r.append("RX")
    if m & mods.HALFTIME:
        r.append("HT")
    if m & mods.FLASHLIGHT:
        r.append("FL")
    if m & mods.SPUNOUT:
        r.append("SO")
    if m & mods.SCOREV2:
        r.append("V2")

    return "".join(r)
