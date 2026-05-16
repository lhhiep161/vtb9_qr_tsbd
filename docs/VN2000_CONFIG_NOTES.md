# VN2000 Config Notes

## Muc dich

Tai lieu nay mo ta nguon du lieu va gia dinh su dung cho file cau hinh:

- `config/vn2000_local_crs.csv`

File cau hinh nay duoc dung de anh xa `province_name` -> `central_meridian` cho bai toan doi toa do dia chinh VN2000 sang WGS84 trong MVP v0.1.

## Nguon du lieu tham chieu

- Nguon: `data/reference_excel/AJS-Chuyen doi vn2000 sang LatLong excel.xlsx`
- Vung du lieu uu tien:
  - Named range: `DSKTTRUC` (trong workbook)
  - Fallback: sheet `OPTION_PARAMETER`, vung `C15:D77`
- Truong trich xuat:
  - Ten tinh/thanh pho
  - Kinh tuyen truc (dang decimal degree)

## Script tai tao cau hinh

- Script: `scripts/extract_vn2000_config.py`
- Dau vao: file Excel tham chieu neu tren
- Dau ra: `config/vn2000_local_crs.csv`
- Script co the chay lai de tai tao CSV khi cap nhat file tham chieu.

## Gia dinh ky thuat mac dinh trong CSV

Theo quy uoc MVP, cac cot duoi day duoc gan gia tri co dinh:

- `projection = TM-3`
- `zone_width = 3`
- `scale_factor = 0.9999`
- `false_easting = 500000`
- `false_northing = 0`
- `unit = meter`
- `source = reference_excel`

Cot `central_meridian_dms` duoc quy doi tu decimal degree sang dinh dang DMS rut gon (do + phut), vi du:

- `105.75` -> `105°45′`

Cot `epsg_code` de trong neu chua co doi chieu chinh thuc va tin cay.

## Luu y chat luong du lieu va tuan thu

- File CSV nay la cau hinh ho tro noi bo trong MVP.
- Du lieu trong file tham chieu Excel co the khac biet theo nguon va phien ban.
- Bat buoc doi chieu bo cau hinh nay voi quy dinh dia chinh/chuan VN2000 chinh thuc truoc khi dung cho quy trinh van hanh co yeu cau phap ly cao.
- Ket qua he thong khong thay the xac nhan cua co quan co tham quyen.

