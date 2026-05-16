from __future__ import annotations

import base64
import csv
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core.distance_calculator import haversine_distance_meters
from backend.main import app


ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_COORDINATES_PATH = ROOT_DIR / "tests" / "test_coordinates.csv"
MAX_DISTANCE_ERROR_METERS = 2.0

client = TestClient(app)


def _load_first_reference_row() -> dict:
    with TEST_COORDINATES_PATH.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, "tests/test_coordinates.csv must have at least one row."
    return rows[0]


def test_convert_endpoint_matches_reference_within_tolerance() -> None:
    row = _load_first_reference_row()
    payload = {
        "province": row["province"],
        "value1": float(row["input_x"]),
        "value2": float(row["input_y"]),
        "input_mode": "auto",
        "current_lat": None,
        "current_lng": None,
    }

    response = client.post("/api/convert", json=payload)
    assert response.status_code == 200
    data = response.json()

    expected_lat = float(row["expected_lat"])
    expected_lng = float(row["expected_lng"])
    actual_lat = float(data["latitude"])
    actual_lng = float(data["longitude"])

    distance_error_m = haversine_distance_meters(expected_lat, expected_lng, actual_lat, actual_lng)
    assert distance_error_m <= MAX_DISTANCE_ERROR_METERS, (
        f"Reference mismatch is {distance_error_m:.3f}m, expected <= {MAX_DISTANCE_ERROR_METERS:.1f}m"
    )

    assert data["province"] == row["province"]
    assert data["used_order"] in {"easting_northing", "northing_easting"}
    assert data["google_maps_url"].startswith("https://www.google.com/maps?q=")
    assert isinstance(data["warnings"], list)

    qr_raw = base64.b64decode(data["qr_png_base64"])
    assert qr_raw.startswith(b"\x89PNG"), "QR payload must be PNG bytes encoded in base64."


def test_convert_endpoint_returns_distance_when_current_gps_provided() -> None:
    row = _load_first_reference_row()
    payload = {
        "province": row["province"],
        "value1": float(row["input_x"]),
        "value2": float(row["input_y"]),
        "input_mode": "auto",
        "current_lat": 11.35,
        "current_lng": 108.88,
    }

    response = client.post("/api/convert", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["distance_meters"] is not None
    assert data["distance_meters"] >= 0
