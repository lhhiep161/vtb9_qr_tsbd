from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

from pyproj import CRS, Transformer

from backend.core.vn2000_config import VN2000LocalCRS


VIETNAM_LAT_MIN = 8.0
VIETNAM_LAT_MAX = 24.0
VIETNAM_LNG_MIN = 102.0
VIETNAM_LNG_MAX = 110.0

# Excel workbook ("TRANS 7 PARAMETERS") constants for VN2000 -> WGS84.
# ROT_X/ROT_Y/ROT_Z are expressed in arc-seconds for +towgs84 usage.
VN2000_TO_WGS84_TOWGS84 = (
    -191.90441429,
    -39.30318279,
    -111.4503283,
    -0.00928836,
    0.01975479,
    -0.00427372,
    2.52906277e-13,
)


class InputMode(str, Enum):
    AUTO = "auto"
    EASTING_NORTHING = "easting_northing"
    NORTHING_EASTING = "northing_easting"


@dataclass(frozen=True)
class ConversionResult:
    latitude: float
    longitude: float
    used_order: str
    warnings: List[str]


class CoordinateConverter:
    @staticmethod
    def _build_source_crs(local_crs: VN2000LocalCRS) -> CRS:
        proj_name = local_crs.projection.strip().upper()
        if proj_name not in {"TM-3", "TM3", "TM_3"}:
            raise ValueError(f"Unsupported projection in config: {local_crs.projection}")

        dx, dy, dz, rx, ry, rz, ds = VN2000_TO_WGS84_TOWGS84
        proj4 = (
            f"+proj=tmerc +lat_0=0 +lon_0={local_crs.central_meridian_decimal} "
            f"+k={local_crs.scale_factor} +x_0={local_crs.false_easting} "
            f"+y_0={local_crs.false_northing} +ellps=WGS84 "
            f"+towgs84={dx},{dy},{dz},{rx},{ry},{rz},{ds} "
            f"+units=m +no_defs"
        )
        return CRS.from_proj4(proj4)

    @staticmethod
    def _convert_xy(
        x: float,
        y: float,
        local_crs: VN2000LocalCRS,
    ) -> Tuple[float, float]:
        source_crs = CoordinateConverter._build_source_crs(local_crs)
        target_crs = CRS.from_epsg(4326)
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        lng, lat = transformer.transform(x, y)
        return lat, lng

    @staticmethod
    def _is_in_vietnam_bbox(latitude: float, longitude: float) -> bool:
        return (
            VIETNAM_LAT_MIN <= latitude <= VIETNAM_LAT_MAX
            and VIETNAM_LNG_MIN <= longitude <= VIETNAM_LNG_MAX
        )

    @classmethod
    def convert(
        cls,
        value1: float,
        value2: float,
        local_crs: VN2000LocalCRS,
        input_mode: InputMode,
    ) -> ConversionResult:
        warnings: List[str] = []

        if input_mode == InputMode.EASTING_NORTHING:
            lat, lng = cls._convert_xy(value1, value2, local_crs)
            if not cls._is_in_vietnam_bbox(lat, lng):
                warnings.append("Converted coordinate is outside Vietnam bbox (lat 8..24, lng 102..110).")
            return ConversionResult(latitude=lat, longitude=lng, used_order=input_mode.value, warnings=warnings)

        if input_mode == InputMode.NORTHING_EASTING:
            lat, lng = cls._convert_xy(value2, value1, local_crs)
            if not cls._is_in_vietnam_bbox(lat, lng):
                warnings.append("Converted coordinate is outside Vietnam bbox (lat 8..24, lng 102..110).")
            return ConversionResult(latitude=lat, longitude=lng, used_order=input_mode.value, warnings=warnings)

        lat_en, lng_en = cls._convert_xy(value1, value2, local_crs)
        lat_ne, lng_ne = cls._convert_xy(value2, value1, local_crs)

        en_valid = cls._is_in_vietnam_bbox(lat_en, lng_en)
        ne_valid = cls._is_in_vietnam_bbox(lat_ne, lng_ne)

        if en_valid and not ne_valid:
            return ConversionResult(
                latitude=lat_en,
                longitude=lng_en,
                used_order=InputMode.EASTING_NORTHING.value,
                warnings=warnings,
            )

        if ne_valid and not en_valid:
            warnings.append("Input order auto-detected as northing/easting (value1/value2 may be swapped).")
            return ConversionResult(
                latitude=lat_ne,
                longitude=lng_ne,
                used_order=InputMode.NORTHING_EASTING.value,
                warnings=warnings,
            )

        if en_valid and ne_valid:
            warnings.append("Both coordinate orders look valid in Vietnam bbox; defaulted to easting_northing.")
            return ConversionResult(
                latitude=lat_en,
                longitude=lng_en,
                used_order=InputMode.EASTING_NORTHING.value,
                warnings=warnings,
            )

        warnings.append("Neither coordinate order looks valid in Vietnam bbox; defaulted to easting_northing.")
        return ConversionResult(
            latitude=lat_en,
            longitude=lng_en,
            used_order=InputMode.EASTING_NORTHING.value,
            warnings=warnings,
        )
