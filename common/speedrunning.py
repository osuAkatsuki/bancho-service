from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
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

    TEN_MINUTES = "10m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


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
    score_type: ScoreType,
) -> UserSpeedrun:
    await glob.db.execute(
        f"""
        INSERT INTO user_speedruns
        (user_id, game_mode, timeframe, score_type, score_value, started_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [user_id, game_mode, timeframe, score_type, 0, datetime.now()],
    )
    speedrun = await get_active_user_speedrun(user_id)
    assert speedrun is not None
    return speedrun


@dataclass
class SpeedrunResults:
    speedrun: UserSpeedrun
    scores: list[SpeedrunScore]


async def end_active_user_speedrun(user_id: int) -> SpeedrunResults | None:
    speedrun = await get_active_user_speedrun(user_id)
    if speedrun is None:
        return None

    speedrun_scores = await get_active_speedrun_scores(user_id)
    assert speedrun_scores is not None

    if speedrun.score_type is ScoreType.WEIGHTED_PP:
        score_value = sum(
            score.value * 0.95 ** (score.rank - 1) for score in speedrun_scores
        )
        score_value += 416.6667 * (1 - 0.9994 ** len(speedrun_scores))
    elif speedrun.score_type is ScoreType.WEIGHTED_SCORE:
        score_value = sum(score.value for score in speedrun_scores)
    else:
        raise NotImplementedError()

    score_value = int(score_value)
    speedrun.score_value = score_value

    await glob.db.execute(
        f"""
        UPDATE user_speedruns
        SET score_value = %s,
            ended_at = %s
        WHERE user_id = %s
        AND ended_at IS NULL
        AND cancelled_at IS NULL
        """,
        [score_value, datetime.now(), user_id],
    )
    return SpeedrunResults(
        speedrun=speedrun,
        scores=speedrun_scores,
    )


async def get_active_user_speedrun(user_id: int) -> UserSpeedrun | None:
    res = await glob.db.fetch(
        f"""
        SELECT {READ_PARAMS}
        FROM user_speedruns
        WHERE user_id = %s
        AND ended_at IS NULL
        AND cancelled_at IS NULL
        """,
        [user_id],
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


@dataclass
class SpeedrunScore:
    value: int
    rank: int
    mods: int
    beatmap_id: int
    song_name: str


async def get_active_speedrun_scores(user_id: int) -> list[SpeedrunScore] | None:
    speedrun = await get_active_user_speedrun(user_id)
    if speedrun is None:
        return None

    if speedrun.score_type is ScoreType.WEIGHTED_PP:
        score_read_param = "pp"
    elif speedrun.score_type is ScoreType.WEIGHTED_SCORE:
        score_read_param = "score"
    else:
        raise NotImplementedError()

    if speedrun.timeframe is SpeedrunTimeframe.TEN_MINUTES:
        interval = timedelta(minutes=10)
    elif speedrun.timeframe is SpeedrunTimeframe.ONE_HOUR:
        interval = timedelta(hours=1)
    elif speedrun.timeframe is SpeedrunTimeframe.ONE_DAY:
        interval = timedelta(days=1)
    elif speedrun.timeframe is SpeedrunTimeframe.ONE_WEEK:
        interval = timedelta(weeks=1)
    else:
        raise NotImplementedError()

    speedrun_starts_at = speedrun.started_at
    speedrun_ends_at = speedrun_starts_at + interval

    if speedrun.game_mode in range(0, 4):
        scores_table = "scores"
    elif speedrun.game_mode in range(4, 8):
        scores_table = "scores_rx"
    elif speedrun.game_mode in range(8, 12):
        scores_table = "scores_ap"
    else:
        raise NotImplementedError()

    recs = await glob.db.fetchAll(
        f"""
        SELECT
            {score_read_param} AS value,
            DENSE_RANK() OVER (
                PARTITION BY scores.userid
                ORDER BY scores.pp DESC
            ) AS score_rank,
            scores.mods,
            beatmaps.beatmap_id,
            beatmaps.song_name
        FROM {scores_table} scores
        JOIN users ON scores.userid = users.id
        JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5
        WHERE scores.userid = %s
        AND scores.play_mode = %s
        AND scores.time BETWEEN %s AND %s
        AND scores.completed = 3
        AND users.privileges & 1
        AND beatmaps.ranked IN (2, 3)
        ORDER BY {score_read_param} DESC
        """,
        [
            user_id,
            speedrun.game_mode,
            speedrun_starts_at.timestamp(),
            speedrun_ends_at.timestamp(),
        ],
    )
    return [
        SpeedrunScore(
            value=rec["value"],
            rank=rec["score_rank"],
            mods=rec["mods"],
            beatmap_id=rec["beatmap_id"],
            song_name=rec["song_name"],
        )
        for rec in recs
    ]


async def get_user_speedruns(
    user_id: int,
    game_mode: int,
    score_type: ScoreType,
    timeframe: SpeedrunTimeframe,
) -> list[UserSpeedrun]:
    res = await glob.db.fetchAll(
        f"""
        SELECT {READ_PARAMS}
        FROM user_speedruns
        WHERE user_id = %s
        AND game_mode = %s
        AND score_type = %s
        AND timeframe = %s
        AND ended_at IS NOT NULL
        AND cancelled_at IS NULL
        ORDER BY score_value DESC
        """,
        [user_id, game_mode, score_type, timeframe],
    )

    return [
        UserSpeedrun(
            id=rec["id"],
            user_id=rec["user_id"],
            game_mode=rec["game_mode"],
            timeframe=SpeedrunTimeframe(rec["timeframe"]),
            score_type=ScoreType(rec["score_type"]),
            score_value=rec["score_value"],
            started_at=rec["started_at"],
            ended_at=rec["ended_at"],
            cancelled_at=rec["cancelled_at"],
        )
        for rec in res
    ]
