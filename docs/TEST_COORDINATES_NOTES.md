# TEST_COORDINATES Notes

## Purpose

`tests/test_coordinates.csv` is a reference dataset for MVP v0.1 conversion tests.
It provides known input/output values to validate VN2000 -> WGS84 conversion behavior.

## Source

- Reference file: `data/reference_excel/AJS-Chuyen doi vn2000 sang LatLong excel.xlsx`
- Main sheet used: `AJS-Vn2000=>LatLong`
- Current extracted cells:
  - `province`: `C2`
  - `input_x`: `C8`
  - `input_y`: `C9`
  - `expected_lat`: `H8`
  - `expected_lng`: `H9`
  - `central_meridian_decimal`: `H2`
  - `zone_width`: `H3`

## Regeneration

Use:

```bash
python scripts/extract_test_coordinates.py
```

The script uses only Python standard library (zip/xml parsing) and does not use Excel as runtime engine.

## Limitation in current MVP data

At this stage, the reference workbook exposes one clear sample on the main sheet layout.
Therefore `tests/test_coordinates.csv` currently contains one row.
More verified samples are needed in later phases to improve test coverage and confidence.

## Compliance note

This dataset supports internal reference testing only and does not replace official cadastral/survey validation.

