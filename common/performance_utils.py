from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

import settings

performance_service_http_client = httpx.AsyncClient(
    base_url=settings.PERFORMANCE_SERVICE_BASE_URL,
)


# TODO: split sr & pp calculations


class PerformanceRequest(BaseModel):
    beatmap_id: int
    beatmap_md5: str
    mode: int
    mods: int
    max_combo: int
    accuracy: float
    miss_count: int


class PerformanceResult(BaseModel):
    pp: float
    stars: float


async def calculate_performance_batch(
    requests: list[PerformanceRequest],
) -> list[PerformanceResult]:
    try:
        response = await performance_service_http_client.post(
            "/api/v1/calculate",
            json=[request.model_dump() for request in requests],
            timeout=4,
        )
        response.raise_for_status()
    except Exception:
        logging.exception(
            "Performance service returned an error",
            extra={"requests": [request.model_dump() for request in requests]},
        )
        return [PerformanceResult(pp=0.0, stars=0.0) for _ in range(len(requests))]

    return [
        PerformanceResult(pp=result["pp"], stars=result["stars"])
        for result in response.json()
    ]
