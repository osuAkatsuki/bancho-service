from __future__ import annotations

from typing import Optional

from common.constants import mods
from objects import glob


async def overwritePreviousScore(
    userID: int,
) -> Optional[str]:  # written pretty horribly, redo one day
    """
    Update a users previous score to overwrite all of their other scores, no matter what.
    The ratelimit has already been checked in the case of the !overwrite command.
    """

    # Figure out whether they would like
    # to overwrite a relax or vanilla score
    relax = await glob.db.fetch(
        "SELECT time, play_mode FROM scores_relax "
        "WHERE userid = %s AND completed = 2 "
        "ORDER BY id DESC LIMIT 1",
        [userID],
    )
    vanilla = await glob.db.fetch(
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
    result = await glob.db.fetch(
        "SELECT {0}.id, {0}.beatmap_md5, beatmaps.song_name FROM {0} "
        "LEFT JOIN beatmaps USING(beatmap_md5) "
        "WHERE {0}.userid = %s AND {0}.completed = 2 AND {0}.play_mode = %s "
        "ORDER BY {0}.time DESC LIMIT 1".format(table),
        [userID, mode],
    )

    # Set their previous completed scores on the map to completed = 2.
    await glob.db.execute(
        f"UPDATE {table} SET completed = 2 "
        "WHERE beatmap_md5 = %s AND (completed & 3) = 3 "
        "AND userid = %s AND play_mode = %s",
        [result["beatmap_md5"], userID, mode],
    )

    # Set their new score to completed = 3.
    await glob.db.execute(
        f"UPDATE {table} SET completed = 3 WHERE id = %s",
        [result["id"]],
    )

    # Update the last time they overwrote a score to the current time.
    await glob.db.execute(
        "UPDATE users SET previous_overwrite = UNIX_TIMESTAMP() " "WHERE id = %s",
        [userID],
    )

    # Return song_name for the command to send back to the user
    return result["song_name"]


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
