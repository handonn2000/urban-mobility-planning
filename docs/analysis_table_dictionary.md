# Bảng phân tích và mẫu số

## daily_segment.csv

Khóa: request_date × operator × touches_zone. Có 90 ngày, 2 hãng, 2 nhãn vùng. Mốc ngày theo request_datetime giờ New York.

## hourly_city.csv

Khóa: request_hour. Có 2.160 giờ. Bao gồm Uber/Lyft và cả hai nhãn vùng trong tập giữ lại. Không có chiều operator/touches_zone; không áp bộ lọc hãng/vùng cho fact này khi làm dashboard.

## Các chỉ số chung

| Cột | Định nghĩa và mẫu số |
|---|---|
| trips | Số chuyến giữ lại, kể cả giá/chờ/quãng đường không dùng được |
| short_trips | Chuyến có quãng đường hữu hạn 0<dặm<2 |
| low_fare_trips | Chuyến có cước dương hữu hạn <=ngưỡng cố định 01/2024 |
| valid_wait_trips | Số chuyến có chờ 0-60 phút; mẫu số của chỉ số chờ |
| valid_fare_trips | Số chuyến có cước dương hữu hạn |
| valid_distance_trips | Số chuyến có quãng đường hữu hạn >0 |
| valid_driver_pay_trips | Số chuyến có driver pay hữu hạn >=0 |
| valid_economics_trips | Số chuyến có cả cước và driver pay hợp lệ |
| total_base_fare | Tổng cước trên đúng mẫu valid_economics |
| total_driver_pay | Tổng tiền tài xế trên đúng mẫu valid_economics |
| median_wait_minutes | Median chờ của mẫu valid_wait; không có mẫu thì NULL |
| data_available | Có coverage nguồn trước khi loại endpoint; không khẳng định báo cáo đầy đủ |
| is_holiday / holiday_name | Cờ/ngày lễ Mỹ, nối theo ngày |
| day_of_week | Thứ theo Python: thứ Hai=0, Chủ nhật=6 |

Giá trung bình của mẫu kinh tế = total_base_fare / valid_economics_trips; không chia cho trips khi có cước bị loại. Proxy tỷ lệ chênh lệch cước = (total_base_fare-total_driver_pay)/total_base_fare trên cùng mẫu; chưa phải take rate kế toán hoặc contribution margin.

low_fare_trips/trips mô tả phần chuyến toàn tập được nhận diện là giá thấp; low_fare_trips/valid_fare_trips mô tả tỷ lệ trong mẫu cước quan sát hợp lệ. Không dùng hai mẫu số thay cho nhau.

hourly_city thêm request_date, hour, source_trips, temperature_c, rain_mm, snowfall_cm. source_trips là số dòng request đúng phạm vi/hãng trước khi loại endpoint. Mưa mm/h, tuyết cm/h, nhiệt độ °C.

## Tổng hợp đúng

Số chuyến, số mẫu và hai tổng tiền có thể cộng. Median không thể lấy trung bình giữa các nhóm để ra median chung; dùng bảng giờ đã tính trực tiếp cho phân tích chờ toàn thành phố. Tổng các tỷ lệ cũng không có nghĩa: cộng tử/mẫu trước khi tính lại tỷ lệ.
