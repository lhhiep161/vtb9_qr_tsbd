#!/usr/bin/env python3
"""Extract reference coordinate sample(s) from Excel into tests/test_coordinates.csv.

This script intentionally uses Python standard library only (zipfile + XML)
so Excel is not used as runtime engine.
"""

from __future__ import annotations

import csv
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_XLSX = ROOT_DIR / "data" / "reference_excel" / "AJS-Chuyen doi vn2000 sang LatLong excel.xlsx"
OUTPUT_CSV = ROOT_DIR / "tests" / "test_coordinates.csv"

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": NS_MAIN, "r": NS_REL}


def _get_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out: List[str] = []
    for si in root.findall("a:si", NS):
        t = si.find("a:t", NS)
        if t is not None:
            out.append(t.text or "")
            continue
        chunks: List[str] = []
        for rt in si.findall("a:r/a:t", NS):
            chunks.append(rt.text or "")
        out.append("".join(chunks))
    return out


def _sheet_name_to_target(zf: zipfile.ZipFile) -> Dict[str, str]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target: Dict[str, str] = {}
    for rel in rels.findall(f"{{{NS_PKG_REL}}}Relationship"):
        rid_to_target[rel.attrib["Id"]] = rel.attrib["Target"]

    out: Dict[str, str] = {}
    for sheet in wb.findall("a:sheets/a:sheet", NS):
        name = sheet.attrib["name"]
        rid = sheet.attrib[f"{{{NS_REL}}}id"]
        target = rid_to_target[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        out[name] = target
    return out


def _read_sheet_cells(zf: zipfile.ZipFile, sheet_target: str, shared_strings: List[str]) -> Dict[str, str]:
    root = ET.fromstring(zf.read(sheet_target))
    cells: Dict[str, str] = {}
    for cell in root.findall("a:sheetData/a:row/a:c", NS):
        ref = cell.attrib.get("r", "")
        if not ref:
            continue
        v = cell.find("a:v", NS)
        if v is None:
            continue
        raw = v.text or ""
        if cell.attrib.get("t") == "s":
            try:
                value = shared_strings[int(raw)]
            except (ValueError, IndexError):
                value = raw
        else:
            value = raw
        cells[ref] = value
    return cells


def extract_sample() -> Dict[str, str]:
    with zipfile.ZipFile(INPUT_XLSX, "r") as zf:
        shared_strings = _get_shared_strings(zf)
        sheet_map = _sheet_name_to_target(zf)
        if "AJS-Vn2000=>LatLong" not in sheet_map:
            raise RuntimeError("Main sheet 'AJS-Vn2000=>LatLong' not found.")
        cells = _read_sheet_cells(zf, sheet_map["AJS-Vn2000=>LatLong"], shared_strings)

    # Current known sample layout from the main sheet.
    province = cells.get("C2", "").strip()
    input_x = cells.get("C8", "").strip()
    input_y = cells.get("C9", "").strip()
    expected_lat = cells.get("H8", "").strip()
    expected_lng = cells.get("H9", "").strip()
    central_meridian = cells.get("H2", "").strip()
    zone_width = cells.get("H3", "").strip()

    if not all([province, input_x, input_y, expected_lat, expected_lng, central_meridian, zone_width]):
        raise RuntimeError(
            "Cannot extract complete sample from expected main-sheet cells "
            "(C2, C8, C9, H8, H9, H2, H3)."
        )

    return {
        "province": province,
        "input_x": input_x,
        "input_y": input_y,
        "expected_lat": expected_lat,
        "expected_lng": expected_lng,
        "central_meridian_decimal": central_meridian,
        "zone_width": zone_width,
        "source": "reference_excel",
        "note": "Single sample extracted from AJS-Vn2000=>LatLong (main sheet)",
    }


def write_csv(row: Dict[str, str]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "province",
        "input_x",
        "input_y",
        "expected_lat",
        "expected_lng",
        "central_meridian_decimal",
        "zone_width",
        "source",
        "note",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def main() -> None:
    row = extract_sample()
    write_csv(row)
    print(f"Wrote 1 row to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

