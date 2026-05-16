# VietinBank VN2000 Coordinate Checker

Mobile-first MVP to convert VN2000 cadastral coordinates to WGS84 lat/lng for internal VietinBank reference workflows.

## Backend MVP (FastAPI)

### 1) Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Run API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
GET http://localhost:8000/health
```

Convert endpoint:

```bash
POST http://localhost:8000/api/convert
```

Province list endpoint:

```bash
GET http://localhost:8000/api/provinces
```

### 3) Run tests

```bash
pytest -q
```

## Frontend MVP (Mobile-first Web UI)

### Desktop run

1. Start backend:
   - `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
2. Serve frontend:
   - `python -m http.server 5500`
3. Open:
   - `http://localhost:5500/frontend/index.html`

### Phone LAN run (same Wi-Fi)

1. Start backend:
   - `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
2. Serve frontend:
   - `python -m http.server 5500 --bind 0.0.0.0`
3. Open on phone:
   - `http://<computer-ip>:5500/frontend/index.html`
4. By default, frontend will call:
   - `http://<same-hostname>:8000`
   - Example: `192.168.1.13:5500` -> `192.168.1.13:8000`

### API_BASE_URL override (if needed)

- File: `frontend/config.js`
- Set:
  - `API_BASE_URL_OVERRIDE: "http://<computer-ip>:8000"`
- If override is empty, app auto-resolves backend URL:
  - localhost/127.0.0.1 -> `http://localhost:8000`
  - others -> `http://<same-hostname>:8000`

### GPS note

- GPS on phone may require HTTPS (secure context), depending on browser/device policy.
- `localhost` is typically allowed for desktop local testing.
- Frontend co fallback nhap tay vi tri hien tai: dan `Lat,Long` hoac link Google Maps va bam `Doc vi tri tu noi dung da dan`.

## OCR (Experimental)

- Endpoint: `POST /api/ocr-coordinates` (multipart form field: `image`).
- OCR status endpoint: `GET /api/ocr-status`.
- OCR does not save uploaded images permanently.
- Recommendation: only crop/upload the coordinate area from GCN if possible.
- OCR is experimental. User must verify OCR values before pressing `Convert`.

Tesseract setup:

1. Install Tesseract OCR binary on your OS.
2. Ensure `tesseract` is available on system `PATH`.
3. Install Python dependencies:
   - `pip install -r requirements.txt`
4. If Tesseract is missing, API returns a clear `503` error with install guidance.

Diagnostic error format (`/api/ocr-coordinates`):

```json
{
  "ok": false,
  "stage": "tesseract_run",
  "error_code": "TESSERACT_RUN_FAILED",
  "message": "Tesseract OCR run failed.",
  "detail": "...",
  "suggestion": "..."
}
```

## Notes

- Runtime conversion logic reads `config/vn2000_local_crs.csv`.
- Reference Excel files under `data/reference_excel` are used only for data extraction/testing.
- Google Maps is URL-based only; no Google Maps API is used in MVP v0.1.
- OCR is not implemented.
- GPS is stored in frontend memory state only (not persisted to database/localStorage).
