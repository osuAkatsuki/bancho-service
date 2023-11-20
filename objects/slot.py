from __future__ import annotations

from typing import Literal
from typing import Optional
from typing import TypedDict
from typing import Union

import orjson

from constants import matchTeams
from constants import slotStatuses
from objects import glob


class Slot(TypedDict):
    status: int  # slotStatuses.FREE
    team: int  # matchTeams.NO_TEAM
    user_id: int  # -1 # TODO: why -1 instead of None
    user_token: Optional[str]  # string of osutoken
    mods: int
    loaded: bool
    skip: bool
    complete: bool
    score: int
    failed: bool
    passed: bool


def make_key(match_id: int, slot_id: Union[int, Literal["*"]]) -> str:
    return f"bancho:matches:{match_id}:slots:{slot_id}"


async def create_slot(match_id: int, slot_id: int) -> Slot:
    slot: Slot = {
        "status": slotStatuses.FREE,
        "team": matchTeams.NO_TEAM,
        "user_id": -1,
        "user_token": None,
        "mods": 0,
        "loaded": False,
        "skip": False,
        "complete": False,
        "score": 0,
        "failed": False,
        "passed": True,
    }
    await glob.redis.set(make_key(match_id, slot_id), orjson.dumps(slot))
    return slot


async def get_slot(match_id: int, slot_id: int) -> Optional[Slot]:
    slot = await glob.redis.get(make_key(match_id, slot_id))
    if slot is None:
        return None
    return orjson.loads(slot)


async def get_slots(match_id: int) -> list[Slot]:
    keys = [make_key(match_id, slot_id) for slot_id in range(16)]
    raw_slots = await glob.redis.mget(keys)
    slots = []
    for raw_slot in raw_slots:
        assert raw_slot is not None
        slots.append(orjson.loads(raw_slot))
    return slots


async def update_slot(
    match_id: int,
    slot_id: int,
    status: Optional[int] = None,
    team: Optional[int] = None,
    user_id: Optional[int] = None,
    user_token: Optional[str] = "",
    mods: Optional[int] = None,
    loaded: Optional[bool] = None,
    skip: Optional[bool] = None,
    complete: Optional[bool] = None,
    score: Optional[int] = None,
    failed: Optional[bool] = None,
    passed: Optional[bool] = None,
) -> Optional[Slot]:
    slot = await get_slot(match_id, slot_id)
    if slot is None:
        return None

    if status is not None:
        slot["status"] = status
    if team is not None:
        slot["team"] = team
    if user_id is not None:
        slot["user_id"] = user_id
    if user_token != "":
        slot["user_token"] = user_token
    if mods is not None:
        slot["mods"] = mods
    if loaded is not None:
        slot["loaded"] = loaded
    if skip is not None:
        slot["skip"] = skip
    if complete is not None:
        slot["complete"] = complete
    if score is not None:
        slot["score"] = score
    if failed is not None:
        slot["failed"] = failed
    if passed is not None:
        slot["passed"] = passed

    await glob.redis.set(make_key(match_id, slot_id), orjson.dumps(slot))
    return slot


async def delete_slot(match_id: int, slot_id: int) -> None:
    # TODO: should we throw error when no slot exists?
    await glob.redis.delete(make_key(match_id, slot_id))


async def delete_slots(match_id: int) -> None:
    # TODO: should we throw error when no slots exist?
    await glob.redis.delete(*await glob.redis.keys(make_key(match_id, "*")))
