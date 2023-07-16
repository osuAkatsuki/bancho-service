from __future__ import annotations

from objects import match
from objects.osuToken import Token
from objects.redisLock import redisLock

from objects import glob
from amplitude import BaseEvent
from uuid import uuid4


def handle(userToken: Token, _):
    # Make sure we are in a match
    if userToken["match_id"] is None:
        return

    # Make sure the match exists
    multiplayer_match = match.get_match(userToken["match_id"])
    if multiplayer_match is None:
        return

    with redisLock(f"{match.make_key(userToken['match_id'])}:lock"):
        # Host check
        if userToken["user_id"] != multiplayer_match["host_user_id"]:
            return

        match.start(multiplayer_match["match_id"])

    insert_id = str(uuid4())
    glob.amplitude.track(
        BaseEvent(
            event_type="start_multiplayer_match",
            user_id=str(userToken["user_id"]),
            event_properties={
                "match": {
                    "match_id": multiplayer_match["match_id"],
                    "match_name": multiplayer_match["match_name"],
                    # "match_password": multiplayer_match["match_password"],
                    "beatmap_id": multiplayer_match["beatmap_id"],
                    "beatmap_name": multiplayer_match["beatmap_name"],
                    "beatmap_md5": multiplayer_match["beatmap_md5"],
                    "game_mode": multiplayer_match["game_mode"],
                    "host_user_id": multiplayer_match["host_user_id"],
                    "mods": multiplayer_match["mods"],
                    "match_scoring_type": multiplayer_match["match_scoring_type"],
                    "match_team_type": multiplayer_match["match_team_type"],
                    "match_mod_mode": multiplayer_match["match_mod_mode"],
                    "seed": multiplayer_match["seed"],
                    "is_tourney": multiplayer_match["is_tourney"],
                    "is_locked": multiplayer_match["is_locked"],
                    "is_starting": multiplayer_match["is_starting"],
                    "is_in_progress": multiplayer_match["is_in_progress"],
                    "creation_time": multiplayer_match["creation_time"],
                },
            },
            insert_id=insert_id,
        )
    )
