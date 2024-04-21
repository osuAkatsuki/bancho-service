import logging

import httpx
from objects import glob
import settings


# TODO: split sr & pp calculations
async def calculate_performance(
    beatmap_id: int,
    vanilla_mode: int,
    mods: int,
    max_combo: int,
    acc: float,
    nmiss: int,
) -> tuple[float, float]:
    try:
        response = await glob.http_client.post(
            f"{settings.PERFORMANCE_SERVICE_BASE_URL}/api/v1/calculate",
            json=[
                {
                    "beatmap_id": beatmap_id,
                    "mode": vanilla_mode,
                    "mods": mods,
                    "max_combo": max_combo,
                    "accuracy": acc,
                    "miss_count": nmiss,
                },
            ],
        )
        response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError, TimeoutError):
        logging.exception(
            "Performance service returned an error",
            extra={
                "request_attributes": {
                    "beatmap_id": beatmap_id,
                    "mode": vanilla_mode,
                    "mods": mods,
                    "max_combo": max_combo,
                    "accuracy": acc,
                    "miss_count": nmiss,
                }
            },
        )
        return 0.0, 0.0

    data = response.json()[0]
    return data["pp"], data["stars"]
