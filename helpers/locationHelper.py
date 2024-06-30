from __future__ import annotations

import logging
from typing import TypedDict

import settings
from common.log import logger
from helpers import countryHelper
from objects import glob

API_CALL_TIMEOUT = 5


class Geolocation(TypedDict):
    iso_country_code: str  # iso-3166-1 alpha-2
    osu_country_code: int
    latitude: float
    longitude: float


def unknown_geolocation() -> Geolocation:
    return {
        "iso_country_code": "XX",
        "osu_country_code": 0,
        "latitude": 0.0,
        "longitude": 0.0,
    }


async def resolve_ip_geolocation(ip_address: str) -> Geolocation:
    if not settings.LOCALIZE_ENABLE:
        return unknown_geolocation()

    try:
        response = await glob.http_client.get(
            f"http://ip-api.com/json/{ip_address}",
            timeout=API_CALL_TIMEOUT,
        )
        logging.info(
            "Made request to ip-api.com for geolocation resolution",
            extra={
                "client_ip_address": ip_address,
                "response_status": response.status_code,
            },
        )
        response.raise_for_status()
        json = response.json()
        country = json["countryCode"]
        return {
            "iso_country_code": country,
            "osu_country_code": countryHelper.iso_code_to_osu_code(country),
            "latitude": float(json["lat"]),
            "longitude": float(json["lon"]),
        }
    except:
        logger.exception(
            f"Failed to resolve geolocation for {ip_address}",
            extra={"ip_address": ip_address},
        )
        return unknown_geolocation()
