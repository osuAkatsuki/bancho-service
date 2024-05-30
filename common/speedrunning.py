from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from objects import glob


class ScoreType(StrEnum):
    """The type of score that the user is speedrunning."""

    # TODO: implicitly only loved/ranked/approved maps
    WEIGHTED_PP = "weighted_pp"
    WEIGHTED_SCORE = "weighted_score"


class SpeedrunTimeframe(StrEnum):
    """The timeframe that the user is speedrunning."""

    TEN_MINUTES = "ten_minutes"
    ONE_HOUR = "one_hour"
    ONE_DAY = "one_day"
    ONE_WEEK = "one_week"


@dataclass
class UserSpeedrun:
    id: UUID
    user_id: int
    game_mode: int
    timeframe: SpeedrunTimeframe
    score_type: ScoreType
    score_value: int
    started_at: datetime
    ended_at: datetime | None
    cancelled_at: datetime | None


READ_PARAMS = """
    id, user_id, game_mode, timeframe, score_type, score_value,
    started_at, ended_at, cancelled_at
"""


async def create_user_speedrun(
    *,
    user_id: int,
    game_mode: int,
    timeframe: SpeedrunTimeframe,
) -> UserSpeedrun:
    await glob.db.execute(
        f"""
        INSERT INTO user_speedruns
        (user_id, game_mode, timeframe, score_type, score_value, started_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        [user_id, game_mode, timeframe, ScoreType.WEIGHTED_PP, 0, datetime.now()],
    )
    speedrun = await get_active_user_speedrun(user_id, game_mode)
    assert speedrun is not None
    return speedrun


async def end_user_speedrun(user_id: int, game_mode) -> UserSpeedrun | None:
    speedrun = await get_active_user_speedrun(user_id, game_mode)
    if speedrun is None:
        return None

    game_mode = 0  # TODO support others
    score_value = await get_active_speedrun_score(user_id, game_mode)

    await glob.db.execute(
        f"""
        UPDATE user_speedruns
        SET score_value = %s,
            ended_at = %s
        WHERE user_id = %s
        AND ended_at IS NULL
        AND cancelled_at IS NULL
        AND game_mode = %s
        """,
        [score_value, datetime.now(), user_id, game_mode],
    )
    return speedrun


async def get_active_user_speedrun(user_id: int, game_mode: int) -> UserSpeedrun | None:
    res = await glob.db.fetch(
        f"""
        SELECT {READ_PARAMS}
        FROM user_speedruns
        WHERE user_id = %s
        AND game_mode = %s
        AND ended_at IS NULL
        AND cancelled_at IS NULL
        """,
        [user_id, game_mode],
    )

    if res is None:
        return None

    return UserSpeedrun(
        id=res["id"],
        user_id=res["user_id"],
        game_mode=res["game_mode"],
        timeframe=SpeedrunTimeframe(res["timeframe"]),
        score_type=ScoreType(res["score_type"]),
        score_value=res["score_value"],
        started_at=res["started_at"],
        ended_at=res["ended_at"],
        cancelled_at=res["cancelled_at"],
    )


async def get_active_speedrun_score(user_id: int, game_mode: int) -> int | None:
    speedrun = await get_active_user_speedrun(user_id, game_mode)
    if speedrun is None:
        return None

    if speedrun.score_type is ScoreType.WEIGHTED_PP:
        score_read_param = "pp"
    elif speedrun.score_type is ScoreType.WEIGHTED_SCORE:
        score_read_param = "score"
    else:
        raise NotImplementedError()

    if speedrun.timeframe is SpeedrunTimeframe.TEN_MINUTES:
        interval = "10 minute"
    elif speedrun.timeframe is SpeedrunTimeframe.ONE_HOUR:
        interval = "1 hour"
    elif speedrun.timeframe is SpeedrunTimeframe.ONE_DAY:
        interval = "1 day"
    elif speedrun.timeframe is SpeedrunTimeframe.ONE_WEEK:
        interval = "1 week"
    else:
        raise NotImplementedError()

    # TODO: rx/ap

    recs = await glob.db.fetchAll(
        f"""
        SELECT
            {score_read_param} AS score_value,
            DENSE_RANK() OVER (
                PARTITION BY userid
                ORDER BY pp DESC
            ) AS score_rank
        FROM scores
        JOIN users ON scores.userid = users.id
        JOIN beatmaps ON scores.beatmap_md5 = beatmaps.md5
        WHERE scores.speedrun_id = %s
        AND scores.time >= (NOW() - INTERVAL %s)
        AND scores.completed = 3
        AND scores.play_mode = %s
        AND users.privileges & 1
        AND beatmaps.ranked IN (2, 3)
        ORDER BY {score_read_param} DESC
        """,
        [speedrun.id, interval, game_mode],
    )
    if speedrun.score_type is ScoreType.WEIGHTED_PP:
        score_value = sum(
            rec["score_value"] * 0.95 ** (rec["score_rank"] - 1) for rec in recs
        )
        score_value += int(416.6667 * (1 - 0.9994 ** len(recs)))
    elif speedrun.score_type is ScoreType.WEIGHTED_SCORE:
        score_value = sum(rec["score_value"] for rec in recs)
    else:
        raise NotImplementedError()

    return score_value
