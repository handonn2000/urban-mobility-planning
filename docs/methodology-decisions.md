# Các quyết định phương pháp đã chốt trước phân tích

Ngày chốt: 14/10/2026. Không thay đổi lựa chọn chỉ vì kết quả không giống ví dụ.

1. Giữ đúng 3 tháng theo deck. Không thêm ML, bản đồ hay dữ liệu tàu điện ở phần chính.
2. Chuyến hoàn thành là metric chính. Không gọi đó là toàn bộ booking demand.
3. Dùng request_datetime cho ngày/giờ phân tích; báo cáo riêng chênh lệch với pickup và ngày ngoài tháng. Với kiểm tra thời điểm phí, dùng chuyến kết thúc hoàn toàn trước mốc để kiểm tra lỗi chắc chắn; ghi riêng request/pickup trước mốc nhưng dropoff sau mốc. Không có thời điểm vượt ranh giới vùng nên không khẳng định chính xác lúc tính phí.
4. Thiếu cột phí năm 2024 là khác schema đã biết, không sửa raw. Phí cũ congestion_surcharge không thay thế cbd_congestion_fee.
5. Zone chạm vùng là proxy dựa trên điểm đón/trả, không bao trùm chuyến xuyên vùng.
6. Credit Lyft là quyền giảm giá tương lai, có thể dùng ngoài vùng hoặc Citi Bike; ROI là kịch bản, không phải chi phí chiến dịch đã quan sát.
7. Ngưỡng uplift và tỷ lệ trợ giá phải dùng cùng mẫu số.
8. Hệ số mưa là tỷ số quan sát; chờ tăng không chứng minh tài xế giảm.
9. M5 dùng cutoff 16/02/2025. Không dùng kết quả M4 tới 23/02, actual thời tiết test hay điểm backtest để giả lập quyết định đã biết tại cutoff.
10. Backtest tốt/xấu đều được giữ. Sensitivity đổi chiều được ghi là kết quả không vững, không ép gate thành kết luận có tác động.
11. Lịch holidays gọi Presidents’ Day bằng tên Washington’s Birthday; dùng ngày 17/02/2025 để nối, không nối theo tên hiển thị.
12. Thời tiết ERA5 tại Central Park cố định model và múi giờ để tái lập. Raw rain tính bằng mm/h, snowfall cm/h; không cộng hai cột khác đơn vị.
13. M5 chọn B2 trước làm baseline kế hoạch; B3 là kịch bản chuyển hệ số giữa hai ngày lễ khác nhau, chưa chứng minh tốt hơn. Winner được chọn bằng WAPE toàn tuần sau test và báo cáo riêng, không thay lựa chọn trong memo tại cutoff.
14. History dự báo chỉ đếm chuyến đã hoàn thành trước 00:00 ngày 17/02. Dùng DuckDB tái dựng từ raw, đối chiếu với bảng ngày hồi cứu mà không sửa raw/bảng ngày. Calendar của lễ tương lai là thông tin lịch biết trước, không phải quan sát tương lai.
15. Mô phỏng cutoff giả định record và static lookup truy cập được tại cutoff; TLC monthly release không phải realtime feed. Không tuyên bố quy trình công khai đã triển khai dự báo realtime; chưa mô hình hóa reporting delay.
