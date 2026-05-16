from __future__ import annotations

import logging
import os
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRCandidate:
    point_label: str
    raw_value1: str
    raw_value2: str
    value1: float
    value2: float
    corrections: List[str]
    confidence_note: str


@dataclass(frozen=True)
class OCRStatusInfo:
    python_packages_ok: bool
    tesseract_available: bool
    tesseract_version: str
    tesseract_cmd: str
    error: Optional[str]


@dataclass(frozen=True)
class OCRRunResult:
    raw_text: str
    preprocessing_method: str
    ocr_config: str
    language: str
    warnings: List[str]


class OCRError(Exception):
    def __init__(
        self,
        stage: str,
        error_code: str,
        message: str,
        detail: str,
        suggestion: str,
        status_code: int = 503,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.suggestion = suggestion
        self.status_code = status_code

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "stage": self.stage,
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class _ColumnContext:
    median: float
    int_len: int
    prefix: str


def _normalize_number_token(token: str) -> str:
    value = token.strip().replace(" ", "")
    if "." in value and "," in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    return value


def _extract_numeric_parts(raw: str) -> Optional[Tuple[str, str]]:
    match = re.search(r"(-?)(\d+)(?:[.,](\d+))?", raw.strip())
    if not match:
        return None
    sign = "-" if match.group(1) else ""
    int_part = sign + match.group(2)
    frac = match.group(3) or ""
    return int_part, frac


def _parse_float_strict(raw: str) -> Optional[float]:
    cleaned = raw.strip()
    if not cleaned:
        return None
    if not re.match(r"^-?\d+(?:[.,]\d+)?$", cleaned):
        return None
    try:
        return float(_normalize_number_token(cleaned))
    except ValueError:
        return None


def _build_column_context(values: List[float]) -> Optional[_ColumnContext]:
    if len(values) < 2:
        return None
    int_parts = [str(int(abs(v))) for v in values]
    int_lens = [len(p) for p in int_parts]
    int_len = Counter(int_lens).most_common(1)[0][0]
    prefixes = [p[: min(4, len(p))] for p in int_parts if len(p) == int_len]
    if not prefixes:
        return None
    prefix = Counter(prefixes).most_common(1)[0][0]
    return _ColumnContext(median=float(statistics.median(values)), int_len=int_len, prefix=prefix)


def _proximity_ok(value: float, context: _ColumnContext) -> bool:
    threshold = max(20_000.0, abs(context.median) * 0.2)
    return abs(value - context.median) <= threshold


def _correct_by_column_context(
    raw: str,
    context: Optional[_ColumnContext],
    field_name: str,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    direct = _parse_float_strict(raw)
    if direct is not None:
        return direct, None, None

    if context is None:
        return None, None, f"{field_name}: not enough valid column context for correction ({raw})"

    parts = _extract_numeric_parts(raw)
    if not parts:
        return None, None, f"{field_name}: cannot parse numeric token ({raw})"

    int_part, frac = parts
    is_negative = int_part.startswith("-")
    unsigned = int_part[1:] if is_negative else int_part
    if len(unsigned) != context.int_len - 1:
        return None, None, f"{field_name}: token length does not match one-missing-digit pattern ({raw})"

    lead = context.prefix[0]
    corrected_int = f"{lead}{unsigned}"
    corrected = f"-{corrected_int}" if is_negative else corrected_int
    if frac:
        corrected = f"{corrected}.{frac}"

    try:
        corrected_value = float(corrected)
    except ValueError:
        return None, None, f"{field_name}: failed to build corrected value from {raw}"

    if not _proximity_ok(corrected_value, context):
        return None, None, f"{field_name}: corrected value still far from column median ({raw} -> {corrected_value})"

    note = f"{field_name}: {raw} -> {corrected_value} using column prefix {context.prefix}"
    return corrected_value, note, None


def extract_coordinate_candidates_with_warnings(raw_text: str) -> Tuple[List[OCRCandidate], List[str]]:
    text = raw_text or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    warnings: List[str] = []

    def token_int_len(token: str) -> int:
        parts = _extract_numeric_parts(token)
        if not parts:
            return 0
        int_part = parts[0]
        int_unsigned = int_part[1:] if int_part.startswith("-") else int_part
        return len(int_unsigned)

    def coord_tokens_from_segment(segment: str) -> List[str]:
        raw_tokens = re.findall(r"[^\s]+", segment)
        out: List[str] = []
        for tk in raw_tokens:
            if not re.search(r"\d", tk):
                continue
            if token_int_len(tk) < 5:
                continue
            out.append(tk)
        return out

    raw_rows: List[Tuple[str, str, str]] = []
    for idx, line in enumerate(lines):
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) < 2:
                continue
            left_tokens = coord_tokens_from_segment(parts[0])
            right_tokens = coord_tokens_from_segment(parts[1])
            left = left_tokens[0] if left_tokens else None
            right = right_tokens[0] if right_tokens else None
            if not left or not right:
                continue
            label = str(len(raw_rows) + 1)
            raw_rows.append((label, left, right))
            continue

        # Secondary row-based parser for lines without explicit separator.
        coord_tokens = coord_tokens_from_segment(line)
        if len(coord_tokens) < 2:
            continue
        label_match = re.match(r"^\s*(\w+)\s+", line)
        label = (label_match.group(1) if label_match else str(len(raw_rows) + 1)).strip()
        raw_rows.append((label, coord_tokens[0], coord_tokens[1]))

    if raw_rows:
        col1_valid = [v for _, raw1, _ in raw_rows if (v := _parse_float_strict(raw1)) is not None]
        col2_valid = [v for _, _, raw2 in raw_rows if (v := _parse_float_strict(raw2)) is not None]
        ctx1 = _build_column_context(col1_valid)
        ctx2 = _build_column_context(col2_valid)

        candidates: List[OCRCandidate] = []
        for label, raw1, raw2 in raw_rows:
            v1, corr1, warn1 = _correct_by_column_context(raw1, ctx1, "value1")
            v2, corr2, warn2 = _correct_by_column_context(raw2, ctx2, "value2")

            if warn1:
                warnings.append(warn1)
            if warn2:
                warnings.append(warn2)
            if v1 is None or v2 is None:
                continue

            # Range sanity for VN2000-like table rows.
            big_min, big_max = 1_000_000.0, 2_500_000.0
            small_min, small_max = 300_000.0, 800_000.0
            plausible = (
                (big_min <= v1 <= big_max and small_min <= v2 <= small_max)
                or (big_min <= v2 <= big_max and small_min <= v1 <= small_max)
            )
            if not plausible:
                warnings.append(
                    f"Skipped suspicious row {label}: {v1} | {v2} (possible missing leading digit or OCR noise)."
                )
                continue

            corrections = []
            if corr1:
                corrections.append(corr1)
            if corr2:
                corrections.append(corr2)
            confidence_note = "detected from same OCR row"
            if corrections:
                confidence_note += "; corrected by column context"

            candidates.append(
                OCRCandidate(
                    point_label=label,
                    raw_value1=raw1,
                    raw_value2=raw2,
                    value1=v1,
                    value2=v2,
                    corrections=corrections,
                    confidence_note=confidence_note,
                )
            )

        if candidates:
            return candidates[:50], warnings

    # If any row-like entries were detected, never run nearby-number fallback.
    if raw_rows:
        return [], warnings

    # Fallback only when no row-like entries were detected at all.
    token_pattern = re.compile(r"(?<!\d)(\d{5,10}(?:[.,]\d+)?)(?!\d)")
    tokens = token_pattern.findall(text)
    values: List[float] = []
    for token in tokens:
        parsed = _parse_float_strict(token)
        if parsed is not None:
            values.append(parsed)

    fallback: List[OCRCandidate] = []
    for i in range(len(values) - 1):
        v1, v2 = values[i], values[i + 1]
        fallback.append(
            OCRCandidate(
                point_label=str(i + 1),
                raw_value1=str(v1),
                raw_value2=str(v2),
                value1=v1,
                value2=v2,
                corrections=[],
                confidence_note="detected from nearby OCR numbers (low confidence)",
            )
        )
        if len(fallback) >= 20:
            break
    if fallback:
        warnings.append("Using low-confidence fallback pairing from nearby numbers.")
    return fallback, warnings


def extract_coordinate_candidates_from_text(raw_text: str) -> List[OCRCandidate]:
    candidates, _ = extract_coordinate_candidates_with_warnings(raw_text)
    return candidates


def _resolve_tesseract_cmd() -> str:
    env_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if env_cmd:
        return env_cmd
    win_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if win_default.exists():
        return str(win_default)
    return "tesseract"


def get_ocr_status() -> OCRStatusInfo:
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
    except Exception as exc:
        return OCRStatusInfo(False, False, "", "", f"Missing OCR dependency: {exc.__class__.__name__}")

    tesseract_cmd = _resolve_tesseract_cmd()
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    try:
        version = str(pytesseract.get_tesseract_version())
        logger.info("OCR status - tesseract_cmd=%s version=%s", tesseract_cmd, version)
        return OCRStatusInfo(True, True, version, tesseract_cmd, None)
    except Exception as exc:
        logger.exception("Failed to detect Tesseract command/version.")
        return OCRStatusInfo(True, False, "", tesseract_cmd, f"Tesseract unavailable: {exc.__class__.__name__}")


def run_ocr_with_diagnostics(image_bytes: bytes) -> OCRRunResult:
    status = get_ocr_status()
    if not status.python_packages_ok:
        raise OCRError(
            stage="dependency_check",
            error_code="OCR_DEPENDENCY_MISSING",
            message="OCR dependencies are not installed.",
            detail=status.error or "Missing python OCR packages.",
            suggestion="Install pytesseract, Pillow, OpenCV, numpy and restart backend.",
            status_code=503,
        )
    if not status.tesseract_available:
        raise OCRError(
            stage="dependency_check",
            error_code="TESSERACT_UNAVAILABLE",
            message="Tesseract OCR binary is not available.",
            detail=status.error or "Cannot run tesseract command.",
            suggestion="Chua cau hinh duoc Tesseract OCR. Kiem tra TESSERACT_CMD/PATH.",
            status_code=503,
        )

    try:
        from PIL import Image, ImageFilter
        import numpy as np
        import cv2  # type: ignore
        import pytesseract
    except Exception as exc:
        logger.exception("Unexpected dependency import failure during OCR.")
        raise OCRError(
            stage="dependency_check",
            error_code="OCR_IMPORT_FAILED",
            message="Cannot import OCR dependencies.",
            detail=f"{exc.__class__.__name__}: import failed",
            suggestion="Reinstall OCR dependencies and restart backend.",
            status_code=503,
        ) from exc

    try:
        probe = Image.open(BytesIO(image_bytes))
        probe.verify()
    except Exception as exc:
        logger.exception("Image verify failed in OCR pipeline.")
        raise OCRError(
            stage="image_open",
            error_code="IMAGE_INVALID",
            message="Cannot read uploaded image.",
            detail="Unsupported/corrupt image or invalid file bytes.",
            suggestion="Khong doc duoc file anh. Hay dung JPG/PNG ro net va thu lai.",
            status_code=400,
        ) from exc

    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        logger.exception("Image reopen/convert failed after verify.")
        raise OCRError(
            stage="image_open",
            error_code="IMAGE_REOPEN_FAILED",
            message="Cannot reopen image for OCR.",
            detail="Image verify passed but reopen/convert failed.",
            suggestion="Khong doc duoc file anh. Hay dung JPG/PNG ro net va thu lai.",
            status_code=400,
        ) from exc

    try:
        arr = np.array(img)

        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        gray_2x = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        gray_3x = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        denoise_2x = cv2.fastNlMeansDenoising(gray_2x, None, 10, 7, 21)
        denoise_3x = cv2.fastNlMeansDenoising(gray_3x, None, 10, 7, 21)

        contrast_2x = cv2.convertScaleAbs(denoise_2x, alpha=1.25, beta=10)
        contrast_3x = cv2.convertScaleAbs(denoise_3x, alpha=1.30, beta=12)

        _, otsu_2x = cv2.threshold(contrast_2x, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        adaptive_3x = cv2.adaptiveThreshold(
            contrast_3x,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7,
        )
        sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharp_3x = cv2.filter2D(adaptive_3x, -1, sharpen_kernel)

        preprocess_variants = [
            ("original_rgb", img),
            ("gray_2x_otsu", Image.fromarray(otsu_2x)),
            ("gray_3x_adaptive_sharpen", Image.fromarray(sharp_3x).filter(ImageFilter.SHARPEN)),
        ]
    except Exception as exc:
        logger.exception("Image preprocessing failed for OCR.")
        raise OCRError(
            stage="image_preprocess",
            error_code="IMAGE_PREPROCESS_FAILED",
            message="Image preprocessing failed.",
            detail=f"{exc.__class__.__name__}: preprocessing failed",
            suggestion="Try a clearer crop around coordinate table and upload again.",
            status_code=422,
        ) from exc

    ocr_warnings: List[str] = []
    preferred_lang = "eng+vie"
    lang_to_use = "eng"
    try:
        available_langs = set(pytesseract.get_languages(config=""))
        if {"eng", "vie"}.issubset(available_langs):
            lang_to_use = preferred_lang
        else:
            ocr_warnings.append("Không tìm thấy đủ dữ liệu ngôn ngữ eng+vie, hệ thống dùng eng.")
    except Exception:
        ocr_warnings.append("Không kiểm tra được danh sách ngôn ngữ Tesseract, hệ thống dùng eng.")

    whitelist = "0123456789.,|/-:;()[]{} XYxyABCDDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯàáâãèéêìíòóôõùúăđĩũơưẠ-ỹ"
    ocr_configs = [
        ("table_block", f'--oem 3 --psm 6 -c preserve_interword_spaces=1 -c tessedit_char_whitelist="{whitelist}"'),
        ("line_mode", f'--oem 3 --psm 7 -c preserve_interword_spaces=1 -c tessedit_char_whitelist="{whitelist}"'),
    ]

    best_text = ""
    best_method = ""
    best_cfg = ""
    best_score = -1
    best_candidates: List[OCRCandidate] = []
    best_parse_warnings: List[str] = []
    run_error: Optional[Exception] = None

    for method_name, image_variant in preprocess_variants:
        for cfg_name, cfg_value in ocr_configs:
            try:
                text = pytesseract.image_to_string(image_variant, lang=lang_to_use, config=cfg_value) or ""
            except Exception as exc:
                if lang_to_use == preferred_lang:
                    try:
                        text = pytesseract.image_to_string(image_variant, lang="eng", config=cfg_value) or ""
                        ocr_warnings.append("eng+vie không khả dụng ở lần chạy OCR này, hệ thống đã fallback sang eng.")
                        lang_to_use = "eng"
                    except Exception as exc2:
                        run_error = exc2
                        continue
                else:
                    run_error = exc
                    continue

            candidates, parse_warnings = extract_coordinate_candidates_with_warnings(text)
            score = len(candidates)
            if score > best_score:
                best_score = score
                best_text = text
                best_method = method_name
                best_cfg = cfg_name
                best_candidates = candidates
                best_parse_warnings = parse_warnings

    if best_score < 0:
        logger.exception("Tesseract OCR execution failed.", exc_info=run_error)
        raise OCRError(
            stage="tesseract_run",
            error_code="TESSERACT_RUN_FAILED",
            message="Tesseract OCR run failed.",
            detail=f"{(run_error.__class__.__name__ if run_error else 'UnknownError')}: tesseract execution error",
            suggestion="Chua cau hinh duoc Tesseract OCR. Kiem tra TESSERACT_CMD/PATH.",
            status_code=503,
        ) from run_error

    try:
        _ = best_text or ""
        _ = best_candidates
        _ = best_parse_warnings
    except Exception as exc:
        logger.exception("Text extraction stage failed.")
        raise OCRError(
            stage="text_extract",
            error_code="TEXT_EXTRACT_FAILED",
            message="Failed to read OCR text output.",
            detail=f"{exc.__class__.__name__}: invalid OCR text output",
            suggestion="Retry with another image crop.",
            status_code=500,
        ) from exc

    merged_warnings = list(ocr_warnings)
    return OCRRunResult(
        raw_text=best_text,
        preprocessing_method=best_method,
        ocr_config=best_cfg,
        language=lang_to_use,
        warnings=merged_warnings,
    )
