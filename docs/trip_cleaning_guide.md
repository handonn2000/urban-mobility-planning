# Làm sạch, gắn nhãn và tổng hợp dữ liệu

## Chạy lại

Notebook `notebooks/urban_mobility_demand_analysis.ipynb` chứa đầy đủ hàm SQL và xử lý. Upload riêng notebook lên Colab và Run all; dữ liệu nguồn được tải hoặc xác minh hash rồi tái sử dụng. Không cần upload script/SQL/CSV xử lý. Trên máy có dữ liệu nguồn, có thể chạy CLI:

```sh
.venv/bin/python scripts/clean_and_aggregate_trips.py
```

DuckDB đặt memory_limit 2 GB và lưu bảng chuyến trung gian trên ổ đĩa trong `.analysis-cache/`. Dữ liệu Parquet khoảng 1,43 GB, database xử lý thực tế khoảng 1,6 GB; cần thêm dung lượng cho spill khi xử lý. Cache không đưa lên GitHub. Dữ liệu lớn không đi qua pandas.

## Các bước

1. **Đọc đúng ba file.** Dùng `union_by_name` để giữ schema năm 2024 thiếu cột phí; thiếu cột được đọc NULL, không sửa raw. Lưu tháng nguồn từ filename.
2. **Kiểm tra khóa zone.** LocationID phải duy nhất và không NULL trước khi nối hai lần cho điểm đón/trả. Zone 264 Unknown không đủ thông tin; zone 265 Outside of NYC xác định ngoài vùng và được giữ.
3. **Audit raw.** Đếm 13 quy tắc theo tháng nguồn: request thiếu/ngoài tháng/ngoài phạm vi, hãng khác, endpoint không rõ, pickup thiếu, chờ âm/>60 phút, cước/tiền tài xế/quãng đường không hợp lệ, phí âm/thiếu. Một dòng có thể vi phạm nhiều quy tắc.
4. **Chọn tập phân tích.** Ngày request thuộc 01/2024 hoặc 01-02/2025; hãng Uber/Lyft; hai endpoint xác định. Không loại chỉ vì request khác tháng file. Các lý do loại trong exclusion_summary được áp theo thứ tự nên không chồng lấn.
5. **Tách mẫu metric.** Chờ: 0-60 phút; cước hữu hạn >0; driver pay hữu hạn >=0; quãng đường hữu hạn >0. Lỗi metric không xóa chuyến khỏi đếm. Hai tổng cước/driver pay dùng chung mẫu có cả hai hợp lệ; không gọi chênh lệch là lợi nhuận thực tế.
6. **Suy ra zone.** Tỷ lệ chuyến đón có phí dương trên toàn bộ chuyến đón trong 05-31/01/2025. Zone đạt 95% vào nhãn chính. Báo cáo số chuyến có quan sát phí, đồng thời lưu nhãn 90%/99% để dùng cho sensitivity. Chưa có kết luận về độ vững tác động ở bước này.
7. **Gắn nhãn.** Chạm vùng nếu PU hoặc DO thuộc danh sách; chuyến ngắn 0<dặm<2; chuyến giá thấp là cước dương <=phân vị 25% của toàn bộ tập giữ lại 01/2024, cố định cho mọi tháng/hãng/vùng. Giá trùng ngưỡng được bao gồm nên tỷ lệ có thể hơi hơn 25%.
8. **Gộp SQL.** Ngày × hãng × nhãn vùng, hoặc giờ toàn thành phố trong tập giữ lại. Median chờ tính trực tiếp từ chuyến ở từng grain, không gộp median.
9. **Lấp lưới và nối nguồn nhỏ.** Đủ 90×2×2=360 khóa ngày và 90×24=2.160 khóa giờ. Chỉ điền 0 cho nhóm rỗng khi giờ/ngày có coverage nguồn; thiếu dữ liệu không biến thành 0. Median rỗng vẫn NULL. Nối thời tiết theo giờ và lịch lễ theo ngày sau tổng hợp; cardinality được kiểm tra để tránh nhân đôi.
10. **Đối chiếu.** Tổng 10 metric cộng được trong ngày/giờ khớp tập giữ lại; số chuyến khớp chính xác, tiền cho phép sai khác số thực tối đa một cent ở các mức tổng thông thường. Kiểm tra từng ngày, khóa duy nhất, số quan sát hợp lệ <=số chuyến, chờ trong khoảng quy định và một phân khúc 21/01/2025.

## Đầu ra

| File | Nội dung |
|---|---|
| trip_quality_audit.csv | 13 quy tắc × 3 tháng, số dòng ảnh hưởng/quyết định/lý do |
| trip_exclusion_summary.csv | Phân rã raw thành lý do loại không chồng lấn và chuyến giữ lại |
| zone_fee_profile.csv | Tỷ lệ phí và cỡ mẫu theo zone |
| crz_zones.csv | Danh sách zone ở ngưỡng chính 95% |
| zone_definition_sensitivity.csv | Nhãn zone 90%/95%/99%, chưa phải ước tính tác động |
| daily_segment.csv | 360 dòng, một ngày × hãng × nhãn vùng |
| hourly_city.csv | 2.160 dòng, một giờ toàn thành phố trong tập giữ lại |
| metric_quality_by_date.csv | Mức mất mẫu giá/chờ theo ngày và hãng |
| fee_label_diagnostics.csv | Tỷ lệ có phí ở từng hãng × nhãn vùng |
| aggregation_reconciliation.csv | Tổng từ tập giữ lại so với hai bảng tổng hợp |
| daily_segment_spot_check.csv | Một phân khúc được tính lại từ tập giữ lại |

CSV nằm trong `data/processed/`. Tham số lưu trong `docs/trip_processing_parameters.json`; quyết định và số thật trong `docs/trip_data_quality.md`. SQL được xuất trong `sql/` để đọc lại, không phải phụ thuộc đầu vào của notebook.

## Giới hạn cần giữ trong giải thích

Tháng nguồn theo pickup trong khi phân tích theo request; ở ranh giới tháng 01/2024 không có file 02/2024 để bổ sung. Nhãn endpoint không nhận biết chuyến xuyên vùng. Coverage có dòng không chứng minh nguồn báo cáo đủ mọi chuyến. Cước 0 chưa biết là lỗi báo cáo hay điều chỉnh; giữ chuyến nhưng loại khỏi mẫu giá và nêu mức mất mẫu. Không tự deduplicate bằng một tổ hợp thời gian/zone/giá khi không có trip ID tin cậy.

## Cách đọc SQL

SQL được tách thành từng bước ngắn trong notebook; phần giải thích nằm trong Markdown, code không chèn comment.

- derive_trip_fields.sql: chọn cột cần dùng, tạo ngày/giờ, tên hãng và số phút chờ. Tháng file nối từ bảng source_files, không dùng regex.
- audit_trip_fields.sql: dùng CASE WHEN để tạo cờ hợp lệ; nối bảng ngày và zone.
- retain_classifiable_trips.sql: chọn chuyến bằng WHERE với các cờ đã tạo.
- count_zone_fees.sql: đếm tổng chuyến và số chuyến có phí dương theo điểm đón.
- infer_congestion_zones.sql: nối bảng đếm nhỏ với zone lookup rồi tính tỷ lệ.
- label_analysis_segments.sql: nối danh sách zone cho điểm đón/trả và tạo nhãn bằng CASE WHEN.
- aggregate_daily_segments.sql / aggregate_hourly_city.sql: COUNT, SUM, MEDIAN theo GROUP BY có tên cột rõ ràng.

Mẫu đếm có điều kiện là SUM(CASE WHEN điều kiện THEN 1 ELSE 0 END). Với tiền/chờ, CASE không có ELSE trả NULL để loại quan sát khỏi phép tính, không thay quan sát lỗi bằng 0. Hàm isfinite giữ việc loại NaN/vô cực; MEDIAN và quantile_cont vẫn dùng để giữ đúng mục đích trung vị/phân vị.

File SQL xuất để xem lại; các bảng view nguồn được tạo bởi notebook hoặc script. Notebook không đọc các file SQL này để chạy.
