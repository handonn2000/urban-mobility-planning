# Phân tích thời tiết và theo dõi biến động

## Dữ liệu và cách chọn

Phạm vi phí/credit/dự báo không đổi. Phần mưa bổ sung 06-08/2024, được chọn sau rà 8.784 giờ thời tiết 2024 nhưng trước khi xem kết quả chuyến. So mười cửa sổ ba tháng liên tục; giữ cửa sổ có >=20 giờ mưa >2 mm/h không phải lễ, ưu tiên số đợt ẩm riêng biệt, rồi số giờ. 06-08 có 35 giờ, 14 đợt. Một đợt là các giờ liên tục có rain>0 hoặc snowfall>0; một đợt có thể có nhiều mức mưa. Đây là quy tắc sàng lọc mẫu cho demo, không phải kiểm định sức mạnh thống kê.

Nguồn thời tiết năm dùng để chọn cửa sổ; khi nối với chuyến, tải JSON theo từng tháng tại cùng tọa độ/múi giờ/model. Giữ đơn vị rain mm/h, snowfall cm/h. Đếm đợt phụ thuộc dữ liệu ERA5 tại Central Park, không phải nhận dạng bão toàn NYC.

## Từ Parquet đến bảng giờ bổ sung

SQL ngắn tách ba bước: chuẩn hóa thời gian; chọn đúng request trong cửa sổ, Uber/Lyft và endpoint xác định; gộp theo giờ. Chờ hợp lệ 0-60 phút, được median trực tiếp ở grain giờ. Chỉ bảng giờ nhỏ vào pandas. Raw bổ sung lưu riêng để không lọt vào phạm vi chính.

## Tính hệ số

1. Ưu tiên tuyết khi snowfall>0. Khô: không mưa/tuyết. Mưa nhỏ 0<rain<0,5 bỏ khỏi hệ số; mưa nhẹ 0,5-2; mưa vừa trở lên >2.
2. Loại ngày lễ khỏi mẫu tính và khỏi baseline khô.
3. Với từng năm/tháng/thứ/giờ, lấy median số chuyến và median của chỉ số chờ theo giờ khô. Chỉ số chờ baseline là median các hourly medians, không phải median toàn bộ chuyến của nhiều giờ.
4. Hệ số từng giờ = số đo giờ đó / baseline. Baseline thiếu hoặc bằng 0 thì để NULL, không bù bằng số 0.
5. Hệ số nhóm = median các tỷ số. Lưu giờ dùng/ngày/đợt, số giờ khô tham chiếu và cờ dưới 20 giờ cho từng metric.
6. Xuất một giờ mưa và nhóm khô tương ứng để tự tính lại. Ví dụ đầu: 8.463 / 7.427 = 1,13949.

Nhóm dry là mốc tham chiếu; drizzle không có hệ số. Báo cáo mùa hè và hai mẫu mùa đông riêng. Hệ số mô tả liên hệ với chuyến hoàn thành, không phải nhân quả hay toàn bộ nhu cầu đặt xe. Hệ số mùa hè không dùng trực tiếp cho tháng 02.

## Watchlist

Một dòng theo ngày × hãng × nhãn vùng trong 90 ngày phạm vi chính. Kỳ vọng = trung bình cùng thứ của D-7 và D-14. Chỉ dùng bộ hai ngày đầy đủ; thiếu bộ thì fallback D-364 nếu có. Thiếu tiếp để NULL và không tạo cảnh báo. Trung bình chờ kỳ vọng dùng trung bình hai daily medians, không phải median gộp chuyến.

Lệch chuyến >±7% hoặc chờ >±20% tạo cảnh báo. Đây là ngưỡng vận hành minh họa, không phải mức ý nghĩa thống kê. Lịch lễ, lễ trong baseline, giờ mưa/tuyết và tỷ lệ mất mẫu cước/chờ được ghi lại. Các nhãn possible_cause là giả thuyết; chưa phải nguyên nhân.

Rà hai case: Lyft ngoài vùng 20/01 và Lyft chạm vùng 21/01. Bảng so sánh giữ cả bốn phân khúc trong hai ngày để không chọn riêng nhóm phù hợp câu chuyện. Chỉ ghi reviewed_with_limitations, không coi đã chứng minh root cause. Các case khác giữ needs_follow_up nhưng có evidence và next_step.

## File đầu ra

- weather_coverage_by_month.csv / weather_window_comparison.csv: rà tháng và cửa sổ.
- weather_study_hourly.csv: 2.208 giờ mùa hè cùng dữ liệu chuyến/thời tiết.
- weather_hourly_factors.csv: số đo và baseline ở từng giờ cho từng mẫu.
- rain_factors.csv: hệ số nhóm và cỡ mẫu.
- demand_monitoring.csv: đủ 360 dòng theo dõi, kể cả không cảnh báo/thiếu baseline.
- watchlist.csv: chỉ các dòng cảnh báo.
- alert_investigations.csv / alert_case_comparison.csv: hai case rà và so cả bốn phân khúc.
- weather_factor_spot_check.csv: ví dụ tính tay.
- reports/rain_factors.png: biểu đồ mưa mùa hè.

Chạy notebook độc lập Run all hoặc `.venv/bin/python scripts/analyze_weather_and_alerts.py` sau chuẩn bị/tổng hợp nguồn. Không cần upload các script/SQL/CSV xử lý khi chạy notebook.

## Dùng trong bước tiếp theo

So độ tương đồng thời tiết giữa cửa sổ phí/credit bằng dữ liệu mùa đông của phạm vi chính. Các hệ số hồi cứu dùng cả giai đoạn; nếu đưa vào forecast phải ước tính lại chỉ tới cutoff. Không dùng thời tiết thực tế sau cutoff làm đầu vào dự báo. Không suy ra số tài xế hoạt động từ thời gian chờ.
