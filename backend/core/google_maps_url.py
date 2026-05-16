from __future__ import annotations


def build_google_maps_url(latitude: float, longitude: float) -> str:
    return f"https://www.google.com/maps?q={latitude:.12f},{longitude:.12f}"

