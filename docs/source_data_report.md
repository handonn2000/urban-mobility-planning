# Dữ liệu nguồn - Báo cáo thực hiện

Thời điểm kiểm tra UTC: 2026-10-14T09:38:21.618259+00:00

## Cách đã thực hiện

1. Môi trường Python riêng; các thư viện được import thật.
2. Tải nguyên file Parquet/zone và lưu manifest kèm SHA-256.
3. Lấy thời tiết ERA5 theo giờ Central Park, giờ New York; giữ bản JSON API.
4. Xuất lịch lễ Mỹ; DuckDB đọc schema, đếm chuyến và quét phí theo ngày.

## Số dòng thực tế

| Tháng | Chuyến | MB | Có cột phí |
|---|---:|---:|---|
| 2024-01 | 19,663,930 | 472.8 | False |
| 2025-01 | 20,405,666 | 491.1 | True |
| 2025-02 | 19,339,461 | 461.6 | True |

Tổng chuyến raw: 59,409,057.
Thời tiết: 2,160 giờ; zone: 265 dòng; lịch lễ: 22 ngày.

## Kết quả kiểm tra

- Hợp lệ - libraries_import: {"duckdb": "1.5.6", "pandas": "3.0.6", "requests": "2.34.2", "holidays": "0.106"}
- Hợp lệ - schema_2024-01: {"missing": []}
- Hợp lệ - rows_2024-01: {"rows": 19663930}
- Hợp lệ - schema_2025-01: {"missing": []}
- Hợp lệ - rows_2025-01: {"rows": 20405666}
- Hợp lệ - fee_column_2025-01: {}
- Hợp lệ - schema_2025-02: {"missing": []}
- Hợp lệ - rows_2025-02: {"rows": 19339461}
- Hợp lệ - fee_column_2025-02: {}
- Hợp lệ - no_positive_fee_on_trips_ended_before_start: {"positive_fee_trips": 0, "time_basis": "dropoff_datetime < 2025-01-05 00:00 New York", "note": "Trips spanning midnight may have a fee; 2024 has no fee column"}
- Hợp lệ - positive_fee_has_dropoff: {}
- Hợp lệ - positive_fee_after_start: {"positive_fee_trips": 13123818}
- Hợp lệ - zone_unique_key: {"rows": 265}
- Hợp lệ - weather_exact_hour_grid: {"rows": 2160, "expected": 2160}
- Hợp lệ - weather_non_null: {"nulls": {"request_hour": 0, "temperature_c": 0, "rain_mm": 0, "snowfall_cm": 0}}
- Hợp lệ - weather_nonnegative: {}
- Hợp lệ - key_holidays_present: [{"date": "2024-01-15", "holiday_name": "Martin Luther King Jr. Day"}, {"date": "2025-01-20", "holiday_name": "Martin Luther King Jr. Day"}, {"date": "2025-02-17", "holiday_name": "Washington's Birthday"}]
- Hợp lệ - holidays_unique: {"rows": 22}

## Giới hạn và bước tiếp

Kiểm tra mốc phí dựa trên chuyến đã kết thúc trước 00:00 ngày 05/01. Request/pickup trước mốc không đủ kết luận lỗi nếu chuyến kéo dài qua mốc. Không quan sát được thời điểm đi qua ranh giới thu phí.
Chuyến có phí nhưng đặt trước mốc: 1,890; đón trước mốc: 1,184; kết thúc trước mốc: 0. Chi tiết: congestion_fee_start_date_checks.csv.
2024 không có cột phí: không sửa raw và không coi NULL là khoản phí đã đo bằng 0.
Số raw gồm mọi hãng/dòng; chưa phải tập sạch Uber/Lyft. Bước làm sạch sẽ audit giờ ngoài tháng, lỗi metric và nhãn vùng.
Thời tiết ERA5 là dữ liệu tái phân tích tại một điểm, không phải đo toàn thành phố hay forecast tại cutoff.
Chưa ước tính tác động phí, credit hoặc dự báo; không dùng số minh họa trong deck.
