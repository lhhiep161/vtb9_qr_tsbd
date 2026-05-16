from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse


_PAIR_REGEX = re.compile(r"(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)")
_AT_REGEX = re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")


def _validate_lat_lng(lat: float, lng: float) -> Optional[Tuple[float, float]]:
    if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
        return (lat, lng)
    return None


def parse_lat_lng_from_text(text: str) -> Optional[Tuple[float, float]]:
    value = (text or "").strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return parse_lat_lng_from_google_maps_url(value)

    match = _PAIR_REGEX.search(value)
    if not match:
        return None
    lat = float(match.group(1))
    lng = float(match.group(2))
    return _validate_lat_lng(lat, lng)


def parse_lat_lng_from_google_maps_url(url: str) -> Optional[Tuple[float, float]]:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return None

    query = parse_qs(parsed.query)
    if "q" in query and query["q"]:
        match = _PAIR_REGEX.search(query["q"][0])
        if match:
            lat = float(match.group(1))
            lng = float(match.group(2))
            valid = _validate_lat_lng(lat, lng)
            if valid:
                return valid

    at_match = _AT_REGEX.search(parsed.path) or _AT_REGEX.search(parsed.fragment)
    if at_match:
        lat = float(at_match.group(1))
        lng = float(at_match.group(2))
        valid = _validate_lat_lng(lat, lng)
        if valid:
            return valid

    return None


def is_google_maps_short_link(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"maps.app.goo.gl", "goo.gl"}

