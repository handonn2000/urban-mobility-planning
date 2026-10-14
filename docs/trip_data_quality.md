# Làm sạch và tổng hợp chuyến

## Cách thực hiện

1. Audit raw bằng SQL, đếm từng quy tắc riêng. Một chuyến có thể vi phạm nhiều quy tắc; không cộng các dòng audit để suy ra tổng bị loại.
2. Chọn ngày request trong 90 ngày nghiên cứu trên cả ba file; không loại chỉ vì request khác tháng nguồn. Chỉ giữ Uber/Lyft và hai endpoint xác định. Zone 265 Outside of NYC được giữ; 264 Unknown bị loại khỏi tập phân tích chung.
3. Giữ chuyến có giá/chờ/quãng đường lỗi để đếm; chỉ bỏ metric tương ứng. Hai tổng cước và tiền tài xế cùng dùng mẫu kinh tế hợp lệ.
4. Suy ra vùng từ tỷ lệ phí dương trên toàn bộ chuyến đón 05-31/01/2025 của tập giữ lại. Ngưỡng chính 95%; lưu nhãn 90% và 99% để kiểm tra độ vững sau này. Không coi NULL phí là số đo 0.
5. Ngưỡng giá thấp lấy một lần từ cước dương hợp lệ 01/2024; phân vị 25% và dùng <= để bao gồm giá trùng ngưỡng. Chuyến ngắn: 0<dặm<2.
6. Gộp ngày × hãng × nhãn vùng và giờ toàn thành phố; lấp lưới theo coverage, nối thời tiết/lễ với kiểm tra cardinality.
7. Đối chiếu từng metric cộng được với tập giữ lại và giữa hai bảng cho từng ngày; kiểm tra riêng một phân khúc 21/01/2025.

## Quy mô sau xử lý

| Tháng file | Raw | Ngoài thời kỳ | Hãng khác | Endpoint không rõ | Giữ lại |
|---|---:|---:|---:|---:|---:|
| 2024-01 | 19,663,930 | 861.0 | 0.0 | 0.0 | 19,663,069.0 |
| 2025-01 | 20,405,666 | 1,164.0 | 0.0 | 0.0 | 20,404,502.0 |
| 2025-02 | 19,339,461 | 13.0 | 0.0 | 6.0 | 19,339,442.0 |

Tổng giữ lại: 59,407,013 chuyến. Vùng thu phí: 38 zone. Ngưỡng giá thấp: $11.63.
Bảng ngày: 360 dòng. Bảng giờ: 2160 dòng. Median chờ dùng quan sát hợp lệ, không lấy trung bình median giữa các nhóm.

## Quy tắc audit và quyết định

| Quy tắc | Dòng ảnh hưởng trên raw | Quyết định | Lý do |
|---|---:|---|---|
| missing_request_time | 0 | exclude | Không xác định được ngày phân tích |
| request_outside_source_month | 5,362 | flag | Phân tháng theo request trong toàn bộ phạm vi, không loại chỉ vì khác tháng file |
| request_outside_analysis_period | 2,038 | exclude | Ngày đặt ngoài 90 ngày đã chọn |
| unsupported_operator | 0 | exclude | Chỉ phân tích Uber và Lyft |
| unknown_endpoint | 6 | exclude | Không đủ cơ sở gắn nhãn vùng; 264 là Unknown, 265 Outside of NYC được giữ |
| missing_pickup_time | 0 | metric_only | Giữ chuyến; bỏ khỏi mẫu thời gian chờ |
| negative_wait | 581,794 | metric_only | Giữ chuyến; bỏ khỏi mẫu thời gian chờ |
| wait_over_60_minutes | 1,677 | metric_only | Giữ chuyến; bỏ khỏi mẫu thời gian chờ |
| invalid_fare | 26,246 | metric_only | Cước phải hữu hạn và >0; không dùng để tính giá, giá thấp hoặc mẫu kinh tế |
| invalid_driver_pay | 688 | metric_only | Tiền tài xế phải hữu hạn và >=0; không dùng cho mẫu kinh tế |
| invalid_distance | 8,361 | metric_only | Quãng đường phải hữu hạn và >0; không gắn nhãn chuyến ngắn |
| negative_congestion_fee | 0 | flag | Giữ chuyến; khoản điều chỉnh không tính là có phí dương |
| missing_congestion_fee | 19,663,930 | flag | 2024 thiếu cột phí theo schema; không đổi NULL thành 0 |

## Nhãn vùng và phí thực tế

| Hãng | Chạm vùng | Chuyến | Có phí dương | Tỷ lệ |
|---|---|---:|---:|---:|
| Lyft | False | 2,829,790 | 79,793.0 | 2.82% |
| Lyft | True | 1,618,799 | 1,582,513.0 | 97.76% |
| Uber | False | 9,069,038 | 247,585.0 | 2.73% |
| Uber | True | 4,410,674 | 4,389,910.0 | 99.53% |

## Giới hạn

- Cước bằng 0 có thể là điều chỉnh/khuyến mãi hoặc vấn đề báo cáo; chưa biết nguyên nhân. Không xóa chuyến, nhưng trung bình giá chỉ phản ánh mẫu cước dương. metric_quality_by_date.csv cho biết mức mất mẫu theo ngày/hãng.
- Nhãn endpoint không nhận biết chuyến xuyên vùng. Nhóm ngoài vùng vẫn có thể chịu phí; bảng diagnostics lượng hóa sai khác này.
- Bỏ endpoint không rõ làm thay đổi phạm vi so với raw. Các tổng và tỷ lệ trong phân tích chỉ đại diện tập đã giữ lại.
- Tháng 01/2024 thiếu các chuyến request cuối tháng nhưng pickup trong tháng 02/2024. Đầu/cuối phạm vi có sai khác biên; không giả lập dữ liệu chưa tải.
- Mỗi giờ có dòng nguồn không chứng minh nhà cung cấp đã báo cáo đầy đủ mọi chuyến. data_available chỉ phản ánh coverage quan sát.
- Không có trip ID tin cậy để suy ra hai dòng giống nhau là một chuyến. Không tự deduplicate bằng giờ/zone/giá vì có thể xóa chuyến thật.
- Chênh lệch cước và driver pay là proxy, không phải lợi nhuận đóng góp hoặc take rate kế toán đã xác minh.

## Quan sát cần điều tra tiếp

Ngày 2025-01-21, Lyft: 13,927/165,825 chuyến không thuộc mẫu cước dương hợp lệ (8.40%). Đây là hiện tượng dữ liệu cần điều tra, chưa có bằng chứng để gán nguyên nhân cho credit hay chính sách phí.
