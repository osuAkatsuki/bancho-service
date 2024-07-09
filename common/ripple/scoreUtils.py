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
    user_token = await osuToken.get_token_by_user_id(userID)
    if user_token is None:
        return None

    # Figure out whether they would like
    # to overwrite a relax, vanilla or autopilot score
    # TODO: decide if this feature lives on

    latest_time = -1
    table_for_latest_score: str | None = None
    mode_for_latest_score: int | None = None

    for table in {"scores", "scores_relax", "scores_ap"}:
        latest_score = await glob.db.fetch(
            f"SELECT time, play_mode FROM {table} "
            "WHERE userid = %s AND completed = 2 "
            "ORDER BY id DESC LIMIT 1",
            [userID],
        )
        if latest_score is None:
            continue

        if latest_score["time"] > latest_time:
            latest_time = latest_score["time"]

            table_for_latest_score = table
            mode_for_latest_score = latest_score["play_mode"]

    # no score
    if table_for_latest_score is None:
        return None

    assert mode_for_latest_score is not None

    # Select the users newest completed=2 score
    new_best_score = await glob.db.fetch(
        "SELECT {0}.id, {0}.beatmap_md5, beatmaps.song_name FROM {0} "
        "LEFT JOIN beatmaps USING(beatmap_md5) "
        "WHERE {0}.userid = %s AND {0}.completed = 2 AND {0}.play_mode = %s "
        "ORDER BY {0}.time DESC LIMIT 1".format(table_for_latest_score),
        [userID, mode_for_latest_score],
    )
    assert new_best_score is not None

    # Set their previous completed scores on the map to completed = 2.
    old_best_score = await glob.db.fetch(
        f"SELECT id FROM {table_for_latest_score} "
        "WHERE beatmap_md5 = %s AND completed = 3 "
        "AND userid = %s AND play_mode = %s",
        [new_best_score["beatmap_md5"], userID, mode_for_latest_score],
    )
    assert old_best_score is not None

    await glob.db.execute(
        f"UPDATE {table_for_latest_score} SET completed = 2 "
        "WHERE beatmap_md5 = %s AND completed = 3 "
        "AND userid = %s AND play_mode = %s",
        [new_best_score["beatmap_md5"], userID, mode_for_latest_score],
    )

    # Set their new score to completed = 3.
    await glob.db.execute(
        f"UPDATE {table_for_latest_score} SET completed = 3 WHERE id = %s",
        [new_best_score["id"]],
    )

    # Update the last time they overwrote a score to the current time.
    await glob.db.execute(
        "UPDATE users SET previous_overwrite = UNIX_TIMESTAMP() " "WHERE id = %s",
        [userID],
    )

    if table_for_latest_score == "scores":
        custom_mode_offset = 0
    elif table_for_latest_score == "scores_relax":
        custom_mode_offset = 4
    elif table_for_latest_score == "scores_ap":
        custom_mode_offset = 8
    else:
        raise ValueError(f"Unknown scores table {table_for_latest_score}")

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
                    "mode": adapters.amplitude.format_mode(
                        mode_for_latest_score + custom_mode_offset,
                    ),
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
