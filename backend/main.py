from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.coordinate_converter import CoordinateConverter, InputMode
from backend.core.distance_calculator import haversine_distance_meters
from backend.core.google_maps_url import build_google_maps_url
from backend.core.vn2000_config import VN2000ConfigError, VN2000ConfigLoader
from backend.services.ocr_service import (
    OCRError,
    extract_coordinate_candidates_with_warnings,
    get_ocr_status,
    run_ocr_with_diagnostics,
)
from backend.services.qr_service import build_qr_png_base64


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config" / "vn2000_local_crs.csv"

app = FastAPI(title="VietinBank VN2000 Coordinate Checker API", version="0.1.0")
config_loader = VN2000ConfigLoader(CONFIG_PATH)
logger = logging.getLogger(__name__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConvertRequest(BaseModel):
    province: str = Field(min_length=1)
    value1: float
    value2: float
    input_mode: Literal["auto", "easting_northing", "northing_easting"] = "auto"
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None


class ConvertResponse(BaseModel):
    province: str
    latitude: float
    longitude: float
    google_maps_url: str
    qr_png_base64: str
    distance_meters: Optional[float]
    used_order: str
    warnings: List[str]


class ProvincesResponse(BaseModel):
    provinces: List[str]


class OCRCandidateResponse(BaseModel):
    point_label: str
    raw_value1: str
    raw_value2: str
    value1: float
    value2: float
    corrections: List[str]
    confidence_note: str


class OCRCoordinatesResponse(BaseModel):
    ok: bool = True
    raw_text: str
    candidates: List[OCRCandidateResponse]
    warnings: List[str]


class OCRErrorResponse(BaseModel):
    ok: bool = False
    stage: str
    error_code: str
    message: str
    detail: str
    suggestion: str


class OCRStatusResponse(BaseModel):
    python_packages_ok: bool
    tesseract_available: bool
    tesseract_version: str
    tesseract_cmd: str
    error: Optional[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/provinces", response_model=ProvincesResponse)
def list_provinces() -> ProvincesResponse:
    return ProvincesResponse(provinces=config_loader.list_province_names())


@app.get("/api/ocr-status", response_model=OCRStatusResponse)
def ocr_status() -> OCRStatusResponse:
    status = get_ocr_status()
    return OCRStatusResponse(
        python_packages_ok=status.python_packages_ok,
        tesseract_available=status.tesseract_available,
        tesseract_version=status.tesseract_version,
        tesseract_cmd=status.tesseract_cmd,
        error=status.error,
    )


@app.post("/api/ocr-coordinates", response_model=OCRCoordinatesResponse | OCRErrorResponse)
async def ocr_coordinates(image: UploadFile = File(...)):
    if image is None:
        err = OCRError(
            stage="upload_read",
            error_code="UPLOAD_MISSING",
            message="No image upload found.",
            detail="Form field 'image' is missing.",
            suggestion="Select an image file and retry.",
            status_code=400,
        )
        return JSONResponse(status_code=err.status_code, content=err.to_dict())

    if not (image.content_type or "").startswith("image/"):
        err = OCRError(
            stage="upload_read",
            error_code="UPLOAD_NOT_IMAGE",
            message="Uploaded file is not an image.",
            detail=f"content_type={image.content_type or 'unknown'}",
            suggestion="Upload JPG/PNG image file only.",
            status_code=400,
        )
        return JSONResponse(status_code=err.status_code, content=err.to_dict())

    try:
        content = await image.read()
    except Exception as exc:
        logger.exception("Failed reading uploaded OCR image.")
        err = OCRError(
            stage="upload_read",
            error_code="UPLOAD_READ_FAILED",
            message="Failed to read uploaded file.",
            detail=f"{exc.__class__.__name__}: cannot read uploaded bytes",
            suggestion="Retry upload with a smaller/clearer image.",
            status_code=400,
        )
        return JSONResponse(status_code=err.status_code, content=err.to_dict())

    if not content:
        err = OCRError(
            stage="upload_read",
            error_code="UPLOAD_EMPTY",
            message="Uploaded image is empty.",
            detail="File size is 0 bytes.",
            suggestion="Choose a valid JPG/PNG image and retry.",
            status_code=400,
        )
        return JSONResponse(status_code=err.status_code, content=err.to_dict())

    try:
        raw_text = run_ocr_with_diagnostics(content)
    except OCRError as err:
        logger.error("OCR error stage=%s code=%s detail=%s", err.stage, err.error_code, err.detail)
        return JSONResponse(status_code=err.status_code, content=err.to_dict())

    try:
        candidates, parse_warnings = extract_coordinate_candidates_with_warnings(raw_text)
    except Exception as exc:
        logger.exception("Coordinate parse failed after OCR text extraction.")
        err = OCRError(
            stage="coordinate_parse",
            error_code="COORDINATE_PARSE_FAILED",
            message="Failed to parse coordinate candidates from OCR text.",
            detail=f"{exc.__class__.__name__}: parse failed",
            suggestion="Try crop image tighter around coordinate table and retry.",
            status_code=500,
        )
        return JSONResponse(status_code=err.status_code, content=err.to_dict())

    warnings: List[str] = []
    warnings.extend(parse_warnings)
    if not candidates:
        warnings.append("OCR doc duoc anh nhung chua tim thay cap toa do. Hay crop sat vung bang toa do va thu lai.")
    warnings.append("OCR is experimental. Please verify values before conversion.")

    return OCRCoordinatesResponse(
        ok=True,
        raw_text=raw_text,
        candidates=[
            OCRCandidateResponse(
                point_label=item.point_label,
                raw_value1=item.raw_value1,
                raw_value2=item.raw_value2,
                value1=item.value1,
                value2=item.value2,
                corrections=item.corrections,
                confidence_note=item.confidence_note,
            )
            for item in candidates
        ],
        warnings=warnings,
    )


@app.post("/api/convert", response_model=ConvertResponse)
def convert_coordinates(payload: ConvertRequest) -> ConvertResponse:
    try:
        local_crs = config_loader.get_by_province(payload.province)
    except VN2000ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conversion = CoordinateConverter.convert(
        value1=payload.value1,
        value2=payload.value2,
        local_crs=local_crs,
        input_mode=InputMode(payload.input_mode),
    )

    google_maps_url = build_google_maps_url(conversion.latitude, conversion.longitude)
    qr_png_base64 = build_qr_png_base64(google_maps_url)

    distance_meters: Optional[float] = None
    warnings = list(conversion.warnings)
    if payload.current_lat is not None or payload.current_lng is not None:
        if payload.current_lat is None or payload.current_lng is None:
            warnings.append("Both current_lat and current_lng are required to calculate distance.")
        else:
            distance_meters = haversine_distance_meters(
                payload.current_lat,
                payload.current_lng,
                conversion.latitude,
                conversion.longitude,
            )

    return ConvertResponse(
        province=local_crs.province_name,
        latitude=conversion.latitude,
        longitude=conversion.longitude,
        google_maps_url=google_maps_url,
        qr_png_base64=qr_png_base64,
        distance_meters=distance_meters,
        used_order=conversion.used_order,
        warnings=warnings,
    )
