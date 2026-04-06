"""
yandex maps helpers for the laundry app.

we take a plain-text address, ask yandex's http geocoder for coordinates, then build a
small map-widget link the frontend can drop into an iframe.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

YANDEX_MAPS_API_KEY_ENV = "YANDEX_MAPS_API_KEY"
YANDEX_GEOCODE_URL = "https://geocode-maps.yandex.ru/1.x/"


def _api_key_from_env() -> str:
    key = os.environ.get(YANDEX_MAPS_API_KEY_ENV, "").strip()
    if not key:
        raise ValueError(
            f"missing {YANDEX_MAPS_API_KEY_ENV} in the env"
        )
    return key


def geocode_address(address: str, *, timeout_seconds: float = 10.0) -> tuple[float, float]:
    """
    calls yandex geocoder; returns (longitude, latitude) for the first result.
    """
    params = {
        "apikey": _api_key_from_env(),
        "geocode": address,
        "format": "json",
        "results": 1,
    }
    response = requests.get(YANDEX_GEOCODE_URL, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return _parse_first_point(data)


def _parse_first_point(data: dict[str, Any]) -> tuple[float, float]:
    try:
        members = (
            data["response"]["GeoObjectCollection"]["featureMember"]
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("unexpected geocoder response shape") from exc

    if not members:
        raise ValueError("geocoder returned no results for this address")

    pos = members[0]["GeoObject"]["Point"]["pos"]
    lon_str, lat_str = pos.split()
    return float(lon_str), float(lat_str)


def map_widget_url(
    lon: float,
    lat: float,
    *,
    zoom: int = 16,
    lang: str = "ru_RU",
) -> str:
    """
    link suitable for an <iframe src="..."> yandex map widget centered on lon/lat.
    pt adds a red marker at the same point (pm2rdm).
    """
    query = urlencode(
        {
            "ll": f"{lon},{lat}",
            "z": zoom,
            "pt": f"{lon},{lat},pm2rdm",
            "lang": lang,
        }
    )
    return f"https://yandex.ru/map-widget/v1/?{query}"


def map_widget_iframe_html(
    address: str,
    *,
    width: int = 560,
    height: int = 400,
    zoom: int = 16,
) -> str:
    """geocode the address, then return iframe html for streamlit components.html(...)."""
    lon, lat = geocode_address(address)
    src = map_widget_url(lon, lat, zoom=zoom)
    return (
        f'<iframe src="{src}" width="{width}" height="{height}" '
        'frameborder="0" allowfullscreen="true" '
        'style="border:0;width:100%;max-width:100%;"></iframe>'
    )