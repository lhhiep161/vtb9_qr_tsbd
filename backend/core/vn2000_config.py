from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class VN2000LocalCRS:
    province_name: str
    central_meridian_decimal: float
    projection: str
    zone_width: int
    scale_factor: float
    false_easting: float
    false_northing: float
    unit: str
    epsg_code: str
    source: str
    note: str


class VN2000ConfigError(Exception):
    pass


class VN2000ConfigLoader:
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self._by_province_key: Dict[str, VN2000LocalCRS] = {}
        self._by_original_name: Dict[str, VN2000LocalCRS] = {}
        self._load()

    @staticmethod
    def _normalize_province_name(value: str) -> str:
        return " ".join(value.strip().casefold().split())

    def _load(self) -> None:
        if not self.csv_path.exists():
            raise VN2000ConfigError(f"VN2000 config CSV not found: {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            required_columns = {
                "province_name",
                "central_meridian_decimal",
                "projection",
                "zone_width",
                "scale_factor",
                "false_easting",
                "false_northing",
                "unit",
                "epsg_code",
                "source",
                "note",
            }
            missing = required_columns.difference(set(reader.fieldnames or []))
            if missing:
                raise VN2000ConfigError(f"VN2000 config CSV missing columns: {sorted(missing)}")

            for row in reader:
                province_name = (row.get("province_name") or "").strip()
                if not province_name:
                    continue
                item = VN2000LocalCRS(
                    province_name=province_name,
                    central_meridian_decimal=float(row["central_meridian_decimal"]),
                    projection=(row["projection"] or "").strip(),
                    zone_width=int(float(row["zone_width"])),
                    scale_factor=float(row["scale_factor"]),
                    false_easting=float(row["false_easting"]),
                    false_northing=float(row["false_northing"]),
                    unit=(row["unit"] or "").strip(),
                    epsg_code=(row.get("epsg_code") or "").strip(),
                    source=(row.get("source") or "").strip(),
                    note=(row.get("note") or "").strip(),
                )

                normalized = self._normalize_province_name(item.province_name)
                self._by_province_key[normalized] = item
                self._by_original_name[item.province_name] = item

        if not self._by_province_key:
            raise VN2000ConfigError(f"No province rows loaded from: {self.csv_path}")

    def get_by_province(self, province_name: str) -> VN2000LocalCRS:
        key = self._normalize_province_name(province_name)
        item = self._by_province_key.get(key)
        if not item:
            raise VN2000ConfigError(f"Province not found in VN2000 config: {province_name}")
        return item

    def list_province_names(self) -> List[str]:
        return sorted(self._by_original_name.keys(), key=lambda x: x.casefold())
