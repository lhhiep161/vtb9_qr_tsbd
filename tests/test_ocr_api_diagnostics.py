from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_ocr_status_shape() -> None:
    response = client.get("/api/ocr-status")
    assert response.status_code == 200
    data = response.json()
    assert "python_packages_ok" in data
    assert "tesseract_available" in data
    assert "tesseract_version" in data
    assert "tesseract_cmd" in data
    assert "error" in data


def test_ocr_coordinates_rejects_non_image_with_structured_error() -> None:
    files = {"image": ("note.txt", b"hello", "text/plain")}
    response = client.post("/api/ocr-coordinates", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["ok"] is False
    assert data["stage"] == "upload_read"
    assert data["error_code"] == "UPLOAD_NOT_IMAGE"
    assert "message" in data
    assert "detail" in data
    assert "suggestion" in data


def test_ocr_coordinates_rejects_empty_image() -> None:
    files = {"image": ("empty.png", b"", "image/png")}
    response = client.post("/api/ocr-coordinates", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["ok"] is False
    assert data["stage"] == "upload_read"
    assert data["error_code"] == "UPLOAD_EMPTY"

