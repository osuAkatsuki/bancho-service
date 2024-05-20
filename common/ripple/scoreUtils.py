from __future__ import annotations

from amplitude import BaseEvent

import adapters.amplitude
from common.constants import mods
from objects import glob
from objects import osuToken


async def overwritePreviousScore(userID: int) -> str | None:
    """
    Update a users previous score to overwrite all of their other scores, no matter what.
    The ratelimit has already been checked in the case of the !overwrite command.
    """

    # XXX: a bit of a strange dependency -- means the user needs to be online
    # to overwrite a score, but it's not a huge deal. Worth the analytics.
    all_user_tokens = await osuToken.get_all_tokens_by_user_id(userID)

    # Pick the first token, ideally a primary/non-tournament token.
    user_token = next(
        iter(sorted(all_user_tokens, key=lambda t: not t["tournament"])[0]),
        None,
    )
    if user_token is None:
        return None

    # Figure out whether they would like
    # to overwrite a relax or vanilla score
    # TODO: support autopilot, if this feature lives on
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
        return None  # No scores?

    if relax and not vanilla:
        table = "scores_relax"
        mode = relax["play_mode"]
    elif vanilla and not relax:
        table = "scores"
        mode = vanilla["play_mode"]
    else:
        assert vanilla and relax
        table = "scores_relax" if relax["time"] > vanilla["time"] else "scores"
        mode = relax["play_mode"] if table == "scores_relax" else vanilla["play_mode"]

    # Select the users newest completed=2 score
    new_best_score = await glob.db.fetch(
        "SELECT {0}.id, {0}.beatmap_md5, beatmaps.song_name FROM {0} "
        "LEFT JOIN beatmaps USING(beatmap_md5) "
        "WHERE {0}.userid = %s AND {0}.completed = 2 AND {0}.play_mode = %s "
        "ORDER BY {0}.time DESC LIMIT 1".format(table),
        [userID, mode],
    )
    assert new_best_score is not None

    # Set their previous completed scores on the map to completed = 2.
    old_best_score = await glob.db.fetch(
        f"SELECT id FROM {table} "
        "WHERE beatmap_md5 = %s AND completed = 3 "
        "AND userid = %s AND play_mode = %s",
        [new_best_score["beatmap_md5"], userID, mode],
    )
    assert old_best_score is not None

    await glob.db.execute(
        f"UPDATE {table} SET completed = 2 "
        "WHERE beatmap_md5 = %s AND completed = 3 "
        "AND userid = %s AND play_mode = %s",
        [new_best_score["beatmap_md5"], userID, mode],
    )

    # Set their new score to completed = 3.
    await glob.db.execute(
        f"UPDATE {table} SET completed = 3 WHERE id = %s",
        [new_best_score["id"]],
    )

    # Update the last time they overwrote a score to the current time.
    await glob.db.execute(
        "UPDATE users SET previous_overwrite = UNIX_TIMESTAMP() " "WHERE id = %s",
        [userID],
    )

    if glob.amplitude is not None:
        glob.amplitude.track(
            BaseEvent(
                event_type="score_overwrite",
                user_id=str(userID),
                device_id=user_token["amplitude_device_id"],
                event_properties={
                    "new_best_score_id": new_best_score["id"],
                    "old_best_score_id": old_best_score["id"],
                    "beatmap_md5": new_best_score["beatmap_md5"],
                    "mode": adapters.amplitude.format_mode(mode + (4 if relax else 0)),
                    "source": "bancho-service",
                },
            ),
        )

    # Return song_name for the command to send back to the user
    return str(new_best_score["song_name"])


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
