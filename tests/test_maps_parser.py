from __future__ import annotations

from backend.core.maps_parser import parse_lat_lng_from_text


def test_parse_plain_lat_lng_comma() -> None:
    result = parse_lat_lng_from_text("10.7769,106.7009")
    assert result == (10.7769, 106.7009)


def test_parse_plain_lat_lng_space() -> None:
    result = parse_lat_lng_from_text("10.7769 106.7009")
    assert result == (10.7769, 106.7009)


def test_parse_google_maps_q_param() -> None:
    result = parse_lat_lng_from_text("https://www.google.com/maps?q=10.7769,106.7009")
    assert result == (10.7769, 106.7009)


def test_parse_google_maps_at_path() -> None:
    result = parse_lat_lng_from_text("https://www.google.com/maps/@10.7769,106.7009,17z")
    assert result == (10.7769, 106.7009)


def test_parse_shortened_maps_link_not_supported() -> None:
    result = parse_lat_lng_from_text("https://maps.app.goo.gl/xyz123")
    assert result is None


def test_parse_invalid_text_returns_none() -> None:
    result = parse_lat_lng_from_text("abc xyz")
    assert result is None

