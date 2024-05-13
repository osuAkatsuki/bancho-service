from __future__ import annotations

from objects import glob


def make_key(user_id: int) -> str:
    return f"bancho:verifications:{user_id}"


class VerificationStatus:
    NON_EXISTENT = -1
    NOT_VERIFIED = 0
    VERIFIED = 1


async def get(user_id: int) -> int:
    raw_response = await glob.redis.get(make_key(user_id))
    if raw_response is None:
        return VerificationStatus.NON_EXISTENT

    if int(raw_response) == 1:
        return VerificationStatus.VERIFIED
    else:
        return VerificationStatus.NOT_VERIFIED


async def set(user_id: int, status: bool) -> None:
    await glob.redis.set(make_key(user_id), str(1 if status else 0))
