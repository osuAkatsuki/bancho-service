from __future__ import annotations

from enum import IntEnum

import httpx
from pydantic import BaseModel

import settings
from common.log import logger

beatmaps_service_http_client = httpx.AsyncClient(
    base_url=settings.BEATMAPS_SERVICE_BASE_URL,
)


class RankedStatus(IntEnum):
    NOT_SUBMITTED = -1
    PENDING = 0
    UPDATE_AVAILABLE = 1
    RANKED = 2
    APPROVED = 3
    QUALIFIED = 4
    LOVED = 5


class GameMode(IntEnum):
    OSU = 0
    TAIKO = 1
    FRUITS = 2
    MANIA = 3


class AkatsukiBeatmap(BaseModel):
    beatmap_id: int
    beatmapset_id: int
    beatmap_md5: str
    song_name: str
    file_name: str
    ar: float
    od: float
    mode: GameMode
    max_combo: int
    hit_length: int
    bpm: int
    ranked: RankedStatus
    latest_update: int
    ranked_status_freezed: bool
    playcount: int
    passcount: int
    rankedby: int | None
    rating: float
    bancho_ranked_status: RankedStatus | None
    count_circles: int | None
    count_spinners: int | None
    count_sliders: int | None
    bancho_creator_id: int | None
    bancho_creator_name: str | None


async def fetch_by_id(beatmap_id: int, /) -> AkatsukiBeatmap | None:
    try:
        response = await beatmaps_service_http_client.get(
            "/api/akatsuki/v1/beatmaps/lookup",
            params={"beatmap_id": beatmap_id},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        response_data = response.json()
        return AkatsukiBeatmap(**response_data)
    except Exception:
        logger.exception(
            "Failed to fetch beatmap by id from beatmaps-service",
            extra={"beatmap_id": beatmap_id},
        )
        return None
