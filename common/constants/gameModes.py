from __future__ import annotations

STD = 0
TAIKO = 1
CTB = 2
MANIA = 3

for_db_dict = {STD: "std", TAIKO: "taiko", CTB: "ctb", MANIA: "mania"}  # trolley


def getGameModeForDB(gameMode: int) -> str:
    """
    Convert a game mode number to string for database table/column

    :param gameMode: game mode number
    :return: game mode readable string for db
    """

    return for_db_dict[gameMode]


for_eyes_dict = {STD: "std", TAIKO: "taiko", CTB: "catch", MANIA: "mania"}


def getGamemodeFull(gameMode: int) -> str:
    """
    Get game mode name from game mode number

    :param gameMode: game mode number
    :return: game mode readable name
    """

    return f"osu!{for_eyes_dict[gameMode]}"
