#!/usr/bin/env python3
"""Extract VN2000 local CRS config from reference Excel into CSV.

This script parses the .xlsx file using only Python standard library
(`zipfile` + XML), so it can run without external dependencies.
"""

from __future__ import annotations

import csv
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_XLSX = ROOT_DIR / "data" / "reference_excel" / "AJS-Chuyen doi vn2000 sang LatLong excel.xlsx"
OUTPUT_CSV = ROOT_DIR / "config" / "vn2000_local_crs.csv"

NAMESPACE_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NAMESPACE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NAMESPACE_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": NAMESPACE_MAIN, "r": NAMESPACE_REL}


@dataclass
class ProvinceMeridianRow:
    province_name: str
    central_meridian_decimal: float


def _column_letters(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)\d+$", cell_ref)
    if not match:
        raise ValueError(f"Invalid cell reference: {cell_ref}")
    return match.group(1)


def _split_cell_ref(cell_ref: str) -> Tuple[str, int]:
    match = re.match(r"([A-Z]+)(\d+)$", cell_ref)
    if not match:
        raise ValueError(f"Invalid cell reference: {cell_ref}")
    return match.group(1), int(match.group(2))


def _column_letters_to_index(col: str) -> int:
    value = 0
    for ch in col:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value


def _parse_range_coords(range_ref: str) -> Tuple[str, int, str, int]:
    # OPTION_PARAMETER!$C$15:$D$77 -> C15:D77
    if "!" in range_ref:
        range_ref = range_ref.split("!", 1)[1]
    range_ref = range_ref.replace("$", "")
    start_ref, end_ref = range_ref.split(":", 1)
    start_col, start_row = _split_cell_ref(start_ref)
    end_col, end_row = _split_cell_ref(end_ref)
    return start_col, start_row, end_col, end_row


def _normalize_sheet_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    if target.startswith("worksheets/"):
        return f"xl/{target}"
    return f"xl/{target}"


def _read_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    result: List[str] = []
    for si in root.findall("a:si", NS):
        t = si.find("a:t", NS)
        if t is not None:
            result.append(t.text or "")
            continue
        runs: List[str] = []
        for run in si.findall("a:r", NS):
            rt = run.find("a:t", NS)
            runs.append("" if rt is None else (rt.text or ""))
        result.append("".join(runs))
    return result


def _cell_value(cell: ET.Element, shared_strings: List[str]) -> str:
    value_node = cell.find("a:v", NS)
    if value_node is None:
        return ""
    raw = value_node.text or ""
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw
    return raw


def _load_workbook_metadata(zf: zipfile.ZipFile) -> Tuple[ET.Element, Dict[str, str], Dict[str, str], Dict[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    workbook_rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

    rid_to_target: Dict[str, str] = {}
    for rel in workbook_rels.findall(f"{{{NAMESPACE_PKG_REL}}}Relationship"):
        rid_to_target[rel.attrib["Id"]] = rel.attrib["Target"]

    sheet_name_to_target: Dict[str, str] = {}
    for sheet in workbook.findall("a:sheets/a:sheet", NS):
        name = sheet.attrib["name"]
        rid = sheet.attrib[f"{{{NAMESPACE_REL}}}id"]
        sheet_name_to_target[name] = _normalize_sheet_target(rid_to_target[rid])

    defined_names: Dict[str, str] = {}
    for dn in workbook.findall("a:definedNames/a:definedName", NS):
        dn_name = dn.attrib.get("name", "").strip()
        dn_ref = (dn.text or "").strip()
        if dn_name:
            defined_names[dn_name] = dn_ref
    return workbook, rid_to_target, sheet_name_to_target, defined_names


def _extract_rows_from_sheet_range(
    zf: zipfile.ZipFile,
    sheet_target: str,
    shared_strings: List[str],
    range_ref: str,
) -> List[ProvinceMeridianRow]:
    start_col, start_row, end_col, end_row = _parse_range_coords(range_ref)
    start_idx = _column_letters_to_index(start_col)
    end_idx = _column_letters_to_index(end_col)

    sheet_xml = ET.fromstring(zf.read(sheet_target))
    rows: List[ProvinceMeridianRow] = []

    for row_node in sheet_xml.findall("a:sheetData/a:row", NS):
        row_idx = int(row_node.attrib.get("r", "0"))
        if row_idx < start_row or row_idx > end_row:
            continue

        row_cells: Dict[str, str] = {}
        for cell in row_node.findall("a:c", NS):
            ref = cell.attrib.get("r", "")
            if not ref:
                continue
            col_letters = _column_letters(ref)
            col_idx = _column_letters_to_index(col_letters)
            if start_idx <= col_idx <= end_idx:
                row_cells[col_letters] = _cell_value(cell, shared_strings).strip()

        province = row_cells.get(start_col, "").strip()
        meridian_raw = row_cells.get(end_col, "").strip()
        if not province or not meridian_raw:
            continue
        # Skip header row inside range.
        if province.lower().startswith("tỉnh") or province.lower().startswith("tinh"):
            continue

        try:
            meridian = float(meridian_raw)
        except ValueError:
            continue

        rows.append(ProvinceMeridianRow(province_name=province, central_meridian_decimal=meridian))

    return rows


def _decimal_to_dms_text(decimal_degree: float) -> str:
    degrees = int(decimal_degree)
    minutes = round((decimal_degree - degrees) * 60)
    # Carry if rounded to 60.
    if minutes == 60:
        degrees += 1
        minutes = 0
    return f"{degrees}\N{DEGREE SIGN}{minutes:02d}\N{PRIME}"


def extract_province_rows(xlsx_path: Path) -> List[ProvinceMeridianRow]:
    with zipfile.ZipFile(xlsx_path, "r") as zf:
        shared_strings = _read_shared_strings(zf)
        _, _, sheet_targets, defined_names = _load_workbook_metadata(zf)

        # Prefer defined range from workbook.
        if "DSKTTRUC" in defined_names:
            defined_ref = defined_names["DSKTTRUC"]
            if "!" in defined_ref:
                sheet_name = defined_ref.split("!", 1)[0].replace("'", "")
            else:
                sheet_name = "OPTION_PARAMETER"
            sheet_target = sheet_targets.get(sheet_name)
            if sheet_target:
                rows = _extract_rows_from_sheet_range(zf, sheet_target, shared_strings, defined_ref)
                if rows:
                    return rows

        # Fallback for compatibility.
        fallback_sheet = "OPTION_PARAMETER"
        fallback_range = "C15:D77"
        if fallback_sheet not in sheet_targets:
            raise RuntimeError("Cannot find OPTION_PARAMETER sheet in reference workbook.")
        rows = _extract_rows_from_sheet_range(
            zf,
            sheet_targets[fallback_sheet],
            shared_strings,
            fallback_range,
        )
        if not rows:
            raise RuntimeError("No province/meridian rows found in reference workbook.")
        return rows


def write_config_csv(rows: Iterable[ProvinceMeridianRow], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "province_name",
        "central_meridian_decimal",
        "central_meridian_dms",
        "projection",
        "zone_width",
        "scale_factor",
        "false_easting",
        "false_northing",
        "unit",
        "epsg_code",
        "source",
        "note",
    ]

    rows_sorted = sorted(rows, key=lambda x: x.province_name.casefold())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow(
                {
                    "province_name": row.province_name,
                    "central_meridian_decimal": f"{row.central_meridian_decimal:.2f}".rstrip("0").rstrip("."),
                    "central_meridian_dms": _decimal_to_dms_text(row.central_meridian_decimal),
                    "projection": "TM-3",
                    "zone_width": "3",
                    "scale_factor": "0.9999",
                    "false_easting": "500000",
                    "false_northing": "0",
                    "unit": "meter",
                    "epsg_code": "",
                    "source": "reference_excel",
                    "note": "Extracted from named range DSKTTRUC / OPTION_PARAMETER",
                }
            )

    return len(rows_sorted)


def main() -> None:
    rows = extract_province_rows(INPUT_XLSX)
    count = write_config_csv(rows, OUTPUT_CSV)
    print(f"Extracted {count} province/city rows to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

