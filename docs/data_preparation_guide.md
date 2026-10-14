# Chuẩn bị dữ liệu và chạy lại

## Chạy trên Google Colab

1. Upload `notebooks/urban_mobility_demand_analysis.ipynb` vào Colab.
2. Dùng CPU runtime; không cần GPU.
3. Chọn Run all. Cell đầu cài các thư viện còn thiếu vào interpreter đang chạy.
4. Cell cấu hình tạo thư mục dữ liệu; các cell sau chứa trực tiếp hàm tải, tổng hợp thời tiết/lễ và kiểm tra.
5. Xem bảng số chuyến, bảng phí quanh ngày 05/01/2025, thời tiết và ngày lễ cuối notebook.

Chỉ cần notebook và Internet. Notebook đầy đủ hiện tải khoảng 2,85 GB Parquet: ba tháng chính và ba tháng riêng cho mưa. Lần chạy sau xác minh SHA-256 rồi tái sử dụng dữ liệu đã có. Mặc định lưu trong runtime; nếu muốn giữ dữ liệu qua phiên Colab, mount Drive và đặt DATA_DIRECTORY tới thư mục đã mount. Không dùng local path của máy tác giả.

## Nguồn và cách xử lý

- TLC: ba file HVFHV Parquet và taxi_zone_lookup.csv; ghi URL, thời điểm UTC, byte, SHA-256. Giữ file raw bất biến.
- Open-Meteo: ba JSON theo tháng; ERA5 Central Park, giờ New York; xuất weather_hourly.csv. Rain mm/h, snowfall cm/h, temperature °C.
- holidays.US: lịch 2024-2025 có ngày nghỉ bù; nối theo ngày, không theo tên ngày lễ.
- DuckDB: đọc schema/metadata và quét phí theo ngày, chỉ chuyển bảng tổng hợp nhỏ sang pandas.

## Các file để kiểm tra

- `data/processed/trip_file_inventory.csv`: số chuyến, kích thước, schema và ngày request theo tháng file.
- `data/processed/congestion_fee_by_request_date.csv`: chuyến/phí theo ngày đặt xe.
- `data/processed/congestion_fee_start_date_checks.csv`: số chuyến đặt/đón/kết thúc trước mốc nhưng có phí.
- `docs/trip_data_schema.json`: tên cột và kiểu dữ liệu.
- `docs/source_data_validation.json`: chẩn đoán kỹ thuật, không phải phần kể chuyện trong notebook.
- `docs/source_data_report.md`: quy mô dữ liệu và các giới hạn.

Dữ liệu thật có 1.890 chuyến có phí đặt trước mốc, 1.184 chuyến đón trước mốc nhưng không chuyến nào kết thúc hoàn toàn trước 05/01. Vì vậy không kết luận sai phí chỉ từ ngày đặt. NULL năm 2024 biểu thị cột phí chưa có, không phải số đo bằng 0.

## Script tùy chọn

```sh
.venv/bin/python scripts/prepare_source_data.py
.venv/bin/python scripts/prepare_source_data.py --validate-only
```

Script và notebook chứa cùng logic thu thập/kiểm tra nhưng notebook không gọi hoặc đọc script. Khi thay đổi logic phải cập nhật cả hai và chạy kiểm tra độc lập.

## Bước phân tích tiếp theo

Audit giờ ngoài tháng, các metric không hợp lệ, chọn tập sạch Uber/Lyft, gắn nhãn vùng, tổng hợp và đối chiếu. Các kết quả tác động/dự báo chưa được thực hiện.
