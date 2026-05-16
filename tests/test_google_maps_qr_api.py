from __future__ import annotations

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.main import app


client = TestClient(app)


def test_google_maps_qr_direct_lat_lng() -> None:
    resp = client.post("/api/google-maps-qr", json={"input_text": "10.7769,106.7009"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert round(data["latitude"], 4) == 10.7769
    assert round(data["longitude"], 4) == 106.7009
    assert data["qr_png_base64"]


def test_google_maps_qr_space_separated_lat_lng() -> None:
    resp = client.post("/api/google-maps-qr", json={"input_text": "10.7769 106.7009"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_google_maps_qr_full_url_q_param() -> None:
    resp = client.post("/api/google-maps-qr", json={"input_text": "https://www.google.com/maps?q=10.7769,106.7009"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_google_maps_qr_full_url_at_param() -> None:
    resp = client.post("/api/google-maps-qr", json={"input_text": "https://www.google.com/maps/@10.7769,106.7009,17z"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_google_maps_qr_mock_short_link_resolver_success(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "resolve_google_maps_short_link", lambda *_args, **_kwargs: "https://www.google.com/maps/@10.7769,106.7009,17z")
    resp = client.post("/api/google-maps-qr", json={"input_text": "https://maps.app.goo.gl/abc123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "resolved_url" in data
    assert data["resolved_url"]


def test_google_maps_qr_mock_short_link_resolver_failure(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "resolve_google_maps_short_link", lambda *_args, **_kwargs: "https://www.google.com/maps/place/NoCoordinates")
    resp = client.post("/api/google-maps-qr", json={"input_text": "https://maps.app.goo.gl/abc123"})
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert "Không tìm thấy tọa độ" in data["message"]


def test_google_maps_qr_non_google_url_rejected() -> None:
    resp = client.post("/api/google-maps-qr", json={"input_text": "https://example.com/?q=10.1,106.2"})
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False


def test_google_maps_qr_outside_vietnam_warning() -> None:
    resp = client.post("/api/google-maps-qr", json={"input_text": "40.7128,-74.0060"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert any("không nằm trong phạm vi Việt Nam".lower() in w.lower() for w in data["warnings"])
