from __future__ import annotations

import logging
from typing import Any
from typing import TypedDict

import httpx

import settings
from common.log import logger
from helpers import countryHelper

API_CALL_TIMEOUT = 5

ip_api_http_client = httpx.AsyncClient(
    # NOTE: TLS for ip-api is a paid feature
    base_url="http://ip-api.com",
)


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

    response_data: dict[str, Any] | None = None
    try:
        response = await ip_api_http_client.get(
            "/json/{ip_address}",
            timeout=API_CALL_TIMEOUT,
        )
        response.raise_for_status()
        response_data = response.json()
        assert response_data is not None
        country = response_data["countryCode"]
        resolved_geolocation: Geolocation = {
            "iso_country_code": country,
            "osu_country_code": countryHelper.iso_code_to_osu_code(country),
            "latitude": float(response_data["lat"]),
            "longitude": float(response_data["lon"]),
        }
        logging.info(
            "Made request to ip-api.com for geolocation resolution",
            extra={
                "client_ip_address": ip_address,
                "resolved_geolocation": resolved_geolocation,
                "response_status": response.status_code,
            },
        )
        return resolved_geolocation
    except:
        logger.exception(
            f"Failed to resolve geolocation for {ip_address}",
            extra={
                "ip_address": ip_address,
                "response_data": response_data,
            },
        )
        return unknown_geolocation()
