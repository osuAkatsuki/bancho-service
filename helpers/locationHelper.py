from __future__ import annotations

from json import loads
from typing import TypedDict
from urllib.request import urlopen

import httpx

import settings
from common.log import logger
from helpers import countryHelper
from objects import glob

API_CALL_TIMEOUT = 3


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
            f"{settings.LOCALIZE_IP_API_URL}/{ip_address}",
            timeout=API_CALL_TIMEOUT,
        )
        response.raise_for_status()
        json = response.json()
        country = json["country"]
        loc = json["loc"].split(",")
        return {
            "iso_country_code": country,
            "osu_country_code": countryHelper.getCountryID(country),
            "latitude": float(loc[0]),
            "longitude": float(loc[1]),
        }
    except:
        logger.exception(
            f"Failed to resolve geolocation for {ip_address}",
            extra={"ip_address": ip_address},
        )
        return unknown_geolocation()
