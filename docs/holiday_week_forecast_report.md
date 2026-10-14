# Dự báo tuần có lễ: kết quả hồi cứu

Dự báo 17-23/02/2025, cutoff hết 16/02 theo giờ New York. B2 được chọn trước làm baseline kế hoạch; B3 là kịch bản lễ. Phương án thắng dưới đây chỉ được biết sau tuần kiểm thử.

## Ba cách dự báo

B1=D-7. B2=trung bình D-7 và D-14. B3=B2×hệ số MLK riêng ngày 17/02; sáu ngày còn lại bằng B2. Hệ số riêng từng hãng/nhãn vùng = chuyến 20/01 chia trung bình 13/01 và 27/01. Không thêm machine learning hoặc chỉnh hệ số theo test.

## Điểm toàn tuần

| Cách | MAE (chuyến/ô ngày × phân khúc) | WAPE | Bias |
|---|---:|---:|---:|
| B1 | 7,660.11 | 4.45% | +2.73% |
| B2 | 5,998.20 | 3.48% | +1.06% |
| B3 | 6,219.57 | 3.61% | +1.01% |

Phương án có WAPE thấp nhất hồi cứu: **B2**. Đây là kết luận của một tuần kiểm thử, không phải quyết định đã biết tại cutoff hoặc bằng chứng tổng quát cho mọi tuần có lễ.

## Riêng ngày lễ

| Cách | MAE (chuyến/phân khúc) | WAPE | Bias |
|---|---:|---:|---:|
| B1 | 5,311.50 | 3.60% | +3.48% |
| B2 | 2,084.50 | 1.41% | +0.19% |
| B3 | 3,634.13 | 2.46% | -0.23% |

Bảng điểm đầy đủ gồm toàn tuần, ngày lễ, ngày thường và từng phân khúc. WAPE toàn mẫu = tổng sai số tuyệt đối của 28 ô / tổng actual, không phải trung bình WAPE các phân khúc. Bias dương là dự báo cao, âm là dự báo thấp.

## Đọc kết quả theo phân khúc

| Hãng | Chạm vùng | WAPE B1 | WAPE B2 | WAPE B3 |
|---|---|---:|---:|---:|
| Lyft | False | 4.02% | 3.64% | 3.69% |
| Lyft | True | 6.00% | 5.81% | 5.84% |
| Uber | False | 4.10% | 2.54% | 2.78% |
| Uber | True | 4.87% | 4.43% | 4.40% |

Chênh lệch WAPE B3 trừ B2 là +0.129 điểm %. Toàn bộ khác biệt dự báo nằm ở 17/02. Hệ số MLK gồm cả nhóm tăng và giảm, không giả định mọi phân khúc giảm trong ngày lễ. Đọc bảng phân khúc trước khi quyết định dùng hệ số chung; kết quả một tuần chưa đủ xác nhận mô hình tốt nhất ổn định.

## Hệ số MLK

| Hãng | Chạm vùng | Chuyến MLK | Reference trung bình | Hệ số |
|---|---|---:|---:|---:|
| Uber | False | 304,115 | 298,376.5 | 1.0192 |
| Uber | True | 130,001 | 137,486.0 | 0.9456 |
| Lyft | False | 88,770 | 89,202.0 | 0.9952 |
| Lyft | True | 46,991 | 47,131.0 | 0.9970 |

## Cutoff và giới hạn

History chỉ giữ request từ 01/01 tới 16/02 và dropoff trước 00:00 ngày 17/02. Loại 9,961 chuyến hoàn thành sau cutoff, 0 chuyến thiếu thời điểm hoàn thành. Đối chiếu các chênh lệch với bảng ngày hồi cứu riêng, không sửa bảng ngày hoặc raw.
Forecast và memo được ghi xuống đĩa trước khi ghép actual; hash forecast được kiểm tra sau scoring. Các tham số dùng tháng 01, không dùng kết quả credit tới 23/02 hoặc thời tiết thực tế tương lai. Bộ kiểm tra còn thay đổi mọi volume sau cutoff để xác nhận dự báo giữ nguyên.
Đây là mô phỏng lịch sử với giả định dữ liệu chuyến đã có ở cutoff; TLC công bố theo tháng sau kỳ dữ liệu, không cung cấp feed dự báo realtime. Ngày lễ khác nhau, thời tiết, xu hướng và sự kiện đặc biệt có thể làm MLK không đại diện cho Presidents' Day. B2/B3 không tạo khoảng tin cậy. Chỉ đo nhu cầu được phục vụ, không đo booking bị hủy hoặc số tài xế.

Memo kế hoạch tại cutoff: holiday_week_planning_memo.md. Đầu ra: forecast_week.csv, forecast_evaluation.csv, forecast_scores.csv, forecast_holiday_factors.csv, forecast_source_dates.csv và biểu đồ holiday_week_forecast.png.
