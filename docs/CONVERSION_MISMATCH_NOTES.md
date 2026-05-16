# Conversion Mismatch Investigation Notes

## Scope

Investigation target: mismatch between API conversion output and `tests/test_coordinates.csv` expected lat/lng.

## Checked items

- Input order from Excel sample:
  - `value1 = Easting (X)` from `C8`
  - `value2 = Northing (Y)` from `C9`
- Local CRS config for sample province (`Ninh Thuận`):
  - central meridian = `108.25`
  - scale factor `k0 = 0.9999`
  - false easting = `500000`
  - false northing = `0`
- Projection: `TM-3 / tmerc`

## Findings

Using only projected CRS (tmerc + WGS84 ellipsoid) without datum transform produced about **225.64 m** mismatch versus Excel sample expected lat/lng.

The Excel workbook sheet `TRANS 7 PARAMETERS` includes explicit VN2000 -> WGS84 Bursa-Wolf parameters:

- `dx = -191.90441429`
- `dy = -39.30318279`
- `dz = -111.4503283`
- `rx = -0.00928836`
- `ry = 0.01975479`
- `rz = -0.00427372`
- `ds = 2.52906277e-13`

Applying these as `+towgs84=dx,dy,dz,rx,ry,rz,ds` reduces mismatch to about **0.54 m** for current sample, which fits the target tolerance (`<= 2 m`).

## Implementation decision

- Implemented Excel-compatible 7-parameter transform in isolated conversion CRS construction.
- Kept runtime independent of Excel (parameters are hardcoded constants from prior extraction/investigation, not read from workbook at runtime).

## Notes

- This improves parity with the current reference workbook sample.
- Additional verified multi-province test points are still needed to validate consistency broadly.

